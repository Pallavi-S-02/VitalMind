"""
followup_agent.py — Follow-Up & Care Plan Agent (Step 23)

A 9-node LangGraph StateGraph that:
  1. assess_patient_state   — Gathers vitals, diagnosis, medication, appointment history
  2. generate_care_plan     — GPT-4o creates a structured SOAP-adjacent JSON care plan
  3. schedule_followup      — Books the next appointment via scheduling.py tool
  4. generate_patient_education — Condition-specific plain-language education
  5. track_adherence        — Checks task completion, fill history, appointment attendance
  6. detect_deviation       — Identifies patients slipping off track
  7. adjust_care_plan       — Revises plan based on deviation analysis
  8. send_reminder          — Triggers notification for non-adherent patients
  9. generate_progress_report — Structured summary for patient + physician

Two entry modes:
  - "generate"   : nodes 1 → 2 → 3 → 4 → END   (initial plan creation)
  - "track"      : nodes 1 → 5 → 6 → [7/8] → 9 → END  (adherence monitoring)
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime, timezone, timedelta
from typing import Any, Optional, TypedDict

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

_GEMINI_MODEL = "gemini-3.1-pro-preview"
_GOOGLE_KEY = __import__("os").getenv("GOOGLE_API_KEY")
from langgraph.graph import StateGraph, END

from app.agents.prompts.care_plan_prompts import (
    ASSESS_PATIENT_STATE_PROMPT,
    GENERATE_CARE_PLAN_PROMPT,
    PATIENT_EDUCATION_PROMPT,
    ADHERENCE_ANALYSIS_PROMPT,
    ADJUST_CARE_PLAN_PROMPT,
    PROGRESS_REPORT_PROMPT,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# State
# ─────────────────────────────────────────────────────────────────────────────

class CarePlanState(TypedDict, total=False):
    # Inputs
    patient_id: str
    doctor_id: Optional[str]
    mode: str                         # "generate" | "track"
    plan_id: Optional[str]            # existing care_plan.id for track mode
    patient_context: dict[str, Any]   # pre-fetched patient profile
    duration_weeks: int               # plan duration
    patient_feedback: str             # optional feedback from patient

    # Intermediate
    state_assessment: dict            # output of assess_patient_state
    care_plan_json: dict              # raw JSON from LLM
    education_content: dict           # per-condition education
    adherence_analysis: dict          # output of track_adherence
    deviations: list[dict]
    plan_adjustments: dict

    # Outputs
    care_plan_id: Optional[str]       # saved DB record ID
    progress_report: dict
    follow_up_appointment_id: Optional[str]
    notifications_sent: list[str]
    error: Optional[str]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _llm(model: str = "gemini-2.0-flash", temperature: float = 0.2) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=_GEMINI_MODEL, temperature=temperature,
        google_api_key=_GOOGLE_KEY, 
        request_timeout=30,
    )


def _safe_json(text: Any) -> dict:
    if isinstance(text, dict):
        return text
        
    if isinstance(text, list):
        # Handle LangChain message content lists (e.g., from Gemini models)
        extracted = []
        for item in text:
            if isinstance(item, str):
                extracted.append(item)
            elif isinstance(item, dict) and "text" in item:
                extracted.append(item["text"])
            else:
                extracted.append(str(item))
        text = " ".join(extracted)
        
    text = str(text)
    try:
        return json.loads(text)
    except Exception:
        import re
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    return {}


def _fetch_patient_context(patient_id: str) -> dict:
    """Load patient profile, medications, recent vitals, recent appointments."""
    ctx: dict = {
        "patient_id": patient_id,
        "age": None,
        "gender": None,
        "diagnoses": [],
        "medications": [],
        "allergies": [],
        "vitals_summary": "No recent vitals available.",
        "active_care_plan": None,
        "appointment_history": [],
    }
    
    resolved_profile_id = patient_id
    
    try:
        from app.models.patient import PatientProfile
        # Try finding by user_id first
        profile = PatientProfile.query.filter_by(user_id=patient_id).first()
        if not profile:
            # Fallback to finding by profile id
            profile = PatientProfile.query.get(patient_id)
            
        if profile:
            resolved_profile_id = str(profile.id)
            if profile.date_of_birth:
                ctx["age"] = (datetime.now().date() - profile.date_of_birth).days // 365
            ctx["gender"] = profile.gender
            
            # Serialize relationships to simple strings or dicts
            if hasattr(profile, 'medical_history') and profile.medical_history:
                ctx["diagnoses"] = [mh.condition_name for mh in profile.medical_history]
            if hasattr(profile, 'prescriptions') and profile.prescriptions:
                ctx["medications"] = [f"{p.medication.name} ({p.dosage}, {p.frequency})" for p in profile.prescriptions if p.medication]
            if hasattr(profile, 'allergies') and profile.allergies:
                ctx["allergies"] = [a.allergen for a in profile.allergies]
    except Exception as exc:
        logger.warning("CarePlanAgent: patient profile fetch failed: %s", exc)

    try:
        from app.models.appointment import Appointment
        appts = (
            Appointment.query
            .filter_by(patient_id=resolved_profile_id)
            .order_by(Appointment.start_time.desc())
            .limit(5)
            .all()
        )
        ctx["appointment_history"] = [
            {"date": str(a.start_time.date()), "status": a.status, "type": a.type}
            for a in appts
        ]
    except Exception:
        pass

    try:
        from app.models.care_plan import CarePlan
        plan = CarePlan.query.filter_by(patient_id=resolved_profile_id, status="active").first()
        if plan:
            ctx["active_care_plan"] = {
                "id": str(plan.id),
                "title": plan.title,
                "goals": plan.goals or {},
            }
    except Exception:
        pass

    return ctx


# ─────────────────────────────────────────────────────────────────────────────
# Nodes
# ─────────────────────────────────────────────────────────────────────────────

def assess_patient_state(state: CarePlanState) -> CarePlanState:
    """Node 1: Gather and summarize patient's current clinical state."""
    patient_id = state.get("patient_id", "")
    ctx = state.get("patient_context") or _fetch_patient_context(patient_id)

    prompt = ASSESS_PATIENT_STATE_PROMPT.format(
        patient_id=patient_id,
        diagnoses=json.dumps(ctx.get("diagnoses", [])),
        medications=json.dumps(ctx.get("medications", [])),
        vitals_summary=ctx.get("vitals_summary", "N/A"),
        active_care_plan=json.dumps(ctx.get("active_care_plan")),
        appointment_history=json.dumps(ctx.get("appointment_history", [])),
    )

    try:
        response = _llm("gemini-2.0-flash").invoke([HumanMessage(content=prompt)])
        assessment = _safe_json(response.content)
    except Exception as exc:
        logger.error("assess_patient_state LLM failed: %s", exc)
        assessment = {
            "state_summary": "Assessment unavailable.",
            "primary_conditions": ctx.get("diagnoses", []),
            "risk_level": "unknown",
            "care_gaps": [],
            "trajectory": "unknown",
        }

    return {**state, "patient_context": ctx, "state_assessment": assessment}


