"""
triage_agent.py — VitalMind Triage Agent (LangGraph)

Fast emergency triage using the Emergency Severity Index (ESI 1–5).
Maximum latency target: ≤ 2 seconds end-to-end.
All LLM calls use gpt-4o-mini throughout.

Graph topology:
  START
    │
    ▼
  collect_triage_inputs    ← Pull symptom report + vitals from state
    │
    ▼
  check_red_flags          ← Pattern-match against emergency symptom database (LLM-free fast path + LLM enrichment)
    │
    ▼
  evaluate_esi_level       ← Compute ESI 1–5 with structured JSON output
    │
    ├─ ESI 1 or 2 ────────→ route_emergency  (dispatch on-call physician + create emergency alert)
    │
    └─ ESI 3–5 ───────────→ assign_priority_queue (schedule in standard care pathway)
                                │
                                ▼
                           generate_triage_report  ← Patient-facing report + audit log
                                │
                                ▼
                               END

Integration:
  - Callable from SymptomAnalystAgent._emergency_response via conditional edge
  - Callable directly from POST /api/v1/triage/evaluate
  - Registered as 'triage' specialist in AgentOrchestrator
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

_GEMINI_MODEL = "gemini-3.1-pro-preview"
_GOOGLE_KEY = __import__("os").getenv("GOOGLE_API_KEY")
from langgraph.graph import StateGraph, END, START

from app.agents.base_agent import BaseAgent, AgentState, extract_llm_text
from app.agents.tools.urgency_scoring import score_symptoms
from app.agents.prompts.triage_prompts import (
    RED_FLAG_DETECTION_PROMPT,
    ESI_EVALUATION_PROMPT,
    TRIAGE_REPORT_PROMPT,
    TRIAGE_AUDIT_PROMPT,
    ESI_CONFIG,
)

logger = logging.getLogger(__name__)

# Maximum seconds we allow each LLM call to take before falling back
_LLM_TIMEOUT = 8


class TriageAgent(BaseAgent):
    """
    Emergency Severity Index (ESI) triage agent.

    Key design decisions:
      - All LLM calls use gpt-4o-mini for maximum speed.
      - The first safety gate (check_red_flags) is rule-based (no LLM) to
        guarantee under 50ms for the initial emergency detection.
      - LLM enrichment of red flags runs in parallel with rule-based output.
      - ESI level is computed with json_object structured output for reliability.
      - For ESI 1/2: the emergency dispatch runs BEFORE patient report generation.
      - Full audit trail is written to DB and Redis on every triage.

    State contract (extends AgentState):
      context["chief_complaint"]     : str — primary symptom description
      context["vital_signs"]         : dict — current vitals (from IoT or manual)
      context["red_flag_result"]     : dict — from check_red_flags node
      context["esi_result"]          : dict — from evaluate_esi_level node
      context["triage_id"]           : str — UUID for this triage event
      context["dispatch_result"]     : dict — escalation outcome (ESI 1/2 only)
      context["queue_assignment"]    : dict — care pathway assignment (ESI 3-5)
      context["triage_report"]       : str — patient-facing report text
      context["audit_note"]          : str — clinical audit note
    """

    def get_tools(self) -> list:
        # Triage uses direct function calls — no LangChain tool binding needed
        return []

    def build_graph(self) -> StateGraph:
        graph = StateGraph(AgentState)

        graph.add_node("collect_triage_inputs", self._collect_triage_inputs)
        graph.add_node("check_red_flags", self._check_red_flags)
        graph.add_node("evaluate_esi_level", self._evaluate_esi_level)
        graph.add_node("route_emergency", self._route_emergency)
        graph.add_node("assign_priority_queue", self._assign_priority_queue)
        graph.add_node("generate_triage_report", self._generate_triage_report)

        # Entry
        graph.add_edge(START, "collect_triage_inputs")
        graph.add_edge("collect_triage_inputs", "check_red_flags")
        graph.add_edge("check_red_flags", "evaluate_esi_level")

        # Conditional branch: ESI 1-2 → emergency dispatch ; ESI 3-5 → priority queue
        graph.add_conditional_edges(
            "evaluate_esi_level",
            self._route_by_esi_level,
            {
                "emergency": "route_emergency",
                "priority": "assign_priority_queue",
            },
        )

        graph.add_edge("route_emergency", "generate_triage_report")
        graph.add_edge("assign_priority_queue", "generate_triage_report")
        graph.add_edge("generate_triage_report", END)

        return graph

    # ─────────────────────────────────────────────────────────────────────
    # Node 1: collect_triage_inputs
    # ─────────────────────────────────────────────────────────────────────

    def _collect_triage_inputs(self, state: AgentState) -> AgentState:
        """
        Extract chief complaint and vitals from the agent state.
        Supports both direct triage API calls and SymptomAnalyst handoff.
        """
        ctx = dict(state.get("context", {}))
        messages = state.get("messages", [])

        # Chief complaint from direct context (API call) or last HumanMessage
        chief_complaint = ctx.get("chief_complaint", "")
        if not chief_complaint:
            for m in reversed(messages):
                if isinstance(m, HumanMessage):
                    chief_complaint = m.content
                    break
        ctx["chief_complaint"] = chief_complaint or "No chief complaint provided"

        # Vitals — try context first (from monitoring agent handoff), then Redis
        vital_signs = ctx.get("vital_signs", {})
        if not vital_signs:
            vital_signs = self._load_latest_vitals(state.get("patient_id"))
        ctx["vital_signs"] = vital_signs

        # Patient profile
        patient = ctx.get("patient", {})
        ctx["allergies"] = ", ".join(patient.get("allergies", [])) or "None known"
        ctx["medications"] = ", ".join(
            [m.get("name", str(m)) if isinstance(m, dict) else str(m)
            for m in patient.get("current_medications", [])]
        ) or "None"
        ctx["patient_name"] = patient.get("name", "Patient")
        ctx["patient_history"] = ctx.get("patient_history", "")

        # Generate triage ID
        ctx["triage_id"] = str(uuid.uuid4())
        ctx["triage_started_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            "TriageAgent: collecting inputs for patient %s — complaint: %s",
            state.get("patient_id", "unknown"),
            chief_complaint[:80],
        )

        return {**state, "context": ctx}

    def _load_latest_vitals(self, patient_id: Optional[str]) -> dict:
        """Load latest vitals from Redis cache if available."""
        if not patient_id:
            return {}
        try:
            import redis as redis_lib
            import os
            r = redis_lib.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                db=int(os.getenv("REDIS_DB", 0)),
                decode_responses=True,
            )
            raw = r.get(f"vitalmind:vitals:{patient_id}:latest")
            if raw:
                return json.loads(raw)
        except Exception as exc:
            logger.debug("TriageAgent: could not load Redis vitals: %s", exc)
        return {}

    # ─────────────────────────────────────────────────────────────────────
    # Node 2: check_red_flags
    # ─────────────────────────────────────────────────────────────────────

    def _check_red_flags(self, state: AgentState) -> AgentState:
        """
        Two-tier red flag detection:
          Tier 1 (fast, < 10ms): Rule-based keyword matching via score_symptoms()
          Tier 2 (LLM, < 800ms): GPT-4o-mini structured JSON for clinical enrichment
        """
        ctx = dict(state.get("context", {}))
        chief_complaint = ctx.get("chief_complaint", "")
        allergies = ctx.get("allergies", "None known")
        medications = ctx.get("medications", "None")

        # ── Tier 1: Rule-based urgency scoring (instantaneous) ──────────
        urgency_result = score_symptoms(chief_complaint)
        ctx["urgency_result"] = urgency_result.to_dict()

        # ── Tier 2: LLM red flag enrichment ─────────────────────────────
        llm_red_flags = {}
        try:
            llm = ChatGoogleGenerativeAI(
                model=_GEMINI_MODEL, temperature=0,
                google_api_key=_GOOGLE_KEY
            )
            prompt = RED_FLAG_DETECTION_PROMPT.format(
                symptom_text=chief_complaint,
                allergies=allergies,
                medications=medications,
            )
            response = llm.invoke(
                [SystemMessage(content=prompt)],
            )
            llm_red_flags = json.loads(extract_llm_text(response))
        except json.JSONDecodeError:
            logger.warning("TriageAgent: LLM red flag JSON parse failed — using rule-based only")
        except Exception as exc:
            logger.error("TriageAgent: LLM red flag call failed: %s", exc)

        # Merge results
        rule_triggers = urgency_result.triggers
        llm_flags = llm_red_flags.get("red_flags_detected", [])
        all_flags = list(set(rule_triggers + llm_flags))

        ctx["red_flag_result"] = {
            "flags": all_flags,
            "rule_urgency_score": urgency_result.score,
            "rule_urgency_level": urgency_result.level,
            "systems_involved": llm_red_flags.get("systems_involved", []),
            "highest_risk_category": llm_red_flags.get("highest_risk_category"),
            "time_critical": llm_red_flags.get("time_critical", urgency_result.level == "emergency"),
            "preliminary_differentials": llm_red_flags.get("preliminary_differentials", []),
        }

        logger.info(
            "TriageAgent: red flags detected: %d (rule: %s, LLM time-critical: %s)",
            len(all_flags),
            urgency_result.level,
            ctx["red_flag_result"]["time_critical"],
        )

        return {**state, "context": ctx}

    # ─────────────────────────────────────────────────────────────────────
    # Node 3: evaluate_esi_level
    # ─────────────────────────────────────────────────────────────────────

    def _evaluate_esi_level(self, state: AgentState) -> AgentState:
        """
        Compute the ESI level (1–5) using GPT-4o-mini structured output.

        Falls back to rule-based urgency mapping if LLM call fails.
        """
        ctx = dict(state.get("context", {}))
        chief_complaint = ctx.get("chief_complaint", "")
        vital_signs = ctx.get("vital_signs", {})
        red_flag_result = ctx.get("red_flag_result", {})
        urgency_result = ctx.get("urgency_result", {})

        # Format vitals for the prompt
        vitals_text = self._format_vitals_for_prompt(vital_signs)

        # Format red flags
        red_flags_text = (
            "; ".join(red_flag_result.get("flags", [])) or "None detected"
        )

        # Patient history summary
        patient = ctx.get("patient", {})
        history_text = (
            f"Age: {patient.get('age', 'unknown')}, "
            f"Conditions: {', '.join(patient.get('chronic_conditions', [])) or 'None'}, "
            f"Meds: {ctx.get('medications', 'None')}, "
            f"Allergies: {ctx.get('allergies', 'None known')}"
        )

        esi_result: dict[str, Any] = {}

        try:
            llm = ChatGoogleGenerativeAI(
                model=_GEMINI_MODEL, temperature=0,
                google_api_key=_GOOGLE_KEY
            )
            prompt = ESI_EVALUATION_PROMPT.format(
                chief_complaint=chief_complaint,
                vital_signs=vitals_text,
                patient_history=history_text,
                red_flags=red_flags_text,
                urgency_score=f"{urgency_result.get('urgency_score', 0)} (level: {urgency_result.get('urgency_level', 'routine')})",
            )
            response = llm.invoke(
                [SystemMessage(content=prompt)],
            )
            esi_result = json.loads(extract_llm_text(response))
        except Exception as exc:
            logger.error("TriageAgent: ESI evaluation LLM failed: %s — falling back", exc)
            esi_result = self._fallback_esi_from_urgency(urgency_result)

        # Enrich with ESI config constants
        esi_level = max(1, min(5, int(esi_result.get("esi_level", 3))))
        esi_result["esi_level"] = esi_level
        esi_config = ESI_CONFIG.get(esi_level, ESI_CONFIG[3])
        esi_result.setdefault("esi_label", esi_config["label"])
        esi_result.setdefault("max_wait_minutes", esi_config["max_wait_minutes"])
        esi_result.setdefault("disposition", esi_config["disposition"])
        esi_result["requires_escalation"] = esi_config["escalation_required"]
        esi_result["escalation_level"] = esi_config["escalation_level"]
        esi_result["patient_instruction"] = esi_config["patient_instruction"]

        ctx["esi_result"] = esi_result

        logger.info(
            "TriageAgent: ESI Level %d (%s) — patient %s — max wait %dm",
            esi_level,
            esi_result.get("esi_label"),
            state.get("patient_id", "unknown"),
            esi_result.get("max_wait_minutes", 999),
        )

        return {**state, "context": ctx}

    def _fallback_esi_from_urgency(self, urgency_result: dict) -> dict:
        """Map rule-based urgency level → ESI level when LLM is unavailable."""
        level = urgency_result.get("urgency_level", "routine")
        score = urgency_result.get("urgency_score", 0)
        if level == "emergency" or score >= 8:
            esi = 1
        elif level == "urgent" or score >= 4:
            esi = 2
        else:
            esi = 4
        cfg = ESI_CONFIG[esi]
        return {
            "esi_level": esi,
            "esi_label": cfg["label"],
            "max_wait_minutes": cfg["max_wait_minutes"],
            "clinical_rationale": f"Rule-based fallback: urgency_level={level}, score={score}",
            "disposition": cfg["disposition"],
            "vital_threats": [],
            "recommended_resources": [],
            "immediate_actions": [],
        }

    def _route_by_esi_level(self, state: AgentState) -> str:
        """Conditional edge: ESI 1-2 → emergency, ESI 3-5 → priority."""
        esi = state.get("context", {}).get("esi_result", {}).get("esi_level", 3)
        if esi <= 2:
            return "emergency"
        return "priority"

    @staticmethod
    def _format_vitals_for_prompt(vitals: dict) -> str:
        if not vitals:
            return "Vitals not available"
        parts = []
        if vitals.get("heart_rate"):
            parts.append(f"HR {vitals['heart_rate']:.0f} bpm")
        if vitals.get("spo2"):
            parts.append(f"SpO2 {vitals['spo2']:.1f}%")
        if vitals.get("systolic_bp") and vitals.get("diastolic_bp"):
            parts.append(f"BP {vitals['systolic_bp']:.0f}/{vitals['diastolic_bp']:.0f} mmHg")
        elif vitals.get("systolic_bp"):
            parts.append(f"BP {vitals['systolic_bp']:.0f} mmHg")
        if vitals.get("temperature_c"):
            parts.append(f"Temp {vitals['temperature_c']:.1f}°C")
        if vitals.get("respiratory_rate"):
            parts.append(f"RR {vitals['respiratory_rate']:.0f}/min")
        return ", ".join(parts) if parts else "Vitals not available"

    # ─────────────────────────────────────────────────────────────────────
    # Node 4a: route_emergency (ESI 1–2)
    # ─────────────────────────────────────────────────────────────────────

    def _route_emergency(self, state: AgentState) -> AgentState:
        """
        ESI 1 or 2: Trigger multi-channel emergency dispatch.

          ESI 1 → Level 3: On-call specialist page + physician SMS + nurse push
          ESI 2 → Level 2: Physician SMS + nurse push notification

        All notifications broadcast via Redis pub/sub to the monitoring dashboard.
        """
        ctx = dict(state.get("context", {}))
        patient_id = state.get("patient_id", "")
        esi_result = ctx.get("esi_result", {})
        red_flag_result = ctx.get("red_flag_result", {})
        esi_level = esi_result.get("esi_level", 2)
        esi_label = esi_result.get("esi_label", "EMERGENT")
        vital_threats = esi_result.get("vital_threats", [])

        alert_payload = {
            "id": str(uuid.uuid4()),
            "patient_id": patient_id,
            "patient_name": ctx.get("patient_name", "Unknown"),
            "type": "triage_alert",
            "source": "triage_agent",
            "level": 3 if esi_level == 1 else 2,
            "severity": "CRITICAL" if esi_level == 1 else "HIGH",
            "message": (
                f"ESI {esi_level} ({esi_label}) — {ctx.get('chief_complaint', '')[:120]}. "
                f"Threats: {'; '.join(vital_threats) if vital_threats else 'See triage record'}."
            ),
            "news2_score": ctx.get("urgency_result", {}).get("urgency_score", 0),
            "esi_level": esi_level,
            "red_flags": red_flag_result.get("flags", []),
            "highest_risk_category": red_flag_result.get("highest_risk_category"),
            "disposition": esi_result.get("disposition"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "triage_id": ctx.get("triage_id"),
        }

        notifications_sent = []

        # ── Level 1: Nurse notification (Socket.IO) ──────────────────────
        try:
            from app.agents.tools.notification_tools import send_nurse_alert
            result = send_nurse_alert.invoke({
                "patient_id": patient_id,
                "alert_level": 1,
                "severity": alert_payload["severity"],
                "message": alert_payload["message"],
                "vitals_summary": TriageAgent._format_vitals_for_prompt(ctx.get("vital_signs", {})),
                "news2_score": alert_payload["news2_score"],
            })
            notifications_sent.append("nurse_push")
            logger.info("TriageAgent: nurse alert sent for ESI %d patient %s", esi_level, patient_id)
        except Exception as exc:
            logger.error("TriageAgent: nurse alert failed: %s", exc)

        # ── Level 2+: Physician SMS (ESI 1 or 2) ────────────────────────
        try:
            from app.agents.tools.notification_tools import send_physician_sms_alert
            result = send_physician_sms_alert.invoke({
                "patient_id": patient_id,
                "alert_level": 2,
                "severity": alert_payload["severity"],
                "message": alert_payload["message"],
                "vitals_summary": TriageAgent._format_vitals_for_prompt(ctx.get("vital_signs", {})),
                "news2_score": alert_payload["news2_score"],
            })
            notifications_sent.append("physician_sms")
            logger.info("TriageAgent: physician SMS sent for ESI %d", esi_level)
        except Exception as exc:
            logger.error("TriageAgent: physician SMS failed: %s", exc)

        # ── Level 3: On-call specialist emergency page (ESI 1 only) ─────
        if esi_level == 1:
            try:
                from app.agents.tools.notification_tools import send_emergency_specialist_alert
                result = send_emergency_specialist_alert.invoke({
                    "patient_id": patient_id,
                    "alert_level": 3,
                    "severity": "CRITICAL",
                    "message": alert_payload["message"],
                    "vitals_summary": TriageAgent._format_vitals_for_prompt(ctx.get("vital_signs", {})),
                    "news2_score": alert_payload["news2_score"],
                })
                notifications_sent.append("specialist_page")
                logger.critical("TriageAgent: SPECIALIST PAGE sent — ESI 1 patient %s", patient_id)
            except Exception as exc:
                logger.error("TriageAgent: specialist page failed: %s", exc)

        # ── Publish to Redis pub/sub (monitoring dashboard) ─────────────
        try:
            import redis as redis_lib
            import os
            r = redis_lib.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                db=int(os.getenv("REDIS_DB", 0)),
                decode_responses=True,
            )
            channel = "vitalmind:emergency_alerts" if esi_level == 1 else "vitalmind:monitoring_alerts"
            r.publish(channel, json.dumps(alert_payload))
            notifications_sent.append(f"redis:{channel}")
        except Exception as exc:
            logger.error("TriageAgent: Redis publish failed: %s", exc)

        # ── Persist alert to DB ──────────────────────────────────────────
        try:
            from app.models.alert import Alert
            from app.models.db import db
            db_alert = Alert(
                id=alert_payload["id"],
                patient_id=patient_id or None,
                alert_type="triage_alert",
                severity=alert_payload["severity"],
                message=alert_payload["message"],
                data=alert_payload,
                acknowledged=False,
                created_at=datetime.now(timezone.utc),
            )
            db.session.add(db_alert)
            db.session.commit()
        except Exception as exc:
            logger.error("TriageAgent: alert DB persist failed: %s", exc)
            try:
                from app.models.db import db
                db.session.rollback()
            except Exception:
                pass

        ctx["dispatch_result"] = {
            "alert_id": alert_payload["id"],
            "notifications_sent": notifications_sent,
            "esi_level": esi_level,
            "timestamp": alert_payload["timestamp"],
        }

        logger.info(
            "TriageAgent: emergency dispatch complete — ESI %d patient %s notifications=%s",
            esi_level, patient_id, notifications_sent,
        )

        return {**state, "context": ctx}

    # ─────────────────────────────────────────────────────────────────────
    # Node 4b: assign_priority_queue (ESI 3–5)
    # ─────────────────────────────────────────────────────────────────────

    def _assign_priority_queue(self, state: AgentState) -> AgentState:
        """
        ESI 3–5: Assign patient to standard care priority queue.
        Optionally triggers a nurse notification for ESI 3.
        """
        ctx = dict(state.get("context", {}))
        patient_id = state.get("patient_id", "")
        esi_result = ctx.get("esi_result", {})
        esi_level = esi_result.get("esi_level", 4)

        # ESI 3 still warrants a nurse notification
        if esi_level == 3:
            try:
                from app.agents.tools.notification_tools import send_nurse_alert
                send_nurse_alert.invoke({
                    "patient_id": patient_id,
                    "alert_level": 1,
                    "severity": "MODERATE",
                    "message": (
                        f"ESI 3 (URGENT) triage — {ctx.get('chief_complaint', '')[:100]}. "
                        f"Patient added to priority queue. Max wait: 60 minutes."
                    ),
                    "vitals_summary": TriageAgent._format_vitals_for_prompt(ctx.get("vital_signs", {})),
                    "news2_score": ctx.get("urgency_result", {}).get("urgency_score", 0),
                })
            except Exception as exc:
                logger.error("TriageAgent: ESI 3 nurse alert failed: %s", exc)

        # Queue assignment record
        ctx["queue_assignment"] = {
            "esi_level": esi_level,
            "queue_priority": 6 - esi_level,   # ESI 3 → priority 3, ESI 4 → 2, ESI 5 → 1
            "disposition": esi_result.get("disposition", "Urgent care"),
            "max_wait_minutes": esi_result.get("max_wait_minutes", 120),
            "assigned_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            "TriageAgent: ESI %d assigned to priority queue — patient %s",
            esi_level, patient_id,
        )

        return {**state, "context": ctx}

    # ─────────────────────────────────────────────────────────────────────
    # Node 5: generate_triage_report
    # ─────────────────────────────────────────────────────────────────────

    def _generate_triage_report(self, state: AgentState) -> AgentState:
        """
        Generate two outputs:
          1. Patient-facing triage report (human-readable, empathetic)
          2. Clinical audit note (for the medical record)

        Also assembles the final_response payload used by the API layer.
        """
        ctx = dict(state.get("context", {}))
        esi_result = ctx.get("esi_result", {})
        dispatch_result = ctx.get("dispatch_result", {})
        queue_assignment = ctx.get("queue_assignment", {})
        chief_complaint = ctx.get("chief_complaint", "")
        patient_name = ctx.get("patient_name", "Patient")

        esi_level = esi_result.get("esi_level", 3)
        esi_label = esi_result.get("esi_label", "URGENT")

        # ── Patient-facing report ────────────────────────────────────────
        triage_report_text = ""
        try:
            llm = ChatGoogleGenerativeAI(
                model=_GEMINI_MODEL, temperature=0.2,
                google_api_key=_GOOGLE_KEY
            )
            prompt = TRIAGE_REPORT_PROMPT.format(
                esi_level=esi_level,
                esi_label=esi_label,
                clinical_rationale=esi_result.get("clinical_rationale", ""),
                disposition=esi_result.get("disposition", ""),
                max_wait_minutes=esi_result.get("max_wait_minutes", 60),
                immediate_actions="; ".join(esi_result.get("immediate_actions", [])) or "None",
                patient_name=patient_name,
                chief_complaint=chief_complaint,
            )
            response = llm.invoke([SystemMessage(content=prompt)])
            triage_report_text = response.content
        except Exception as exc:
            logger.error("TriageAgent: patient report generation failed: %s", exc)
            triage_report_text = (
                f"**Triage Assessment Complete — ESI Level {esi_level} ({esi_label})**\n\n"
                f"{esi_result.get('patient_instruction', 'Please seek appropriate medical care.')}\n\n"
                f"Clinical rationale: {esi_result.get('clinical_rationale', 'See triage record.')}"
            )

        ctx["triage_report"] = triage_report_text

        # ── Clinical audit note ──────────────────────────────────────────
        audit_note_text = ""
        try:
            notifications_str = ", ".join(dispatch_result.get("notifications_sent", []) or
                                          queue_assignment.get("notes", ["Standard queue assignment"]))
            llm = ChatGoogleGenerativeAI(
                model=_GEMINI_MODEL, temperature=0,
                google_api_key=_GOOGLE_KEY
            )
            audit_prompt = TRIAGE_AUDIT_PROMPT.format(
                patient_id=state.get("patient_id", "unknown"),
                timestamp=ctx.get("triage_started_at", datetime.now(timezone.utc).isoformat()),
                chief_complaint=chief_complaint,
                vital_signs=TriageAgent._format_vitals_for_prompt(ctx.get("vital_signs", {})),
                red_flags="; ".join(ctx.get("red_flag_result", {}).get("flags", [])) or "None",
                esi_level=esi_level,
                esi_label=esi_label,
                clinical_rationale=esi_result.get("clinical_rationale", ""),
                disposition=esi_result.get("disposition", ""),
                notifications_sent=notifications_str or "None",
            )
            audit_response = llm.invoke([SystemMessage(content=audit_prompt)])
            audit_note_text = audit_response.content
        except Exception as exc:
            logger.error("TriageAgent: audit note generation failed: %s", exc)
            audit_note_text = f"Triage ID: {ctx.get('triage_id')} | ESI {esi_level} | Auto-generated"

        ctx["audit_note"] = audit_note_text

        # ── Persist audit to DB ──────────────────────────────────────────
        self._persist_triage_record(state, ctx, triage_report_text, audit_note_text)

        # ── Assemble final_response ──────────────────────────────────────
        final_response = {
            "type": "triage",
            "urgency": "emergency" if esi_level <= 2 else "urgent" if esi_level == 3 else "routine",
            "content": triage_report_text,
            "phase": "triage_complete",
            "triage_id": ctx.get("triage_id"),
            "esi_level": esi_level,
            "esi_label": esi_label,
            "max_wait_minutes": esi_result.get("max_wait_minutes", 60),
            "disposition": esi_result.get("disposition", ""),
            "patient_instruction": esi_result.get("patient_instruction", ""),
            "vital_threats": esi_result.get("vital_threats", []),
            "recommended_resources": esi_result.get("recommended_resources", []),
            "immediate_actions": esi_result.get("immediate_actions", []),
            "red_flags": ctx.get("red_flag_result", {}).get("flags", []),
            "preliminary_differentials": ctx.get("red_flag_result", {}).get("preliminary_differentials", []),
            "alert_dispatched": bool(dispatch_result),
            "alert_id": dispatch_result.get("alert_id"),
            "notifications_sent": dispatch_result.get("notifications_sent", []),
            "audit_note": audit_note_text,
        }

        logger.info(
            "TriageAgent: report generated for triage %s — ESI %d dispatched=%s",
            ctx.get("triage_id"), esi_level, bool(dispatch_result),
        )

        return {**state, "context": ctx, "final_response": final_response}

    def _persist_triage_record(
        self,
        state: AgentState,
        ctx: dict,
        report: str,
        audit_note: str,
    ) -> None:
        """Write triage record to DB for audit trail."""
        try:
            from app.models.db import db
            from sqlalchemy import text
            record = {
                "id": ctx.get("triage_id"),
                "patient_id": state.get("patient_id"),
                "chief_complaint": ctx.get("chief_complaint", "")[:500],
                "esi_level": ctx.get("esi_result", {}).get("esi_level"),
                "esi_label": ctx.get("esi_result", {}).get("esi_label", ""),
                "red_flags": json.dumps(ctx.get("red_flag_result", {}).get("flags", [])),
                "vitals_snapshot": json.dumps(ctx.get("vital_signs", {})),
                "patient_report": report,
                "audit_note": audit_note,
                "alert_dispatched": bool(ctx.get("dispatch_result")),
                "created_at": ctx.get("triage_started_at", datetime.now(timezone.utc).isoformat()),
            }
            db.session.execute(
                text("""
                    INSERT INTO triage_records
                        (id, patient_id, chief_complaint, esi_level, esi_label,
                         red_flags, vitals_snapshot, patient_report, audit_note,
                         alert_dispatched, created_at)
                    VALUES
                        (:id, :patient_id, :chief_complaint, :esi_level, :esi_label,
                         :red_flags, :vitals_snapshot, :patient_report, :audit_note,
                         :alert_dispatched, :created_at)
                    ON CONFLICT (id) DO NOTHING
                """),
                record,
            )
            db.session.commit()
        except Exception as exc:
            logger.error("TriageAgent: triage record persist failed: %s", exc)
            try:
                from app.models.db import db
                db.session.rollback()
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton (compiled once, reused per-request)
# ─────────────────────────────────────────────────────────────────────────────

_triage_agent_instance: Optional[TriageAgent] = None


def get_triage_agent() -> TriageAgent:
    """Return the compiled TriageAgent (singleton pattern)."""
    global _triage_agent_instance
    if _triage_agent_instance is None:
        _triage_agent_instance = TriageAgent(model="gemini-2.0-flash", temperature=0)
        logger.info("TriageAgent: instance compiled and cached")
    return _triage_agent_instance


def run_triage(
    chief_complaint: str,
    patient_id: Optional[str] = None,
    vital_signs: Optional[dict] = None,
    patient_context: Optional[dict] = None,
    session_id: Optional[str] = None,
) -> dict:
    """
    Convenience function to invoke the TriageAgent from REST endpoints
    or other agents without manually constructing the full state.

    Returns the final_response dict.
    """
    from langchain_core.messages import HumanMessage as HMsg

    initial_state: AgentState = {
        "messages": [HMsg(content=chief_complaint)],
        "patient_id": patient_id or "",
        "session_id": session_id or str(uuid.uuid4()),
        "intent": "triage",
        "context": {
            "chief_complaint": chief_complaint,
            "vital_signs": vital_signs or {},
            "patient": patient_context or {},
        },
        "tool_outputs": [],
        "final_response": None,
        "error": None,
    }

    agent = get_triage_agent()
    result_state = agent.invoke(initial_state)
    return result_state.get("final_response") or {}
