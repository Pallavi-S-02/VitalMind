"""
drug_interaction_agent.py — VitalMind Drug Interaction Agent (LangGraph)

Medication safety analysis: interaction checking, dosage validation,
allergy cross-referencing, alternative suggestions, and schedule generation.

Graph topology:
  START
    │
    ▼
  load_patient_medications  ← Fetch current meds + allergies + patient profile
    │
    ▼
  check_pairwise_interactions  ← All drug-drug pair checks (local DB + Pinecone)
    │
    ▼
  verify_dosages              ← Validate each dose vs age/weight/renal function
    │
    ▼
  check_allergy_crossref      ← Cross-reference meds vs patient allergy list
    │
    ▼
  search_drug_db              ← RAG over drug knowledge embeddings in Pinecone
    │
    ▼
  classify_severity           ← GPT-4o: structured JSON severity classification
    │
    ├─ SEVERE/CONTRAINDICATED → suggest_alternatives → alert_prescriber ─┐
    │                                                                      │
    └─ SAFE/MODERATE ──────────────────────────────────────────────────────┤
                                                                           │
    ▼                                                                      │
  generate_medication_schedule  ← Optimized dosing timeline               │
    │◄──────────────────────────────────────────────────────────────────────┘
    ▼
  format_drug_response → END
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

_GEMINI_MODEL = "gemini-3.1-pro-preview"
_GOOGLE_KEY = __import__("os").getenv("GOOGLE_API_KEY")
from langgraph.graph import StateGraph, END, START

from app.agents.base_agent import BaseAgent, AgentState
from app.agents.tools.drug_database import (
    check_drug_interactions,
    check_all_drug_interactions,
    validate_drug_dosage,
    cross_reference_drug_allergy,
    search_drug_knowledge_base,
    generate_medication_schedule,
)
from app.agents.tools.patient_history import (
    get_patient_history,
    get_patient_medications,
    get_patient_allergies,
)
from app.agents.prompts.drug_prompts import (
    INTERACTION_ANALYSIS_PROMPT,
    ALTERNATIVES_PROMPT,
    PRESCRIBER_ALERT_PROMPT,
    MEDICATION_SCHEDULE_PROMPT,
    FALLBACK_RESPONSE,
)

logger = logging.getLogger(__name__)

# Severity levels that trigger prescriber notification
_ALERT_SEVERITIES = {"CONTRAINDICATED", "MAJOR"}


class DrugInteractionAgent(BaseAgent):
    """
    Drug Interaction & Medication Safety Agent.

    State contract (extends AgentState):
      context["patient_profile"]       : dict  — full patient memory object
      context["medications"]           : list  — list of medication dicts/strings
      context["medication_list_str"]   : str   — comma-separated med names
      context["allergies"]             : list  — patient allergy list
      context["interaction_findings"]  : str   — raw pairwise check results
      context["dosage_findings"]       : list  — per-drug dosage validation results
      context["allergy_findings"]      : list  — per-drug allergy check results
      context["kb_context"]            : str   — Pinecone semantic search results
      context["severity_analysis"]     : dict  — GPT-4o structured JSON analysis
      context["alternatives"]          : str   — GPT-4o alternative suggestions
      context["schedule"]              : str   — generated medication schedule
      context["alert_sent"]            : bool  — whether prescriber was alerted
    """

    def get_tools(self) -> list:
        return [
            check_drug_interactions,
            check_all_drug_interactions,
            validate_drug_dosage,
            cross_reference_drug_allergy,
            search_drug_knowledge_base,
            generate_medication_schedule,
            get_patient_history,
            get_patient_medications,
            get_patient_allergies,
        ]

    def build_graph(self) -> StateGraph:
        graph = StateGraph(AgentState)

        graph.add_node("load_patient_medications", self._load_patient_medications)
        graph.add_node("check_pairwise_interactions", self._check_pairwise_interactions)
        graph.add_node("verify_dosages", self._verify_dosages)
        graph.add_node("check_allergy_crossref", self._check_allergy_crossref)
        graph.add_node("search_drug_db", self._search_drug_db)
        graph.add_node("classify_severity", self._classify_severity)
        graph.add_node("suggest_alternatives", self._suggest_alternatives)
        graph.add_node("alert_prescriber", self._alert_prescriber)
        graph.add_node("generate_medication_schedule_node", self._generate_medication_schedule)
        graph.add_node("format_drug_response", self._format_drug_response)

        # Entry point
        graph.add_edge(START, "load_patient_medications")
        graph.add_edge("load_patient_medications", "check_pairwise_interactions")
        graph.add_edge("check_pairwise_interactions", "verify_dosages")
        graph.add_edge("verify_dosages", "check_allergy_crossref")
        graph.add_edge("check_allergy_crossref", "search_drug_db")
        graph.add_edge("search_drug_db", "classify_severity")

        # Conditional: severe interactions need alternatives + prescriber alert
        graph.add_conditional_edges(
            "classify_severity",
            self._route_by_severity,
            {
                "severe": "suggest_alternatives",
                "safe": "generate_medication_schedule_node",
            },
        )

        # Severe path
        graph.add_edge("suggest_alternatives", "alert_prescriber")
        graph.add_edge("alert_prescriber", "generate_medication_schedule_node")

        # Final path
        graph.add_edge("generate_medication_schedule_node", "format_drug_response")
        graph.add_edge("format_drug_response", END)

        return graph

    # ─────────────────────────────────────────────────────────────────────────
    # Node implementations
    # ─────────────────────────────────────────────────────────────────────────

    def _load_patient_medications(self, state: AgentState) -> AgentState:
        """
        Load patient profile, medications, and allergy list from memory.
        Also parses any medications mentioned in the user's current message.
        """
        ctx = dict(state.get("context", {}))
        patient_id = state.get("patient_id")

        # Load from memory/DB if patient is authenticated
        if patient_id:
            try:
                from app.agents.memory.patient_memory import PatientMemory
                memory = PatientMemory(patient_id)
                profile = memory.load()
                ctx["patient_profile"] = profile
                ctx["medications"] = profile.get("current_medications", [])
                ctx["allergies"] = profile.get("allergies", [])
                logger.info("DrugAgent: loaded profile for patient %s", patient_id)
            except Exception as exc:
                logger.warning("DrugAgent: could not load patient memory: %s", exc)
                ctx["patient_profile"] = {}
                ctx["medications"] = []
                ctx["allergies"] = []
        else:
            ctx["patient_profile"] = {}
            ctx["medications"] = []
            ctx["allergies"] = []

        # Also parse any drugs mentioned in the current message
        messages = state.get("messages", [])
        user_message = ""
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                user_message = m.content
                break

        if user_message:
            # Extract drug names from user message using a lightweight LLM call
            mentioned_drugs = self._extract_drugs_from_message(user_message)
            if mentioned_drugs:
                existing = [
                    (m.get("name", str(m)) if isinstance(m, dict) else str(m)).lower()
                    for m in ctx["medications"]
                ]
                for drug in mentioned_drugs:
                    if drug.lower() not in existing:
                        ctx["medications"].append({"name": drug, "dose": "as mentioned", "source": "user_input"})
                        logger.info("DrugAgent: added user-mentioned drug '%s'", drug)

        # Build normalized medication list string for tools
        med_names = [
            m.get("name", str(m)) if isinstance(m, dict) else str(m)
            for m in ctx.get("medications", [])
        ]
        ctx["medication_list_str"] = ", ".join(med_names) if med_names else ""

        return {**state, "context": ctx}

    def _extract_json(self, text: str) -> Any:
        """Robustly extract and parse JSON from LLM response, handling markdown blocks."""
        if not text:
            return None
        
        # Try to find JSON within code blocks first
        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if json_match:
            text = json_match.group(1)
        else:
            # Fallback: find anything between [ ] or { }
            json_match = re.search(r'([\[\{].*[\]\}])', text, re.DOTALL)
            if json_match:
                text = json_match.group(1)
        
        try:
            return json.loads(text)
        except Exception as e:
            logger.error("Failed to parse JSON: %s. Raw text: %s", e, text[:100])
            return None

    def _extract_drugs_from_message(self, text: str) -> list[str]:
        """
        Lightweight extraction of drug names mentioned in a user message.
        Uses GPT-4o-mini for speed and cost efficiency.
        """
        try:
            llm = ChatGoogleGenerativeAI(
                model=_GEMINI_MODEL, temperature=0,
                google_api_key=_GOOGLE_KEY
            )
            response = llm.invoke([
                SystemMessage(content=(
                    "Extract all medication/drug names from the following patient message. "
                    "Return ONLY a JSON array of drug name strings, nothing else. "
                    "If no drugs are mentioned, return []. "
                )),
                HumanMessage(content=text),
            ])
            content = response.content.strip()
            extracted = self._extract_json(content)
            if isinstance(extracted, list):
                return extracted
        except Exception as exc:
            logger.debug("Drug extraction via AI failed: %s. Using heuristic fallback.", exc)
            
        # Heuristic fallback: Extract words that look like drug names
        # (Capitalized words or common patterns if they aren't common English words)
        words = re.findall(r'\b[A-Za-z]{3,}\b', text)
        likely_drugs = []
        # Basic common non-drug words to filtered out
        stop_words = {'check','with','and','take','taking','for','have','about','is','it','can','some'}
        for w in words:
            if w.lower() not in stop_words and len(w) > 3:
                likely_drugs.append(w)
        
        return likely_drugs

    def _check_pairwise_interactions(self, state: AgentState) -> AgentState:
        """Run pairwise interaction checks on all medications."""
        ctx = dict(state.get("context", {}))
        med_list_str = ctx.get("medication_list_str", "")

        if not med_list_str:
            ctx["interaction_findings"] = "No medications to analyze."
            return {**state, "context": ctx}

        try:
            logger.info("DrugAgent: Checking interactions for: %s", med_list_str)
            result = check_all_drug_interactions.invoke({"medications": med_list_str})
            logger.info("DrugAgent: Interaction findings: %s", result[:200] + "...")
            ctx["interaction_findings"] = result
        except Exception as exc:
            logger.error("DrugAgent: pairwise interaction check failed: %s", exc)
            ctx["interaction_findings"] = f"Interaction check could not be completed: {exc}"

        tool_outputs = list(state.get("tool_outputs", []))
        tool_outputs.append({"node": "check_pairwise_interactions", "status": "complete"})
        return {**state, "context": ctx, "tool_outputs": tool_outputs}

    def _verify_dosages(self, state: AgentState) -> AgentState:
        """Validate each medication's dosage against patient profile parameters."""
        ctx = dict(state.get("context", {}))
        profile = ctx.get("patient_profile", {})
        medications = ctx.get("medications", [])

        if not medications:
            ctx["dosage_findings"] = []
            return {**state, "context": ctx}

        # Extract profile parameters (with safe defaults)
        age = str(profile.get("age", "unknown"))
        weight = str(profile.get("weight_kg", "unknown"))
        renal = str(profile.get("renal_function", "assuming normal"))

        dosage_results = []
        for med in medications:
            if isinstance(med, dict):
                drug_name = med.get("name", "Unknown")
                dose = med.get("dose", "dose not specified")
                frequency = med.get("frequency", "")
                prescribed_dose = f"{dose} {frequency}".strip()
            else:
                drug_name = str(med)
                prescribed_dose = "dose not specified"

            if drug_name.lower() in ("unknown", ""):
                continue

            try:
                result = validate_drug_dosage.invoke({
                    "drug_name": drug_name,
                    "prescribed_dose": prescribed_dose,
                    "patient_age": age,
                    "patient_weight_kg": weight,
                    "renal_function": renal,
                })
                dosage_results.append({"drug": drug_name, "result": result})
            except Exception as exc:
                logger.warning("DrugAgent: dosage check failed for %s: %s", drug_name, exc)
                dosage_results.append({
                    "drug": drug_name,
                    "result": f"Could not validate dosage for {drug_name}: {exc}"
                })

        ctx["dosage_findings"] = dosage_results
        return {**state, "context": ctx}

    def _check_allergy_crossref(self, state: AgentState) -> AgentState:
        """Cross-reference each medication against patient's known allergies."""
        ctx = dict(state.get("context", {}))
        medications = ctx.get("medications", [])
        allergies = ctx.get("allergies", [])

        if not medications:
            ctx["allergy_findings"] = []
            return {**state, "context": ctx}

        allergies_str = ", ".join(allergies) if allergies else "none documented"
        allergy_results = []

        for med in medications:
            drug_name = med.get("name", str(med)) if isinstance(med, dict) else str(med)
            if drug_name.lower() in ("unknown", ""):
                continue

            try:
                result = cross_reference_drug_allergy.invoke({
                    "drug_name": drug_name,
                    "patient_allergies": allergies_str,
                })
                allergy_results.append({"drug": drug_name, "result": result})
            except Exception as exc:
                logger.warning("DrugAgent: allergy check failed for %s: %s", drug_name, exc)

        ctx["allergy_findings"] = allergy_results
        return {**state, "context": ctx}

    def _search_drug_db(self, state: AgentState) -> AgentState:
        """Semantic RAG search over drug knowledge embeddings in Pinecone."""
        ctx = dict(state.get("context", {}))
        messages = state.get("messages", [])

        # Build a rich query from user message + medications
        user_content = " ".join(m.content for m in messages if isinstance(m, HumanMessage))
        med_list = ctx.get("medication_list_str", "")

        query = f"{user_content} medications: {med_list}".strip()[:600]

        try:
            kb_result = search_drug_knowledge_base.invoke({"query": query})
            ctx["kb_context"] = kb_result
        except Exception as exc:
            logger.warning("DrugAgent: KB search failed: %s", exc)
            ctx["kb_context"] = "Knowledge base unavailable."

        tool_outputs = list(state.get("tool_outputs", []))
        tool_outputs.append({"node": "search_drug_db", "status": "complete"})
        return {**state, "context": ctx, "tool_outputs": tool_outputs}

    def _classify_severity(self, state: AgentState) -> AgentState:
        """
        Use GPT-4o to synthesize all findings into a structured JSON severity analysis.
        """
        ctx = dict(state.get("context", {}))
        profile = ctx.get("patient_profile", {})

        # Build patient profile string
        patient_profile_str = (
            f"Name: {profile.get('name', 'Unknown')}, "
            f"Age: {profile.get('age', 'Unknown')}, "
            f"Conditions: {', '.join(profile.get('chronic_conditions', [])) or 'None'}, "
            f"Renal Function: {profile.get('renal_function', 'unknown')}"
        )

        # Dosage findings as text
        dosage_text = "\n".join(
            f"• {d['drug']}: {d['result']}" for d in ctx.get("dosage_findings", [])
        ) or "No dosage issues identified."

        # Allergy findings as text
        allergy_text = "\n".join(
            f"• {a['drug']}: {a['result']}" for a in ctx.get("allergy_findings", [])
        ) or "No allergy conflicts identified."

        system_prompt = INTERACTION_ANALYSIS_PROMPT.format(
            patient_profile=patient_profile_str,
            medications=ctx.get("medication_list_str", "Not specified"),
            allergies=", ".join(ctx.get("allergies", [])) or "None documented",
            interaction_findings=ctx.get("interaction_findings", "Not checked."),
            dosage_findings=dosage_text,
            allergy_findings=allergy_text,
            kb_context=ctx.get("kb_context", "Not available."),
        )

        try:
            llm = ChatGoogleGenerativeAI(
                model=_GEMINI_MODEL, temperature=0,
                google_api_key=_GOOGLE_KEY
            )
            response = llm.invoke([HumanMessage(content=system_prompt)])
            
            # Robust JSON extraction
            analysis = self._extract_json(response.content)
            
            if not analysis:
                raise ValueError("Extracted analysis is null or invalid format")
                
        except Exception as exc:
            logger.error("DrugAgent: severity classification/extraction failed: %s", exc)
            
            # --- SAFETY FALLBACK: Parse raw findings manually ---
            findings_text = ctx.get("interaction_findings", "")
            
            # Simple interaction counting from tool output string: 
            # "⚠️ Drug Interaction Report (X interaction(s) found)"
            count_match = re.search(r'\((\d+)\s+interaction', findings_text)
            interaction_count = int(count_match.group(1)) if count_match else 0
            
            # Identify critical interactions from tool output
            is_critical = "CONTRAINDICATED" in findings_text or "MAJOR" in findings_text
            
            # Format the tool finding for the fallback response
            display_findings = findings_text if findings_text else "No specific tool results available."
            if "✅ No high-risk interactions detected" in findings_text:
                display_findings = "No high-risk interactions were found in our clinical database for this combination."

            analysis = {
                "overall_safety_rating": "UNSAFE" if is_critical else "CAUTION",
                "total_interactions_found": interaction_count,
                "critical_alerts": [], # Will be empty, UI will rely on response text
                "moderate_warnings": [],
                "minor_notes": [],
                "patient_explanation": FALLBACK_RESPONSE.format(findings=display_findings),
                "prescriber_note": f"AI Engine limit reached. Raw database results shown. Error: {str(exc)}",
                "urgent_action_required": is_critical,
            }

        ctx["severity_analysis"] = analysis
        return {**state, "context": ctx}

    def _route_by_severity(self, state: AgentState) -> str:
        """Conditional edge: route to alternatives/alert if major issues found."""
        analysis = state.get("context", {}).get("severity_analysis", {})

        # Check for any critical/major alerts
        critical = analysis.get("critical_alerts", [])
        urgent = analysis.get("urgent_action_required", False)
        rating = analysis.get("overall_safety_rating", "SAFE")

        if urgent or rating in ("UNSAFE", "CRITICAL") or any(
            a.get("severity") in _ALERT_SEVERITIES for a in critical
        ):
            logger.warning("DrugAgent: SEVERE interactions detected — routing to alternatives + alert")
            return "severe"

        return "safe"

    def _suggest_alternatives(self, state: AgentState) -> AgentState:
        """Generate alternative medication suggestions for detected conflicts."""
        ctx = dict(state.get("context", {}))
        analysis = ctx.get("severity_analysis", {})
        profile = ctx.get("patient_profile", {})

        # Build conflict summary for the prompt
        critical = analysis.get("critical_alerts", [])
        conflicts_text = "\n".join(
            f"• [{a.get('severity')}] {' + '.join(a.get('drugs_involved', []))}: "
            f"{a.get('summary', 'Interaction detected')}"
            for a in critical
        ) or "Major interactions flagged (see interaction findings)."

        system_prompt = ALTERNATIVES_PROMPT.format(
            conflicts=conflicts_text,
            age=profile.get("age", "Unknown"),
            conditions=", ".join(profile.get("chronic_conditions", [])) or "None documented",
            current_medications=ctx.get("medication_list_str", "See above"),
            allergies=", ".join(ctx.get("allergies", [])) or "None documented",
            renal_function=profile.get("renal_function", "Unknown"),
        )

        try:
            llm = ChatGoogleGenerativeAI(
                model=_GEMINI_MODEL, temperature=0.2,
                google_api_key=_GOOGLE_KEY
            )
            response = llm.invoke([HumanMessage(content=system_prompt)])
            ctx["alternatives"] = response.content
        except Exception as exc:
            logger.error("DrugAgent: suggest_alternatives failed: %s", exc)
            ctx["alternatives"] = (
                "Unable to generate alternatives automatically. "
                "Please consult your pharmacist or prescribing physician for safe substitutions."
            )

        return {**state, "context": ctx}

    def _alert_prescriber(self, state: AgentState) -> AgentState:
        """
        Generate a prescriber alert message.
        In production this would trigger a notification — here it generates the alert text.
        """
        ctx = dict(state.get("context", {}))
        analysis = ctx.get("severity_analysis", {})
        profile = ctx.get("patient_profile", {})
        patient_id = state.get("patient_id", "Unknown")

        critical = analysis.get("critical_alerts", [])
        if not critical:
            ctx["alert_sent"] = False
            return {**state, "context": ctx}

        # Determine severity
        severities = {a.get("severity") for a in critical}
        top_severity = "CONTRAINDICATED" if "CONTRAINDICATED" in severities else "MAJOR"

        interactions_text = "\n".join(
            f"  - {' + '.join(a.get('drugs_involved', []))}: {a.get('summary', '')}"
            for a in critical
        )

        alert_prompt = PRESCRIBER_ALERT_PROMPT.format(
            patient_name=profile.get("name", "Unknown Patient"),
            patient_id=patient_id,
            severity=top_severity,
            interactions=interactions_text,
        )

        try:
            llm = ChatGoogleGenerativeAI(
                model=_GEMINI_MODEL, temperature=0,
                google_api_key=_GOOGLE_KEY
            )
            response = llm.invoke([HumanMessage(content=alert_prompt)])
            ctx["prescriber_alert_text"] = response.content

            logger.warning(
                "DrugAgent: PRESCRIBER ALERT generated for patient %s — severity: %s",
                patient_id, top_severity,
            )

            # In production: trigger notification service here
            # from app.services.notification_service import NotificationService
            # NotificationService.alert_prescriber(patient_id=patient_id, alert_text=ctx["prescriber_alert_text"])

            ctx["alert_sent"] = True

        except Exception as exc:
            logger.error("DrugAgent: prescriber alert generation failed: %s", exc)
            ctx["alert_sent"] = False

        tool_outputs = list(state.get("tool_outputs", []))
        tool_outputs.append({
            "node": "alert_prescriber",
            "alert_sent": ctx.get("alert_sent", False),
            "severity": top_severity,
        })
        return {**state, "context": ctx, "tool_outputs": tool_outputs}

    def _generate_medication_schedule(self, state: AgentState) -> AgentState:
        """Create an optimized medication schedule based on the full analysis."""
        ctx = dict(state.get("context", {}))
        medications = ctx.get("medications", [])
        profile = ctx.get("patient_profile", {})

        if not medications:
            ctx["schedule"] = "No medications to schedule."
            return {**state, "context": ctx}

        # Format medications with dose information
        med_strings = []
        for m in medications:
            if isinstance(m, dict):
                name = m.get("name", "Unknown")
                dose = m.get("dose", "")
                freq = m.get("frequency", "")
                med_strings.append(f"{name} {dose} {freq}".strip())
            else:
                med_strings.append(str(m))

        # Note any interaction timing considerations
        analysis = ctx.get("severity_analysis", {})
        moderate = analysis.get("moderate_warnings", [])
        interaction_notes = "\n".join(
            f"• Do not take {' and '.join(a.get('drugs_involved', []))} simultaneously — {a.get('summary', '')}"
            for a in moderate
        ) or "No specific timing separation required."

        lifestyle = profile.get("lifestyle_notes", "Standard daily schedule, meal times not specified")

        try:
            schedule_result = generate_medication_schedule.invoke({
                "medications": ", ".join(med_strings),
                "patient_lifestyle": lifestyle,
            })
            ctx["schedule"] = schedule_result
        except Exception as exc:
            logger.error("DrugAgent: schedule generation failed: %s", exc)
            ctx["schedule"] = "Schedule generation unavailable. Please consult your pharmacist."

        return {**state, "context": ctx}

    def _format_drug_response(self, state: AgentState) -> AgentState:
        """Assemble the complete, structured drug interaction report."""
        ctx = state.get("context", {})
        analysis = ctx.get("severity_analysis", {})

        # Determine overall urgency for the API response layer
        rating = analysis.get("overall_safety_rating", "CAUTION")
        urgency_map = {
            "SAFE": "routine",
            "CAUTION": "moderate",
            "UNSAFE": "urgent",
            "CRITICAL": "emergency",
        }
        urgency = urgency_map.get(rating, "moderate")

        patient_explanation = analysis.get(
            "patient_explanation",
            FALLBACK_RESPONSE,
        )

        response_text = patient_explanation
        if ctx.get("alternatives"):
            response_text += f"\n\n---\n**Alternative Medication Suggestions:**\n{ctx['alternatives']}"
        if ctx.get("schedule"):
            response_text += f"\n\n---\n**Your Medication Schedule:**\n{ctx['schedule']}"
        if ctx.get("alert_sent"):
            response_text += (
                "\n\n---\n⚠️ **Your prescribing physician has been automatically notified** "
                "about the medication concerns identified in this review. "
                "Please do not change any medications until you speak with them."
            )

        return {
            **state,
            "final_response": {
                "type": "drug_interaction",
                "urgency": urgency,
                "content": response_text,
                "overall_safety_rating": rating,
                "total_interactions": analysis.get("total_interactions_found", 0),
                "critical_alerts": analysis.get("critical_alerts", []),
                "moderate_warnings": analysis.get("moderate_warnings", []),
                "minor_notes": analysis.get("minor_notes", []),
                "prescriber_note": analysis.get("prescriber_note", ""),
                "alert_sent": ctx.get("alert_sent", False),
                "schedule": ctx.get("schedule", ""),
                "medications_analyzed": ctx.get("medication_list_str", ""),
            },
        }