def generate_care_plan(state: CarePlanState) -> CarePlanState:
    """Node 2: Generate structured care plan JSON via GPT-4o."""
    ctx = state.get("patient_context", {})
    assessment = state.get("state_assessment", {})
    duration = state.get("duration_weeks", 8)

    prompt = GENERATE_CARE_PLAN_PROMPT.format(
        state_assessment=json.dumps(assessment, indent=2),
        age=ctx.get("age", "unknown"),
        gender=ctx.get("gender", "unknown"),
        conditions=json.dumps(assessment.get("primary_conditions", [])),
        medications=json.dumps(ctx.get("medications", [])),
        allergies=json.dumps(ctx.get("allergies", [])),
        duration_weeks=duration,
    )

    try:
        response = _llm("gemini-2.0-flash", temperature=0.1).invoke([HumanMessage(content=prompt)])
        plan_json = _safe_json(response.content)
    except Exception as exc:
        logger.error("generate_care_plan LLM failed: %s", exc)
        return {**state, "error": f"Care plan generation failed: {exc}"}

    # Persist to database
    care_plan_id = None
    try:
        from app.models.db import db
        from app.models.care_plan import CarePlan, CarePlanTask

        plan_record = CarePlan(
            id=str(uuid.uuid4()),
            patient_id=state["patient_id"],
            doctor_id=state.get("doctor_id"),
            title=plan_json.get("title", "AI-Generated Care Plan"),
            description=plan_json.get("description"),
            status="active",
            start_date=date.today(),
            goals={
                "goals": plan_json.get("goals", []),
                "milestones": plan_json.get("milestones", []),
                "success_metrics": plan_json.get("success_metrics", []),
                "education_topics": plan_json.get("education_topics", []),
                "follow_up_weeks": plan_json.get("follow_up_weeks", 4),
            },
        )
        db.session.add(plan_record)

        for task_data in plan_json.get("tasks", []):
            task = CarePlanTask(
                id=str(uuid.uuid4()),
                care_plan_id=plan_record.id,
                title=task_data.get("title", "Task"),
                description=task_data.get("description"),
                type=task_data.get("type", "reading"),
                frequency=task_data.get("frequency", "daily"),
                time_of_day=task_data.get("time_of_day", "anytime"),
                status="pending",
            )
            db.session.add(task)

        db.session.commit()
        care_plan_id = plan_record.id
        logger.info("CarePlanAgent: saved care plan %s", care_plan_id)
    except Exception as exc:
        logger.error("CarePlanAgent: DB save failed: %s", exc)
        try:
            from app.models.db import db
            db.session.rollback()
        except Exception:
            pass

    return {**state, "care_plan_json": plan_json, "care_plan_id": care_plan_id}


