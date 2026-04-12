"""
care_plan_prompts.py — Prompt templates for the Follow-Up & Care Plan Agent.
"""

# ─────────────────────────────────────────────────────────────────────────────
# Patient state assessment
# ─────────────────────────────────────────────────────────────────────────────

ASSESS_PATIENT_STATE_PROMPT = """You are a clinical AI assistant reviewing a patient's current health state.

Patient ID: {patient_id}

Available context:
- Recent diagnoses: {diagnoses}
- Current medications: {medications}
- Recent vitals summary: {vitals_summary}
- Active care plan: {active_care_plan}
- Appointment history: {appointment_history}

Summarize the patient's current clinical state in 3-5 sentences. Focus on:
1. Primary conditions being managed
2. Current treatment trajectory (improving/stable/deteriorating)
3. Key risk factors or concerns
4. Gaps in care (missed appointments, non-adherence)

Return JSON:
{{
  "state_summary": "...",
  "primary_conditions": ["..."],
  "risk_level": "low|medium|high|critical",
  "care_gaps": ["..."],
  "trajectory": "improving|stable|deteriorating|unknown"
}}"""

# ─────────────────────────────────────────────────────────────────────────────
# Care plan generation
# ─────────────────────────────────────────────────────────────────────────────

GENERATE_CARE_PLAN_PROMPT = """You are an expert clinical care coordinator generating a personalized, evidence-based care plan.

Patient state assessment:
{state_assessment}

Patient profile:
- Age: {age}
- Gender: {gender}
- Primary conditions: {conditions}
- Current medications: {medications}
- Allergies: {allergies}

Generate a comprehensive, structured care plan for the next {duration_weeks} weeks.

Return ONLY valid JSON matching this schema exactly:
{{
  "title": "Care Plan: <primary condition>",
  "description": "2-sentence overview of the plan",
  "goals": [
    {{
      "id": "g1",
      "title": "...",
      "description": "...",
      "target_metric": "e.g. Blood pressure < 130/80",
      "timeframe_weeks": 4,
      "priority": "high|medium|low"
    }}
  ],
  "milestones": [
    {{
      "week": 2,
      "description": "...",
      "success_criteria": "..."
    }}
  ],
  "tasks": [
    {{
      "title": "...",
      "description": "...",
      "type": "exercise|diet|medication_reminder|reading|vitals_check",
      "frequency": "daily|weekly|twice_daily|as_needed",
      "time_of_day": "morning|afternoon|evening|anytime"
    }}
  ],
  "education_topics": ["..."],
  "follow_up_weeks": 4,
  "success_metrics": ["..."]
}}"""

# ─────────────────────────────────────────────────────────────────────────────
# Patient education content
# ─────────────────────────────────────────────────────────────────────────────

PATIENT_EDUCATION_PROMPT = """You are a patient education specialist creating accessible health information.

Condition: {condition}
Patient age: {age}
Reading level: simple (8th grade)

Generate a structured educational guide for this patient about their condition.

Return JSON:
{{
  "condition": "{condition}",
  "overview": "2-3 sentence plain language explanation",
  "key_facts": ["..."],
  "warning_signs": ["..."],
  "lifestyle_tips": ["..."],
  "medication_notes": ["..."],
  "when_to_call_doctor": ["..."],
  "resources": ["..."]
}}"""

# ─────────────────────────────────────────────────────────────────────────────
# Adherence tracking & deviation detection
# ─────────────────────────────────────────────────────────────────────────────

ADHERENCE_ANALYSIS_PROMPT = """You are a clinical adherence analyst.

Patient care plan:
{care_plan}

Completed tasks in the last {days} days:
{completed_tasks}

Missed tasks:
{missed_tasks}

Recent appointments (attended vs missed):
{appointment_adherence}

Medication fill data:
{medication_fills}

Analyze adherence and identify deviations from the care plan.

Return JSON:
{{
  "overall_adherence_pct": 0-100,
  "medication_adherence_pct": 0-100,
  "appointment_adherence_pct": 0-100,
  "task_adherence_pct": 0-100,
  "deviations": [
    {{
      "type": "missed_medication|skipped_task|missed_appointment|vitals_out_of_range",
      "description": "...",
      "severity": "low|medium|high",
      "recommendation": "..."
    }}
  ],
  "on_track": true|false,
  "requires_plan_adjustment": true|false,
  "summary": "..."
}}"""

# ─────────────────────────────────────────────────────────────────────────────
# Care plan adjustment
# ─────────────────────────────────────────────────────────────────────────────

ADJUST_CARE_PLAN_PROMPT = """You are a clinical care coordinator updating a care plan based on patient progress.

Current care plan:
{current_plan}

Adherence analysis:
{adherence_analysis}

Patient feedback/complaints:
{patient_feedback}

Recommend specific adjustments to the care plan. Be conservative — only change what is necessary.

Return JSON:
{{
  "adjustments": [
    {{
      "section": "goals|tasks|milestones|medications",
      "action": "modify|add|remove",
      "item_id": "...",
      "change": "...",
      "rationale": "..."
    }}
  ],
  "new_tasks": [],
  "removed_task_ids": [],
  "updated_goals": [],
  "adjustment_summary": "..."
}}"""

# ─────────────────────────────────────────────────────────────────────────────
# Progress report
# ─────────────────────────────────────────────────────────────────────────────

PROGRESS_REPORT_PROMPT = """You are a clinical care coordinator writing a progress report for both the doctor and patient.

Patient ID: {patient_id}
Report period: {period_weeks} weeks
Care plan title: {plan_title}
Adherence analysis: {adherence}
Goals progress: {goals_progress}
Clinical notes: {clinical_notes}

Generate a structured progress report suitable for the medical record.

Return JSON:
{{
  "report_date": "{report_date}",
  "period_summary": "...",
  "achievements": ["..."],
  "challenges": ["..."],
  "goal_statuses": [
    {{
      "goal": "...",
      "status": "on_track|behind|achieved|paused",
      "notes": "..."
    }}
  ],
  "overall_adherence_pct": 0-100,
  "clinical_observations": "...",
  "recommended_next_steps": ["..."],
  "for_patient": "Plain language summary for the patient (2-3 sentences)"
}}"""
