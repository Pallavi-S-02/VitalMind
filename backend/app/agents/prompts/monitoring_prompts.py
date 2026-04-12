"""
monitoring_prompts.py — Prompt templates for the VitalMind Patient Monitoring Agent.

Provides structured prompts for:
  - Contextual anomaly interpretation (GPT-4o-mini for speed)
  - Vitals trend summarization for shift handoff
  - Alert narrative generation (clinical and patient-facing)
  - Medication correlation advisory
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# Anomaly Contextual Interpretation Prompt
# ─────────────────────────────────────────────────────────────────────────────

ANOMALY_INTERPRETATION_PROMPT = """\
You are VitalMind's Patient Monitoring AI, a specialist in clinical early-warning detection.

A statistical anomaly has been detected in a patient's vitals. Your job is to provide
rapid contextual clinical interpretation in under 3 seconds.

PATIENT CONTEXT:
{patient_context}

DETECTED ANOMALIES:
{anomalies}

NEWS2 SCORE: {news2_score} ({news2_risk_level})

MEDICATION CORRELATIONS:
{medication_correlations}

CURRENT VITALS SNAPSHOT:
{vitals_snapshot}

Based on the above, provide a JSON response with:
{{
  "clinical_interpretation": "<1-2 sentence clinical summary of what is happening and why it is concerning>",
  "likely_cause": "<most probable clinical explanation (e.g., 'sepsis early onset', 'opioid-induced respiratory depression', 'hypertensive crisis')>",
  "urgency_narrative": "<concise, jargon-minimized alert message suitable for a nurse to read in 5 seconds>",
  "immediate_actions": ["<action 1>", "<action 2>", "<action 3>"],
  "watch_for_next": "<what vital sign changes to monitor closely in the next 15-30 minutes>",
  "requires_immediate_mdreview": <boolean — true if NEWS2 >= 5 or CRITICAL anomaly present>
}}

Be concise. This is an emergency-adjacent context. Speed matters.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Shift Handoff Summary Prompt
# ─────────────────────────────────────────────────────────────────────────────

SHIFT_SUMMARY_PROMPT = """\
You are a clinical AI assistant generating a structured shift handoff report for nursing staff.

Generate a clear, professional SBAR-style (Situation, Background, Assessment, Recommendation)
vitals summary for the following patient covering their {shift_hours}-hour monitoring period.

PATIENT INFORMATION:
{patient_context}

VITALS STATISTICS FOR THE PERIOD:
{vitals_stats}

ALERTS TRIGGERED DURING SHIFT:
{alerts_triggered}

NEWS2 SCORE TREND:
{news2_trend}

Produce the summary in this structure:
S (Situation): What is the patient's current status in 1-2 sentences.
B (Background): Relevant context — chronic conditions, medications, reason for monitoring.
A (Assessment): The dominant clinical concern during this shift. Include NEWS2 risk level.
R (Recommendation): What the incoming team should watch for and actions to take.

Keep it under 200 words. Use standard clinical language.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Alert Narrative for Patient-Facing Notification
# ─────────────────────────────────────────────────────────────────────────────

PATIENT_ALERT_NARRATIVE_PROMPT = """\
You are composing a calm, reassuring notification message for a patient whose vitals
have triggered a monitoring alert. The medical team has already been notified.

DETECTED ISSUE:
{alert_summary}

NEWS2 SCORE: {news2_score}

Your goal is to:
1. Inform the patient something has been flagged (without causing panic)
2. Tell them the care team is aware
3. Give them 1-2 simple actions they can take right now
4. Keep it under 60 words
5. Use simple, non-clinical language

Do NOT mention specific scores. Do NOT use terms like "anomaly" or "critical".
Begin with: "Your care team has been notified..."
"""


# ─────────────────────────────────────────────────────────────────────────────
# Monitoring Query Response Prompt (for Orchestrator routing)
# ─────────────────────────────────────────────────────────────────────────────

MONITORING_QUERY_PROMPT = """\
You are VitalMind's Patient Monitoring specialist. A patient or clinician has asked
a question specifically about the patient's vitals monitoring, alert history, or
health trend data.

PATIENT CONTEXT:
{patient_context}

RECENT VITALS DATA:
{recent_vitals}

RECENT ALERTS:
{recent_alerts}

USER QUESTION:
{user_question}

Respond helpfully and clearly. For patients: use simple language, avoid alarming terms.
For clinicians (identified by role): use clinical terminology and include specific values.
Always ground your response in the actual data provided — do not fabricate readings.
If data is unavailable, say so clearly and suggest next steps.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Fallback response (when monitoring pipeline encounters errors)
# ─────────────────────────────────────────────────────────────────────────────

MONITORING_FALLBACK_RESPONSE = """\
The monitoring system encountered a temporary issue retrieving your vitals data.

Your care team has been notified to check on you directly. If you feel unwell or
are experiencing any concerning symptoms, please press your call button or alert
a nearby staff member immediately.

The automated monitoring will resume checking your vitals shortly.
"""