def schedule_followup(state: CarePlanState) -> CarePlanState:
    """Node 3: Book the next follow-up appointment using scheduling tools."""
    plan_json = state.get("care_plan_json", {})
    follow_up_weeks = plan_json.get("follow_up_weeks", 4)
    patient_id = state.get("patient_id")
    doctor_id = state.get("doctor_id")

    appt_id = None
    if doctor_id and patient_id:
        try:
            from app.agents.tools.scheduling import book_appointment

            # Schedule follow-up at follow_up_weeks from now (noon UTC)
            follow_up_dt = (
                datetime.now(timezone.utc) + timedelta(weeks=follow_up_weeks)
            ).replace(hour=12, minute=0, second=0, microsecond=0)

            result = book_appointment.invoke({
                "patient_id": patient_id,
                "doctor_id": doctor_id,
                "start_time": follow_up_dt.isoformat(),
                "type": "in-person",
                "reason": f"Care plan follow-up: {plan_json.get('title', '')}",
                "duration_minutes": 30,
            })
            if result.get("success"):
                appt_id = result["appointment_id"]
                logger.info("CarePlanAgent: follow-up appointment booked %s", appt_id)
        except Exception as exc:
            logger.warning("CarePlanAgent: schedule_followup failed: %s", exc)

    return {**state, "follow_up_appointment_id": appt_id}


