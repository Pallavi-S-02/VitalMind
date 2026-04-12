"""
symptom_analyst.py — VitalMind Symptom Analyst Agent (LangGraph)

Multi-turn symptom interview with OPQRST framework → differential diagnosis.

Graph topology:
  START
    │
    ▼
  check_urgency           ← Immediate rule-based emergency scan (no LLM)
    │
    ├─ EMERGENCY ──────→ emergency_response → END
    │
    ▼
  query_patient_history   ← Load allergies, meds, conditions from Redis/DB
    │
    ▼
  [state-based routing]
    │
    ├─ first_turn ──────→ gather_initial_symptoms → END (return question)
    │
    └─ followup ────────┬→ ask_followup_questions (turns 2-5) → END
                        │
                        └→ search_medical_kb         (turn 6+)
                              │
                              ▼
                           generate_differential
                              │
                              ▼
                           recommend_specialist
                              │
                              ▼
                           finalize_response → END
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI

_GEMINI_MODEL = "gemini-3.1-pro-preview"
_GOOGLE_KEY = __import__("os").getenv("GOOGLE_API_KEY")
from langgraph.graph import StateGraph, END, START

from app.agents.base_agent import BaseAgent, AgentState, extract_llm_text
from app.agents.tools.medical_kb import search_medical_knowledge_base
from app.agents.tools.patient_history import get_patient_history
from app.agents.tools.urgency_scoring import calculate_urgency_score, score_symptoms
from app.agents.prompts.symptom_prompts import (
    INITIAL_INTAKE_PROMPT,
    FOLLOWUP_QUESTION_PROMPT,
    DIFFERENTIAL_DIAGNOSIS_PROMPT,
    get_specialist_for_condition,
)

logger = logging.getLogger(__name__)

_MAX_FOLLOWUP_TURNS = 5  # After this many user turns, generate differential
_MIN_FOLLOWUP_TURNS = 2  # Minimum turns before differential is allowed


class SymptomAnalystAgent(BaseAgent):
    """
    Multi-turn symptom interview + differential diagnosis agent.

    State contract (extends AgentState):
      context["turn_count"]        : int  — number of patient message turns
      context["patient_history"]   : str  — loaded patient profile text
      context["symptoms_summary"]  : str  — accumulated symptom描述
      context["opqrst_covered"]    : list — OPQRST aspects explored
      context["urgency_result"]    : dict — from urgency scoring tool
      context["differential"]      : dict — final differential JSON
    """

    def get_tools(self) -> list:
        return [
            search_medical_knowledge_base,
            get_patient_history,
            calculate_urgency_score,
        ]

    def build_graph(self) -> StateGraph:
        graph = StateGraph(AgentState)

        graph.add_node("check_urgency", self._check_urgency)
        graph.add_node("query_patient_history", self._query_patient_history)
        graph.add_node("gather_initial_symptoms", self._gather_initial_symptoms)
        graph.add_node("ask_followup_questions", self._ask_followup_questions)
        graph.add_node("search_medical_kb", self._search_medical_kb)
        graph.add_node("generate_differential", self._generate_differential)
        graph.add_node("recommend_specialist", self._recommend_specialist)
        graph.add_node("emergency_response", self._emergency_response)
        graph.add_node("finalize_response", self._finalize_response)

        # Entry
        graph.add_edge(START, "check_urgency")

        # Emergency short-circuit
        graph.add_conditional_edges(
            "check_urgency",
            self._route_after_urgency_check,
            {
                "emergency": "emergency_response",
                "continue": "query_patient_history",
            },
        )

        graph.add_edge("emergency_response", END)

        # Normal flow
        graph.add_edge("query_patient_history", "__route_turn__")
        graph.add_node("__route_turn__", lambda s: s)  # passthrough routing node
        graph.add_conditional_edges(
            "__route_turn__",
            self._route_by_turn_count,
            {
                "initial": "gather_initial_symptoms",
                "followup": "ask_followup_questions",
                "diagnose": "search_medical_kb",
            },
        )

        graph.add_edge("gather_initial_symptoms", END)
        graph.add_edge("ask_followup_questions", END)
        graph.add_edge("search_medical_kb", "generate_differential")
        graph.add_edge("generate_differential", "recommend_specialist")
        graph.add_edge("recommend_specialist", "finalize_response")
        graph.add_edge("finalize_response", END)

        return graph

    # ─────────────────────────────────────────────────────────────────
    # Node implementations
    # ─────────────────────────────────────────────────────────────────

    def _check_urgency(self, state: AgentState) -> AgentState:
        """Immediately scan the latest patient message for emergency keywords."""
        messages = state.get("messages", [])
        patient_input = ""
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                patient_input = m.content
                break

        if not patient_input:
            return state

        result = score_symptoms(patient_input)
        context = dict(state.get("context", {}))
        context["urgency_result"] = result.to_dict()

        return {**state, "context": context}

    def _route_after_urgency_check(self, state: AgentState) -> str:
        urgency = state.get("context", {}).get("urgency_result", {})
        if urgency.get("urgency_level") == "emergency":
            return "emergency"
        return "continue"

    def _emergency_response(self, state: AgentState) -> AgentState:
        """
        Emergency branch: delegate to the TriageAgent for structured ESI evaluation.
        Falls back to a direct LLM call if the TriageAgent is unavailable.
        """
        urgency = state.get("context", {}).get("urgency_result", {})
        triggers = ", ".join(urgency.get("triggers", []))
        messages = state.get("messages", [])
        last_msg = messages[-1].content if messages else ""

        # ── Primary: delegate to TriageAgent for full ESI evaluation ────
        try:
            from app.agents.triage_agent import run_triage
            patient_id = state.get("patient_id")
            patient_context = state.get("context", {}).get("patient", {})
            vital_signs = state.get("context", {}).get("vital_signs", {})

            triage_result = run_triage(
                chief_complaint=last_msg,
                patient_id=patient_id,
                vital_signs=vital_signs,
                patient_context=patient_context,
                session_id=state.get("session_id"),
            )

            if triage_result and triage_result.get("content"):
                return {
                    **state,
                    "final_response": {
                        "type": "symptom_check",
                        "urgency": triage_result.get("urgency", "emergency"),
                        "content": triage_result.get("content", ""),
                        "phase": "emergency_triage",
                        "esi_level": triage_result.get("esi_level"),
                        "esi_label": triage_result.get("esi_label"),
                        "triage_id": triage_result.get("triage_id"),
                        "alert_dispatched": triage_result.get("alert_dispatched", False),
                        "immediate_actions": triage_result.get("immediate_actions", []),
                        "disposition": triage_result.get("disposition", ""),
                    },
                }
        except Exception as exc:
            logger.error("SymptomAnalyst: TriageAgent delegation failed: %s — using direct LLM", exc)

        # ── Fallback: direct LLM triage prompt ──────────────────────────
        from app.agents.prompts.system_prompts import PROMPTS
        try:
            llm = ChatGoogleGenerativeAI(
                model=_GEMINI_MODEL, temperature=0,
                google_api_key=_GOOGLE_KEY
            )
            resp = llm.invoke([
                SystemMessage(content=PROMPTS["triage"]),
                HumanMessage(content=f"Triggered by: {triggers}\n\nPatient said: {last_msg}"),
            ])
            response_text = resp.content
        except Exception as exc:
            logger.error("Emergency response LLM failed: %s", exc)
            response_text = (
                "⚠️ EMERGENCY: Based on your symptoms, please call 911 immediately "
                "or have someone take you to the nearest emergency room RIGHT NOW. "
                "Do not wait. Your safety is the priority."
            )

        return {
            **state,
            "final_response": {
                "type": "symptom_check",
                "urgency": "emergency",
                "content": response_text,
                "phase": "emergency_triage",
            },
        }


    def _query_patient_history(self, state: AgentState) -> AgentState:
        """Load patient history if not already in context."""
        context = dict(state.get("context", {}))
        patient_id = state.get("patient_id")

        if "patient_history" not in context and patient_id:
            history_text = get_patient_history.invoke({"patient_id": patient_id})
            context["patient_history"] = history_text
        elif "patient_history" not in context:
            context["patient_history"] = "No patient history available."

        return {**state, "context": context}

    def _route_by_turn_count(self, state: AgentState) -> str:
        context = state.get("context", {})
        turn_count = int(context.get("turn_count", 0))

        if turn_count == 0:
            return "initial"
        elif turn_count < _MAX_FOLLOWUP_TURNS:
            return "followup"
        else:
            return "diagnose"

    def _gather_initial_symptoms(self, state: AgentState) -> AgentState:
        """First turn: ask an open-ended initial question."""
        ctx = state.get("context", {})
        patient = ctx.get("patient", {})

        system_prompt = INITIAL_INTAKE_PROMPT.format(
            patient_name=patient.get("name", "there"),
            chronic_conditions=", ".join(patient.get("chronic_conditions", [])) or "None",
            current_medications=", ".join(
                [m.get("name", str(m)) if isinstance(m, dict) else str(m)
                 for m in patient.get("current_medications", [])]
            ) or "None",
            allergies=", ".join(patient.get("allergies", [])) or "None known",
            language=ctx.get("language", "English"),
        )

        messages = state.get("messages", [])
        try:
            llm = ChatGoogleGenerativeAI(
                model=_GEMINI_MODEL, temperature=0.3,
                google_api_key=_GOOGLE_KEY
            )
            response = llm.invoke([SystemMessage(content=system_prompt), *messages])
            response_text = response.content
        except Exception as exc:
            logger.error("gather_initial_symptoms failed: %s", exc)
            response_text = "I'm here to help. Could you tell me what's been bothering you today?"

        new_ctx = {**ctx, "turn_count": 1, "opqrst_covered": []}
        return {
            **state,
            "context": new_ctx,
            "final_response": {
                "type": "symptom_check",
                "urgency": "routine",
                "content": response_text,
                "phase": "initial_intake",
                "turn": 1,
            },
        }

    def _ask_followup_questions(self, state: AgentState) -> AgentState:
        """Turns 2-N: generate targeted OPQRST follow-up questions."""
        ctx = dict(state.get("context", {}))
        turn_count = int(ctx.get("turn_count", 1))
        opqrst_covered = ctx.get("opqrst_covered", [])

        # Build symptoms summary from conversation
        messages = state.get("messages", [])
        user_turns = [m.content for m in messages if isinstance(m, HumanMessage)]
        symptoms_so_far = "\n".join(f"Turn {i+1}: {t}" for i, t in enumerate(user_turns))

        system_prompt = FOLLOWUP_QUESTION_PROMPT.format(
            symptoms_reported=symptoms_so_far,
            opqrst_covered=", ".join(opqrst_covered) if opqrst_covered else "None yet",
            question_number=turn_count,
            language=ctx.get("language", "English"),
        )

        try:
            llm = ChatGoogleGenerativeAI(
                model=_GEMINI_MODEL, temperature=0.3,
                google_api_key=_GOOGLE_KEY
            )
            response = llm.invoke([SystemMessage(content=system_prompt), *messages])
            response_text = response.content
        except Exception as exc:
            logger.error("ask_followup_questions failed: %s", exc)
            response_text = "Could you describe how severe your symptoms are on a scale of 1 to 10?"

        ctx["turn_count"] = turn_count + 1
        ctx["symptoms_summary"] = symptoms_so_far

        return {
            **state,
            "context": ctx,
            "final_response": {
                "type": "symptom_check",
                "urgency": ctx.get("urgency_result", {}).get("urgency_level", "routine"),
                "content": response_text,
                "phase": "followup_interview",
                "turn": turn_count + 1,
            },
        }

    def _search_medical_kb(self, state: AgentState) -> AgentState:
        """Search Pinecone for relevant clinical knowledge based on accumulated symptoms."""
        ctx = dict(state.get("context", {}))
        messages = state.get("messages", [])
        user_content = " ".join(
            m.content for m in messages if isinstance(m, HumanMessage)
        )

        kb_results = search_medical_knowledge_base.invoke({
            "query": user_content[:500],
            "namespace": "symptoms",
            "top_k": 4,
        })
        ctx["kb_context"] = kb_results

        tool_outputs = list(state.get("tool_outputs", []))
        tool_outputs.append({"node": "search_medical_kb", "results_length": len(kb_results)})

        return {**state, "context": ctx, "tool_outputs": tool_outputs}

    def _generate_differential(self, state: AgentState) -> AgentState:
        """Generate structured differential diagnosis using all gathered context."""
        ctx = state.get("context", {})
        patient = ctx.get("patient", {})
        messages = state.get("messages", [])
        user_turns = [m.content for m in messages if isinstance(m, HumanMessage)]

        patient_summary = (
            f"Name: {patient.get('name', 'Unknown')}, "
            f"Conditions: {', '.join(patient.get('chronic_conditions', [])) or 'None'}, "
            f"Medications: {', '.join([m.get('name', str(m)) if isinstance(m, dict) else str(m) for m in patient.get('current_medications', [])]) or 'None'}, "
            f"Allergies: {', '.join(patient.get('allergies', [])) or 'None'}"
        )

        urgency = ctx.get("urgency_result", {})
        urgency_text = (
            f"Level: {urgency.get('urgency_level', 'routine')}\n"
            f"Triggers: {', '.join(urgency.get('triggers', [])) or 'None'}"
        )

        system_prompt = DIFFERENTIAL_DIAGNOSIS_PROMPT.format(
            patient_summary=patient_summary,
            symptom_summary="\n".join(f"- {t}" for t in user_turns),
            kb_context=ctx.get("kb_context", "No knowledge base results available."),
            urgency_assessment=urgency_text,
            language=ctx.get("language", "English"),
        )

        try:
            llm = ChatGoogleGenerativeAI(
                model=_GEMINI_MODEL, temperature=0,
                google_api_key=_GOOGLE_KEY
            )
            response = llm.invoke([HumanMessage(content=system_prompt)])
            differential = json.loads(extract_llm_text(response))
        except json.JSONDecodeError:
            differential = {
                "primary_diagnosis": {"condition": "Unable to determine", "probability": "unknown"},
                "differential": [],
                "urgency": "routine",
                "patient_explanation": "I was unable to generate a structured differential at this time.",
                "next_steps": "Please consult a healthcare professional.",
            }
        except Exception as exc:
            logger.error("generate_differential failed: %s", exc)
            differential = {"error": str(exc)}

        ctx_updated = {**ctx, "differential": differential}
        return {**state, "context": ctx_updated}

    def _recommend_specialist(self, state: AgentState) -> AgentState:
        """Map primary diagnosis to appropriate specialist."""
        ctx = dict(state.get("context", {}))
        differential = ctx.get("differential", {})
        primary = differential.get("primary_diagnosis", {})
        condition = primary.get("condition", "general")
        specialist = get_specialist_for_condition(condition)
        ctx["recommended_specialist"] = specialist
        return {**state, "context": ctx}

    def _finalize_response(self, state: AgentState) -> AgentState:
        """Assemble the complete patient-facing response."""
        ctx = state.get("context", {})
        differential = ctx.get("differential", {})

        patient_explanation = differential.get(
            "patient_explanation",
            "Based on your symptoms, I've prepared a preliminary assessment."
        )
        next_steps = differential.get("next_steps", "Please consult your healthcare provider.")
        specialist = ctx.get("recommended_specialist", "General Practitioner")
        urgency = differential.get("urgency", "routine")

        response_text = (
            f"{patient_explanation}\n\n"
            f"**Recommended Next Steps:** {next_steps}\n\n"
            f"**Suggested Specialist:** {specialist}"
        )

        return {
            **state,
            "final_response": {
                "type": "symptom_check",
                "urgency": urgency,
                "content": response_text,
                "phase": "differential_complete",
                "differential": differential,
                "specialist": specialist,
            },
        }
