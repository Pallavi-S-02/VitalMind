"""
monitoring_agent.py — VitalMind Patient Monitoring Agent (LangGraph)

Continuous anomaly detection, NEWS2 early-warning scoring, and escalating
alert dispatch for inpatient and remote patient monitoring.

Graph topology:
  START
    │
    ▼
  ingest_vitals_stream    ← Fetch latest vitals from InfluxDB/Redis
    │
    ▼
  compute_baseline        ← Adaptive per-patient 7-day rolling baseline
    │
    ▼
  detect_anomaly          ← Z-score + absolute threshold anomaly detection
    │
    ├─ NORMAL ──────────────────────────────────────────────────────────────────┐
    │                                                                            │
    ▼ (anomalies present)                                                        │
  compute_early_warning_score  ← NEWS2 calculation node                         │
    │                                                                            │
    ▼                                                                            │
  evaluate_alert_threshold    ← Compare NEWS2 + severity against thresholds     │
    │                                                                            │
    ├─ BELOW_THRESHOLD ─────────────────────────────────────────────────────────┤
    │ (escalation_level >= 1)                                                    │
    ▼                                                                            │
  correlate_with_medications  ← Check if changes align with medication schedule │
    │                                                                            │
    ▼                                                                            │
  interpret_anomaly           ← GPT-4o-mini contextual clinical interpretation  │
    │                                                                            │
    ▼                                                                            │
  trigger_alert               ← Escalation chain: L1 nurse / L2 MD / L3 specialist
    │                                                                            │
    ▼◄───────────────────────────────────────────────────────────────────────────┘
  generate_vitals_summary     ← Periodic SBAR shift summary
    │
    ▼
  END
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
from app.agents.tools.vitals_analysis import (
    fetch_patient_vitals,
    compute_patient_baseline,
    calculate_news2_score,
    detect_vitals_anomaly,
    correlate_vitals_medications,
    generate_shift_summary,
)
from app.agents.tools.notification_tools import (
    send_nurse_alert,
    send_physician_sms_alert,
    send_emergency_specialist_alert,
)
from app.agents.prompts.monitoring_prompts import (
    ANOMALY_INTERPRETATION_PROMPT,
    SHIFT_SUMMARY_PROMPT,
    MONITORING_QUERY_PROMPT,
    MONITORING_FALLBACK_RESPONSE,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Alert threshold configuration
# ─────────────────────────────────────────────────────────────────────────────

# NEWS2 escalation thresholds (aligns with RCP 2017 guidelines)
NEWS2_LEVEL1_THRESHOLD = 1   # Low-medium: nurse assessment required
NEWS2_LEVEL2_THRESHOLD = 5   # Medium: urgent medical review <1 h
NEWS2_LEVEL3_THRESHOLD = 7   # High: immediate medical emergency


class MonitoringAgent(BaseAgent):
    """
    Patient Monitoring Agent — continuous anomaly detection and alert escalation.

    State contract (extends AgentState):
      context["vitals_snapshot"]       : dict  — current vitals from InfluxDB/Redis
      context["baseline_stats"]        : dict  — per-field rolling statistics
      context["anomaly_result"]        : dict  — anomaly detection output
      context["news2_result"]          : dict  — NEWS2 score calculation output
      context["escalation_level"]      : int   — 0=none, 1=nurse, 2=physician, 3=specialist
      context["medication_correlation"]: dict  — medication timing context
      context["interpretation"]        : dict  — GPT-4o-mini clinical interpretation
      context["alert_result"]          : dict  — alert dispatch result
      context["shift_summary"]         : str   — SBAR shift handoff narrative
      context["monitoring_mode"]       : str   — "continuous" | "query"
    """

    def get_tools(self) -> list:
        return [
            fetch_patient_vitals,
            compute_patient_baseline,
            calculate_news2_score,
            detect_vitals_anomaly,
            correlate_vitals_medications,
            generate_shift_summary,
            send_nurse_alert,
            send_physician_sms_alert,
            send_emergency_specialist_alert,
        ]

    def build_graph(self) -> StateGraph:
        graph = StateGraph(AgentState)

        # Add all nodes
        graph.add_node("ingest_vitals_stream", self._ingest_vitals_stream)
        graph.add_node("compute_baseline", self._compute_baseline)
        graph.add_node("detect_anomaly", self._detect_anomaly)
        graph.add_node("compute_early_warning_score", self._compute_early_warning_score)
        graph.add_node("evaluate_alert_threshold", self._evaluate_alert_threshold)
        graph.add_node("correlate_with_medications", self._correlate_with_medications)
        graph.add_node("interpret_anomaly", self._interpret_anomaly)
        graph.add_node("trigger_alert", self._trigger_alert)
        graph.add_node("generate_vitals_summary", self._generate_vitals_summary)

        # Main sequential flow
        graph.add_edge(START, "ingest_vitals_stream")
        graph.add_edge("ingest_vitals_stream", "compute_baseline")
        graph.add_edge("compute_baseline", "detect_anomaly")

        # Conditional: skip alert chain if vitals are within normal range
        graph.add_conditional_edges(
            "detect_anomaly",
            self._route_after_anomaly_check,
            {
                "anomaly_present": "compute_early_warning_score",
                "normal": "generate_vitals_summary",
            },
        )

        graph.add_edge("compute_early_warning_score", "evaluate_alert_threshold")

        # Conditional: skip alert dispatch if below notification thresholds
        graph.add_conditional_edges(
            "evaluate_alert_threshold",
            self._route_after_threshold_eval,
            {
                "needs_escalation": "correlate_with_medications",
                "below_threshold": "generate_vitals_summary",
            },
        )

        graph.add_edge("correlate_with_medications", "interpret_anomaly")
        graph.add_edge("interpret_anomaly", "trigger_alert")
        graph.add_edge("trigger_alert", "generate_vitals_summary")
        graph.add_edge("generate_vitals_summary", END)

        return graph

    # ─────────────────────────────────────────────────────────────────────────
    # Node implementations
    # ─────────────────────────────────────────────────────────────────────────

    def _ingest_vitals_stream(self, state: AgentState) -> AgentState:
        """
        Poll InfluxDB (via Redis cache) for the patient's latest vitals.
        Supports both continuous monitoring (fresh poll) and query mode
        (where vitals may already be in the context).
        """
        ctx = dict(state.get("context", {}))
        patient_id = state.get("patient_id")

        if not patient_id:
            logger.warning("MonitoringAgent: no patient_id in state — cannot fetch vitals")
            ctx["vitals_snapshot"] = {}
            ctx["vitals_error"] = "No patient_id provided"
            return {**state, "context": ctx}

        # Check if vitals were pre-loaded (e.g. from Celery task payload)
        if ctx.get("vitals_snapshot"):
            logger.debug("MonitoringAgent: using pre-loaded vitals for patient %s", patient_id)
            return {**state, "context": ctx}

        try:
            raw = fetch_patient_vitals.invoke({"patient_id": patient_id, "hours": 1})
            vitals_data = json.loads(raw)
            ctx["vitals_snapshot"] = vitals_data.get("current", {})
            ctx["vitals_history_sample"] = vitals_data.get("history_sample", [])
            logger.info(
                "MonitoringAgent: fetched vitals for patient %s — fields: %s",
                patient_id,
                list(ctx["vitals_snapshot"].keys()),
            )
        except Exception as exc:
            logger.error("MonitoringAgent: vitals fetch failed for %s: %s", patient_id, exc)
            ctx["vitals_snapshot"] = {}
            ctx["vitals_error"] = str(exc)

        tool_outputs = list(state.get("tool_outputs", []))
        tool_outputs.append({"node": "ingest_vitals_stream", "status": "complete"})
        return {**state, "context": ctx, "tool_outputs": tool_outputs}

    def _compute_baseline(self, state: AgentState) -> AgentState:
        """
        Compute per-patient adaptive baseline (7-day rolling stats) from InfluxDB.
        Falls back to population norms if no personal history exists.
        """
        ctx = dict(state.get("context", {}))
        patient_id = state.get("patient_id")

        if not patient_id or not ctx.get("vitals_snapshot"):
            ctx["baseline_stats"] = {}
            return {**state, "context": ctx}

        try:
            raw = compute_patient_baseline.invoke({"patient_id": patient_id, "hours": 168})
            baseline_data = json.loads(raw)
            ctx["baseline_stats"] = baseline_data.get("baselines", {})
            logger.debug(
                "MonitoringAgent: baseline computed for patient %s — fields: %s",
                patient_id,
                list(ctx["baseline_stats"].keys()),
            )
        except Exception as exc:
            logger.warning("MonitoringAgent: baseline computation failed for %s: %s", patient_id, exc)
            ctx["baseline_stats"] = {}

        return {**state, "context": ctx}

    def _detect_anomaly(self, state: AgentState) -> AgentState:
        """
        Run statistical anomaly detection (Z-score + absolute clinical thresholds).
        Sets escalation_level = 0 if no anomalies detected.
        """
        ctx = dict(state.get("context", {}))
        patient_id = state.get("patient_id")
        vitals = ctx.get("vitals_snapshot", {})

        if not vitals:
            ctx["anomaly_result"] = {"anomaly_detected": False, "anomalies": [], "overall_severity": "NORMAL"}
            ctx["escalation_level"] = 0
            return {**state, "context": ctx}

        try:
            vitals_json = json.dumps(vitals)
            raw = detect_vitals_anomaly.invoke({
                "patient_id": patient_id,
                "current_vitals": vitals_json,
            })
            anomaly_result = json.loads(raw)
            ctx["anomaly_result"] = anomaly_result

            # Pre-set escalation level 0; will be refined in evaluate_alert_threshold
            if not anomaly_result.get("anomaly_detected"):
                ctx["escalation_level"] = 0

            logger.info(
                "MonitoringAgent: anomaly check for patient %s — detected=%s severity=%s",
                patient_id,
                anomaly_result.get("anomaly_detected"),
                anomaly_result.get("overall_severity"),
            )
        except Exception as exc:
            logger.error("MonitoringAgent: anomaly detection failed for %s: %s", patient_id, exc)
            ctx["anomaly_result"] = {"anomaly_detected": False, "anomalies": [], "overall_severity": "NORMAL"}
            ctx["escalation_level"] = 0

        tool_outputs = list(state.get("tool_outputs", []))
        tool_outputs.append({"node": "detect_anomaly", "status": "complete"})
        return {**state, "context": ctx, "tool_outputs": tool_outputs}

    def _route_after_anomaly_check(self, state: AgentState) -> str:
        """Conditional edge: proceed to NEWS2 only if anomalies were detected."""
        anomaly = state.get("context", {}).get("anomaly_result", {})
        if anomaly.get("anomaly_detected"):
            return "anomaly_present"
        return "normal"

    def _compute_early_warning_score(self, state: AgentState) -> AgentState:
        """
        Calculate NEWS2 score from current vitals snapshot.
        NEWS2 is the UK National Early Warning Score 2 (RCP 2017 standard).
        """
        ctx = dict(state.get("context", {}))
        vitals = ctx.get("vitals_snapshot", {})
        patient_id = state.get("patient_id")

        if not vitals:
            ctx["news2_result"] = {"news2_total": 0, "risk_level": "Low", "escalation_level": 0}
            return {**state, "context": ctx}

        try:
            raw = calculate_news2_score.invoke({
                "heart_rate": vitals.get("heart_rate"),
                "respiratory_rate": vitals.get("respiratory_rate"),
                "spo2": vitals.get("spo2"),
                "systolic_bp": vitals.get("systolic_bp"),
                "temperature_c": vitals.get("temperature_c"),
                "consciousness": vitals.get("consciousness", "A"),
                "supplemental_oxygen": vitals.get("supplemental_oxygen", False),
            })
            news2_result = json.loads(raw)
            ctx["news2_result"] = news2_result

            logger.info(
                "MonitoringAgent: NEWS2 computed for patient %s — total=%d risk=%s escalation=%d",
                patient_id,
                news2_result.get("news2_total", 0),
                news2_result.get("risk_level", "Unknown"),
                news2_result.get("escalation_level", 0),
            )
        except Exception as exc:
            logger.error("MonitoringAgent: NEWS2 calculation failed for %s: %s", patient_id, exc)
            ctx["news2_result"] = {"news2_total": 0, "risk_level": "Unknown", "escalation_level": 0}

        tool_outputs = list(state.get("tool_outputs", []))
        tool_outputs.append({"node": "compute_early_warning_score", "status": "complete"})
        return {**state, "context": ctx, "tool_outputs": tool_outputs}

    def _evaluate_alert_threshold(self, state: AgentState) -> AgentState:
        """
        Compare NEWS2 score and anomaly severity against configurable thresholds
        to determine the escalation level that should be triggered.

        Escalation levels:
          0 = no action (normal range)
          1 = Level 1: nurse in-app push notification
          2 = Level 2: attending physician SMS
          3 = Level 3: on-call specialist emergency page
        """
        ctx = dict(state.get("context", {}))
        news2 = ctx.get("news2_result", {})
        anomaly = ctx.get("anomaly_result", {})

        news2_score = news2.get("news2_total", 0)
        news2_escalation = news2.get("escalation_level", 0)
        overall_severity = anomaly.get("overall_severity", "NORMAL")

        # Map to VitalMind escalation levels
        if overall_severity == "CRITICAL" or news2_score >= NEWS2_LEVEL3_THRESHOLD:
            escalation_level = 3
        elif news2_score >= NEWS2_LEVEL2_THRESHOLD:
            escalation_level = 2
        elif news2_score >= NEWS2_LEVEL1_THRESHOLD or overall_severity in ("HIGH", "MODERATE"):
            escalation_level = 1
        else:
            escalation_level = 0

        ctx["escalation_level"] = escalation_level

        logger.info(
            "MonitoringAgent: threshold evaluation — news2=%d, severity=%s → escalation_level=%d",
            news2_score, overall_severity, escalation_level,
        )

        return {**state, "context": ctx}

    def _route_after_threshold_eval(self, state: AgentState) -> str:
        """Conditional edge: escalate if level >= 1."""
        level = state.get("context", {}).get("escalation_level", 0)
        return "needs_escalation" if level >= 1 else "below_threshold"

    def _correlate_with_medications(self, state: AgentState) -> AgentState:
        """
        Check if detected vitals anomalies may be explained by recent medication
        administrations (e.g., beta-blocker → low HR, opioid → low RR).
        """
        ctx = dict(state.get("context", {}))
        patient_id = state.get("patient_id")
        anomaly = ctx.get("anomaly_result", {})
        anomalies = anomaly.get("anomalies", [])

        if not anomalies:
            ctx["medication_correlation"] = {}
            return {**state, "context": ctx}

        # Build comma-separated list of anomalous fields for the tool
        anomalous_fields = ",".join({a["field"] for a in anomalies if "field" in a})

        if not anomalous_fields:
            ctx["medication_correlation"] = {}
            return {**state, "context": ctx}

        try:
            raw = correlate_vitals_medications.invoke({
                "patient_id": patient_id,
                "anomalous_fields": anomalous_fields,
            })
            correlation = json.loads(raw)
            ctx["medication_correlation"] = correlation
            logger.debug(
                "MonitoringAgent: medication correlation for patient %s — %d correlations found",
                patient_id, correlation.get("correlations_found", 0),
            )
        except Exception as exc:
            logger.warning("MonitoringAgent: medication correlation failed for %s: %s", patient_id, exc)
            ctx["medication_correlation"] = {}

        return {**state, "context": ctx}

    def _interpret_anomaly(self, state: AgentState) -> AgentState:
        """
        GPT-4o-mini contextual clinical interpretation of the detected anomalies.
        Generates the urgency narrative used in the alert message.
        Uses gpt-4o-mini for speed — target <1.5s response time.
        """
        ctx = dict(state.get("context", {}))
        patient_id = state.get("patient_id")
        anomaly = ctx.get("anomaly_result", {})
        news2 = ctx.get("news2_result", {})
        vitals = ctx.get("vitals_snapshot", {})
        correlation = ctx.get("medication_correlation", {})

        # Load patient context for better interpretation
        patient_context = "Patient information not available."
        try:
            from app.agents.memory.patient_memory import PatientMemory
            memory = PatientMemory(patient_id)
            profile = memory.load()
            patient_context = (
                f"Name: {profile.get('name', 'Unknown')}, "
                f"Age: {profile.get('age', 'Unknown')}, "
                f"Conditions: {', '.join(profile.get('chronic_conditions', [])) or 'None documented'}, "
                f"Current meds: {', '.join(m.get('name', str(m)) if isinstance(m, dict) else str(m) for m in profile.get('current_medications', [])) or 'None'}"
            )
        except Exception as exc:
            logger.debug("MonitoringAgent: could not load patient context for interpretation: %s", exc)

        # Format anomalies for the prompt
        anomaly_text = "\n".join(
            f"• [{a.get('severity')}] {a.get('field')}: {a.get('message', '')}"
            for a in anomaly.get("anomalies", [])
        ) or "Anomalies detected but details unavailable."

        # Format correlation summary
        correlation_text = (
            f"{correlation.get('correlations_found', 0)} possible medication correlations found. "
            + (
                "Top correlation: " + correlation.get("correlations", [{}])[0].get("advisory", "")
                if correlation.get("correlations")
                else "No specific correlations identified."
            )
        )

        system_prompt = ANOMALY_INTERPRETATION_PROMPT.format(
            patient_context=patient_context,
            anomalies=anomaly_text,
            news2_score=news2.get("news2_total", 0),
            news2_risk_level=news2.get("risk_level", "Unknown"),
            medication_correlations=correlation_text,
            vitals_snapshot=json.dumps(vitals, indent=2),
        )

        try:
            # Use gpt-4o-mini for speed — monitoring is latency-sensitive
            llm = ChatGoogleGenerativeAI(
                model=_GEMINI_MODEL, temperature=0,
                google_api_key=_GOOGLE_KEY
            )
            response = llm.invoke([HumanMessage(content=system_prompt)])
            interpretation = json.loads(extract_llm_text(response))
            ctx["interpretation"] = interpretation
            logger.info(
                "MonitoringAgent: interpretation complete for patient %s — urgency_narrative ready",
                patient_id,
            )
        except Exception as exc:
            logger.error("MonitoringAgent: interpretation failed for %s: %s", patient_id, exc)
            ctx["interpretation"] = {
                "clinical_interpretation": "Vitals anomaly detected — automated interpretation unavailable.",
                "urgency_narrative": f"Patient {patient_id} has triggered a vitals alert. Please assess immediately.",
                "immediate_actions": ["Assess patient immediately", "Review current medications", "Notify attending physician"],
                "requires_immediate_mdreview": ctx.get("escalation_level", 0) >= 2,
            }

        tool_outputs = list(state.get("tool_outputs", []))
        tool_outputs.append({"node": "interpret_anomaly", "status": "complete"})
        return {**state, "context": ctx, "tool_outputs": tool_outputs}

    def _trigger_alert(self, state: AgentState) -> AgentState:
        """
        Execute the escalation chain based on escalation_level:
          Level 1 → Nurse in-app Socket.IO push notification
          Level 2 → Attending physician SMS (Twilio)
          Level 3 → On-call specialist emergency page + Redis broadcast
        """
        ctx = dict(state.get("context", {}))
        patient_id = state.get("patient_id", "Unknown")
        escalation_level = ctx.get("escalation_level", 0)
        news2 = ctx.get("news2_result", {})
        interpretation = ctx.get("interpretation", {})
        anomaly = ctx.get("anomaly_result", {})
        vitals = ctx.get("vitals_snapshot", {})

        if escalation_level == 0:
            ctx["alert_result"] = {"status": "no_action_required", "level": 0}
            return {**state, "context": ctx}

        news2_score = news2.get("news2_total", 0)
        urgency_narrative = interpretation.get(
            "urgency_narrative",
            f"Vitals anomaly detected for patient {patient_id}.",
        )

        # Build a vitals summary string for the alert message
        vitals_summary_parts = []
        if vitals.get("heart_rate"):
            vitals_summary_parts.append(f"HR:{vitals['heart_rate']}bpm")
        if vitals.get("spo2"):
            vitals_summary_parts.append(f"SpO2:{vitals['spo2']}%")
        if vitals.get("systolic_bp"):
            vitals_summary_parts.append(f"BP:{vitals.get('systolic_bp')}/{vitals.get('diastolic_bp', '?')}mmHg")
        if vitals.get("temperature_c"):
            vitals_summary_parts.append(f"Temp:{vitals['temperature_c']}°C")
        if vitals.get("respiratory_rate"):
            vitals_summary_parts.append(f"RR:{vitals['respiratory_rate']}/min")
        vitals_summary = " | ".join(vitals_summary_parts) or "Vitals data unavailable"

        # Retrieve patient name from context
        patient_name = "Unknown Patient"
        try:
            from app.agents.memory.patient_memory import PatientMemory
            profile = PatientMemory(patient_id).load()
            patient_name = profile.get("name", f"Patient {patient_id[:8]}")
        except Exception:
            patient_name = f"Patient {str(patient_id)[:8]}"

        alert_result = {"level": escalation_level, "patient_id": patient_id}

        try:
            if escalation_level >= 1:
                # Level 1: Nurse push notification (always triggered for escalation_level >= 1)
                raw = send_nurse_alert.invoke({
                    "patient_id": patient_id,
                    "patient_name": patient_name,
                    "alert_message": urgency_narrative,
                    "news2_score": news2_score,
                    "vitals_summary": vitals_summary,
                })
                alert_result["nurse_alert"] = json.loads(raw)
                logger.warning(
                    "MonitoringAgent: Level 1 nurse alert dispatched for patient %s (NEWS2=%d)",
                    patient_id, news2_score,
                )

            if escalation_level >= 2:
                # Level 2: Physician SMS
                physician_phone = ctx.get("physician_phone") or "+10000000000"  # Fallback placeholder
                raw = send_physician_sms_alert.invoke({
                    "patient_id": patient_id,
                    "patient_name": patient_name,
                    "alert_message": urgency_narrative,
                    "news2_score": news2_score,
                    "physician_phone": physician_phone,
                    "vitals_summary": vitals_summary,
                })
                alert_result["physician_alert"] = json.loads(raw)
                logger.warning(
                    "MonitoringAgent: Level 2 physician SMS alert dispatched for patient %s (NEWS2=%d)",
                    patient_id, news2_score,
                )

            if escalation_level >= 3:
                # Level 3: Emergency specialist page
                specialist_phone = ctx.get("specialist_phone") or "+10000000001"  # Fallback placeholder
                anomaly_details = " | ".join(
                    a.get("message", "") for a in anomaly.get("anomalies", [])[:3]
                ) or "Multiple critical vitals anomalies detected."

                raw = send_emergency_specialist_alert.invoke({
                    "patient_id": patient_id,
                    "patient_name": patient_name,
                    "alert_message": urgency_narrative,
                    "news2_score": news2_score,
                    "specialist_phone": specialist_phone,
                    "vitals_summary": vitals_summary,
                    "anomaly_details": anomaly_details,
                })
                alert_result["specialist_alert"] = json.loads(raw)
                logger.critical(
                    "MonitoringAgent: Level 3 EMERGENCY alert dispatched for patient %s (NEWS2=%d)",
                    patient_id, news2_score,
                )

            alert_result["status"] = "dispatched"
        except Exception as exc:
            logger.error("MonitoringAgent: alert dispatch failed for patient %s: %s", patient_id, exc)
            alert_result["status"] = "dispatch_failed"
            alert_result["error"] = str(exc)

        ctx["alert_result"] = alert_result

        tool_outputs = list(state.get("tool_outputs", []))
        tool_outputs.append({
            "node": "trigger_alert",
            "level": escalation_level,
            "status": alert_result.get("status"),
        })
        return {**state, "context": ctx, "tool_outputs": tool_outputs}

    def _generate_vitals_summary(self, state: AgentState) -> AgentState:
        """
        Generate a structured vitals trend summary for the monitoring run.
        This acts as the final_response for both alert and normal monitoring cycles.
        Shift-level SBAR summaries are generated separately via the shift_hours param.
        """
        ctx = dict(state.get("context", {}))
        patient_id = state.get("patient_id")
        vitals = ctx.get("vitals_snapshot", {})
        anomaly = ctx.get("anomaly_result", {})
        news2 = ctx.get("news2_result", {})
        interpretation = ctx.get("interpretation", {})
        alert_result = ctx.get("alert_result", {})
        escalation_level = ctx.get("escalation_level", 0)

        # Check if this is a user-facing query (via Orchestrator) or a background monitoring run
        is_query_mode = ctx.get("monitoring_mode") == "query"
        messages = state.get("messages", [])

        if is_query_mode and messages:
            # Respond to the user's specific question about monitoring
            user_question = next(
                (m.content for m in reversed(messages) if isinstance(m, HumanMessage)), ""
            )
            patient_context = "Patient context unavailable."
            try:
                from app.agents.memory.patient_memory import PatientMemory
                patient_context = str(PatientMemory(patient_id).load())[:500]
            except Exception:
                pass

            try:
                llm = ChatGoogleGenerativeAI(
                    model=_GEMINI_MODEL, temperature=0.1,
                    google_api_key=_GOOGLE_KEY
                )
                response = llm.invoke([HumanMessage(content=MONITORING_QUERY_PROMPT.format(
                    patient_context=patient_context,
                    recent_vitals=json.dumps(vitals, indent=2) if vitals else "Not available",
                    recent_alerts=json.dumps(alert_result, indent=2) if alert_result else "No recent alerts",
                    user_question=user_question,
                ))])
                ctx["shift_summary"] = response.content
            except Exception as exc:
                logger.error("MonitoringAgent: query response failed: %s", exc)
                ctx["shift_summary"] = MONITORING_FALLBACK_RESPONSE

        else:
            # Build a structured machine-readable monitoring cycle report
            ctx["shift_summary"] = json.dumps({
                "monitoring_cycle": {
                    "patient_id": patient_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "vitals": vitals,
                    "news2": {
                        "total": news2.get("news2_total", 0),
                        "risk_level": news2.get("risk_level", "Not computed"),
                        "recommended_action": news2.get("recommended_action", ""),
                    },
                    "anomaly_detected": anomaly.get("anomaly_detected", False),
                    "overall_severity": anomaly.get("overall_severity", "NORMAL"),
                    "anomaly_count": anomaly.get("anomaly_count", 0),
                    "escalation_level": escalation_level,
                    "alert_status": alert_result.get("status", "no_action"),
                    "clinical_interpretation": interpretation.get("clinical_interpretation", ""),
                }
            }, indent=2)

        # Build the final_response that the Orchestrator will return to the user/task
        final_response = {
            "type": "monitoring_report",
            "patient_id": patient_id,
            "vitals": vitals,
            "news2_score": news2.get("news2_total", 0),
            "risk_level": news2.get("risk_level", "Low"),
            "anomaly_detected": anomaly.get("anomaly_detected", False),
            "overall_severity": anomaly.get("overall_severity", "NORMAL"),
            "escalation_level": escalation_level,
            "alert_dispatched": alert_result.get("status") == "dispatched",
            "urgency_narrative": interpretation.get("urgency_narrative", ""),
            "immediate_actions": interpretation.get("immediate_actions", []),
            "monitoring_cycle_report": ctx.get("shift_summary", ""),
        }

        tool_outputs = list(state.get("tool_outputs", []))
        tool_outputs.append({"node": "generate_vitals_summary", "status": "complete"})

        return {
            **state,
            "context": ctx,
            "final_response": final_response,
            "tool_outputs": tool_outputs,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Convenience class method for Celery task invocation
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def run_monitoring_cycle(
        cls,
        patient_id: str,
        vitals_snapshot: Optional[dict] = None,
        physician_phone: Optional[str] = None,
        specialist_phone: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Convenience factory method for the Celery beat task.
        Creates an agent instance and runs one complete monitoring cycle.

        Args:
            patient_id: UUID of the patient to monitor
            vitals_snapshot: Pre-fetched vitals dict (skip InfluxDB fetch if provided)
            physician_phone: Attending physician phone for Level 2 SMS alerts
            specialist_phone: On-call specialist phone for Level 3 emergency pages

        Returns:
            Final agent state dict with monitoring_report in final_response
        """
        agent = cls(model="gemini-2.0-flash", temperature=0)  # fast for Celery
        initial_state: AgentState = {
            "messages": [],
            "patient_id": patient_id,
            "session_id": f"monitoring_{patient_id}_{uuid.uuid4().hex[:8]}",
            "intent": "monitoring_cycle",
            "context": {
                "monitoring_mode": "continuous",
                "vitals_snapshot": vitals_snapshot or {},
                "physician_phone": physician_phone,
                "specialist_phone": specialist_phone,
            },
            "tool_outputs": [],
            "final_response": None,
            "error": None,
        }
        return agent.invoke(initial_state)