def generate_patient_education(state: CarePlanState) -> CarePlanState:
    """Node 4: Create condition-specific patient education content."""
    ctx = state.get("patient_context", {})
    conditions = (
        state.get("state_assessment", {}).get("primary_conditions")
        or ctx.get("diagnoses", [])
    )

    education_by_condition: dict = {}
    for condition in conditions[:3]:  # cap at 3
        try:
            prompt = PATIENT_EDUCATION_PROMPT.format(
                condition=condition,
                age=ctx.get("age", "adult"),
            )
            response = _llm("gemini-2.0-flash").invoke([HumanMessage(content=prompt)])
            edu = _safe_json(response.content)
            education_by_condition[condition] = edu
        except Exception as exc:
            logger.warning("CarePlanAgent: education gen failed for %s: %s", condition, exc)

    return {**state, "education_content": education_by_condition}


def track_adherence(state: CarePlanState) -> CarePlanState:
    """Node 5: Measure patient adherence to active care plan."""
    patient_id = state.get("patient_id")
    plan_id = state.get("plan_id")

    completed_tasks: list = []
    missed_tasks: list = []
    medication_fills: str = "No fill data available"

    # Query task completion
    try:
        from app.models.care_plan import CarePlanTask, CarePlan
        if plan_id:
            tasks = CarePlanTask.query.filter_by(care_plan_id=plan_id).all()
        else:
            # Find active care plan
            plan = CarePlan.query.filter_by(patient_id=patient_id, status="active").first()
            tasks = CarePlanTask.query.filter_by(care_plan_id=str(plan.id)).all() if plan else []

        for t in tasks:
            entry = {"title": t.title, "type": t.type, "status": t.status}
            if t.status == "completed":
                completed_tasks.append(entry)
            elif t.status in ("pending", "skipped"):
                missed_tasks.append(entry)
    except Exception as exc:
        logger.warning("CarePlanAgent: task query failed: %s", exc)

    # Appointment adherence
    appt_history = state.get("patient_context", {}).get("appointment_history", [])
    attended = [a for a in appt_history if a.get("status") in ("completed", "confirmed")]
    missed_appts = [a for a in appt_history if a.get("status") in ("no-show", "cancelled")]

    plan_data = state.get("patient_context", {}).get("active_care_plan") or {}

    prompt = ADHERENCE_ANALYSIS_PROMPT.format(
        care_plan=json.dumps(plan_data, indent=2),
        days=30,
        completed_tasks=json.dumps(completed_tasks),
        missed_tasks=json.dumps(missed_tasks),
        appointment_adherence=json.dumps({
            "attended": len(attended),
            "missed": len(missed_appts),
        }),
        medication_fills=medication_fills,
    )

    try:
        response = _llm("gemini-2.0-flash").invoke([HumanMessage(content=prompt)])
        analysis = _safe_json(response.content)
    except Exception as exc:
        logger.error("CarePlanAgent: adherence analysis failed: %s", exc)
        analysis = {
            "overall_adherence_pct": 0,
            "deviations": [],
            "on_track": False,
            "requires_plan_adjustment": False,
            "summary": "Analysis unavailable.",
        }

    return {
        **state,
        "adherence_analysis": analysis,
        "deviations": analysis.get("deviations", []),
    }


def detect_deviation(state: CarePlanState) -> CarePlanState:
    """Node 6: Determine if deviations are significant enough to act on."""
    analysis = state.get("adherence_analysis", {})
    # Pass-through — routing logic handled in the conditional edge
    return {**state, "adherence_analysis": analysis}


def adjust_care_plan(state: CarePlanState) -> CarePlanState:
    """Node 7: Revise care plan when patient is significantly off-track."""
    analysis = state.get("adherence_analysis", {})
    plan_data = state.get("patient_context", {}).get("active_care_plan") or {}
    feedback = state.get("patient_feedback", "")

    prompt = ADJUST_CARE_PLAN_PROMPT.format(
        current_plan=json.dumps(plan_data, indent=2),
        adherence_analysis=json.dumps(analysis, indent=2),
        patient_feedback=feedback,
    )

    try:
        response = _llm("gemini-2.0-flash").invoke([HumanMessage(content=prompt)])
        adjustments = _safe_json(response.content)
    except Exception as exc:
        logger.error("CarePlanAgent: adjust_care_plan failed: %s", exc)
        adjustments = {"adjustment_summary": "Adjustment unavailable.", "adjustments": []}

    return {**state, "plan_adjustments": adjustments}


def send_reminder(state: CarePlanState) -> CarePlanState:
    """Node 8: Send adherence reminder for non-compliant patients."""
    patient_id = state.get("patient_id")
    analysis = state.get("adherence_analysis", {})
    deviations = state.get("deviations", [])

    sent: list[str] = []
    if patient_id and deviations:
        try:
            from app.tasks.notification_tasks import send_notification_async
            body_lines = ["Your care plan check-in:"]
            for d in deviations[:3]:
                body_lines.append(f"• {d.get('description', '')}")
            body_lines.append(
                f"\nOverall adherence: {analysis.get('overall_adherence_pct', 0):.0f}%"
            )

            send_notification_async(
                user_id=patient_id,
                title="Care Plan Check-In",
                body="\n".join(body_lines),
                notification_type="care_plan_reminder",
                priority="normal",
                action_url="/patient/care-plan",
            )
            sent.append("care_plan_reminder")
            logger.info("CarePlanAgent: adherence reminder sent to %s", patient_id)
        except Exception as exc:
            logger.warning("CarePlanAgent: reminder send failed: %s", exc)

    return {**state, "notifications_sent": sent}


def generate_progress_report(state: CarePlanState) -> CarePlanState:
    """Node 9: Create a structured progress report for patient + physician."""
    plan_data = state.get("patient_context", {}).get("active_care_plan") or {}
    analysis = state.get("adherence_analysis", {})

    prompt = PROGRESS_REPORT_PROMPT.format(
        patient_id=state.get("patient_id", ""),
        period_weeks=4,
        plan_title=plan_data.get("title", "Care Plan"),
        adherence=json.dumps(analysis, indent=2),
        goals_progress=json.dumps(plan_data.get("goals", {}), indent=2),
        clinical_notes="N/A",
        report_date=datetime.now(timezone.utc).date().isoformat(),
    )

    try:
        response = _llm("gemini-2.0-flash").invoke([HumanMessage(content=prompt)])
        report = _safe_json(response.content)
    except Exception as exc:
        logger.error("CarePlanAgent: progress_report failed: %s", exc)
        report = {"report_date": str(date.today()), "summary": "Report unavailable."}

    return {**state, "progress_report": report}


# ─────────────────────────────────────────────────────────────────────────────
# Routing logic
# ─────────────────────────────────────────────────────────────────────────────

def _route_after_deviation(state: CarePlanState) -> str:
    analysis = state.get("adherence_analysis", {})
    if analysis.get("requires_plan_adjustment"):
        return "adjust_care_plan"
    elif not analysis.get("on_track"):
        return "send_reminder"
    else:
        return "generate_progress_report"


# ─────────────────────────────────────────────────────────────────────────────
# Graph construction
# ─────────────────────────────────────────────────────────────────────────────

def build_followup_graph(mode: str = "generate") -> StateGraph:
    """
    Build the care plan graph.

    mode="generate" : START → assess → generate → schedule → education → END
    mode="track"    : START → assess → track → detect → [adjust|remind] → report → END
    """
    from langgraph.graph import START

    graph = StateGraph(CarePlanState)

    graph.add_node("assess_patient_state", assess_patient_state)
    graph.add_node("generate_care_plan", generate_care_plan)
    graph.add_node("schedule_followup", schedule_followup)
    graph.add_node("generate_patient_education", generate_patient_education)
    graph.add_node("track_adherence", track_adherence)
    graph.add_node("detect_deviation", detect_deviation)
    graph.add_node("adjust_care_plan", adjust_care_plan)
    graph.add_node("send_reminder", send_reminder)
    graph.add_node("generate_progress_report", generate_progress_report)

    # Common: always start at assess
    graph.add_edge(START, "assess_patient_state")

    if mode == "generate":
        # assess → generate → schedule → education → END
        graph.add_edge("assess_patient_state", "generate_care_plan")
        graph.add_edge("generate_care_plan", "schedule_followup")
        graph.add_edge("schedule_followup", "generate_patient_education")
        graph.add_edge("generate_patient_education", END)

        # Stubs so graph validates (unreachable in generate mode)
        graph.add_edge("track_adherence", "detect_deviation")
        graph.add_conditional_edges(
            "detect_deviation",
            _route_after_deviation,
            {
                "adjust_care_plan": "adjust_care_plan",
                "send_reminder": "send_reminder",
                "generate_progress_report": "generate_progress_report",
            },
        )
        graph.add_edge("adjust_care_plan", "send_reminder")
        graph.add_edge("send_reminder", "generate_progress_report")
        graph.add_edge("generate_progress_report", END)
    else:
        # assess → track → detect → [adjust|remind] → report → END
        graph.add_edge("assess_patient_state", "track_adherence")
        graph.add_edge("track_adherence", "detect_deviation")
        graph.add_conditional_edges(
            "detect_deviation",
            _route_after_deviation,
            {
                "adjust_care_plan": "adjust_care_plan",
                "send_reminder": "send_reminder",
                "generate_progress_report": "generate_progress_report",
            },
        )
        graph.add_edge("adjust_care_plan", "send_reminder")
        graph.add_edge("send_reminder", "generate_progress_report")
        graph.add_edge("generate_progress_report", END)

        # Stubs for generate nodes (unreachable in track mode)
        graph.add_edge("generate_care_plan", "schedule_followup")
        graph.add_edge("schedule_followup", "generate_patient_education")
        graph.add_edge("generate_patient_education", END)

    return graph


# ─────────────────────────────────────────────────────────────────────────────
# Public entry points
# ─────────────────────────────────────────────────────────────────────────────

def run_generate_care_plan(
    patient_id: str,
    doctor_id: Optional[str] = None,
    duration_weeks: int = 8,
    patient_context: Optional[dict] = None,
) -> dict:
    """Generate a new care plan for a patient (mode=generate)."""
    graph = build_followup_graph(mode="generate")
    compiled = graph.compile()

    initial_state: CarePlanState = {
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "mode": "generate",
        "duration_weeks": duration_weeks,
        "patient_context": patient_context or {},
        "notifications_sent": [],
    }

    try:
        final = compiled.invoke(initial_state)
        return {
            "success": True,
            "care_plan_id": final.get("care_plan_id"),
            "care_plan": final.get("care_plan_json"),
            "education_content": final.get("education_content", {}),
            "follow_up_appointment_id": final.get("follow_up_appointment_id"),
            "state_assessment": final.get("state_assessment"),
        }
    except Exception as exc:
        logger.exception("run_generate_care_plan failed: %s", exc)
        return {"success": False, "error": str(exc)}


def run_track_adherence(
    patient_id: str,
    plan_id: Optional[str] = None,
    patient_feedback: str = "",
) -> dict:
    """Track adherence for an existing care plan (mode=track)."""
    graph = build_followup_graph(mode="track")
    compiled = graph.compile()

    initial_state: CarePlanState = {
        "patient_id": patient_id,
        "plan_id": plan_id,
        "mode": "track",
        "patient_feedback": patient_feedback,
        "notifications_sent": [],
        "patient_context": {},
    }

    try:
        final = compiled.invoke(initial_state)
        return {
            "success": True,
            "adherence_analysis": final.get("adherence_analysis"),
            "progress_report": final.get("progress_report"),
            "plan_adjustments": final.get("plan_adjustments"),
            "notifications_sent": final.get("notifications_sent", []),
        }
    except Exception as exc:
        logger.exception("run_track_adherence failed: %s", exc)
        return {"success": False, "error": str(exc)}
