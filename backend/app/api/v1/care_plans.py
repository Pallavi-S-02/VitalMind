"""
care_plans.py — REST API for Care Plan management (Step 23)

Endpoints
---------
POST   /api/v1/care-plans/generate           Generate a new AI care plan
GET    /api/v1/care-plans/<patient_id>        Get all care plans for a patient
GET    /api/v1/care-plans/plan/<plan_id>      Get single care plan with tasks
PATCH  /api/v1/care-plans/<plan_id>          Doctor edits / approves a plan
GET    /api/v1/care-plans/<plan_id>/track     Run adherence tracking sweep
GET    /api/v1/care-plans/<plan_id>/report    Get latest progress report
POST   /api/v1/care-plans/<plan_id>/tasks/<task_id>/complete  Mark task done
"""

import logging
from datetime import date

from flask import Blueprint, request, jsonify
from app.middleware.auth_middleware import require_auth
from app.middleware.hipaa_audit import audit_log

logger = logging.getLogger(__name__)

care_plans_bp = Blueprint("care_plans", __name__, url_prefix="/api/v1/care-plans")


# ─────────────────────────────────────────────────────────────────────────────
# POST /generate
# ─────────────────────────────────────────────────────────────────────────────

@care_plans_bp.route("/generate", methods=["POST"])
@require_auth
@audit_log(action="create", resource_type="care_plan")
def generate_care_plan():
    """
    Trigger AI care plan generation for a patient.

    Request JSON
    ------------
    {
        "patient_id": "<uuid>",
        "duration_weeks": 8          // optional, default 8
    }
    """
    current_user = getattr(request, "current_user", None)
    if not current_user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    patient_id = data.get("patient_id") or str(current_user.id)
    duration_weeks = int(data.get("duration_weeks", 8))

    doctor_id = None
    if current_user.role in ("doctor", "admin"):
        doctor_id = str(current_user.id)

    # Patients can only generate for themselves
    if current_user.role.name == "patient" and str(current_user.id) != patient_id:
        return jsonify({"error": "Unauthorized"}), 403

    from app.models.patient import PatientProfile
    patient_profile = PatientProfile.query.filter_by(user_id=patient_id).first()
    resolved_id = str(patient_profile.id) if patient_profile else patient_id

    try:
        from app.agents.followup_agent import run_generate_care_plan
        result = run_generate_care_plan(
            patient_id=resolved_id,
            doctor_id=doctor_id,
            duration_weeks=duration_weeks,
            patient_context={"patient_id": patient_id}  # pass original mapped for context lookup if needed inside agent
        )

        if not result.get("success"):
            return jsonify({"error": result.get("error", "Generation failed")}), 500

        return jsonify(result), 201
    except Exception as exc:
        logger.exception("care_plans generate: %s", exc)
        return jsonify({"error": "Internal server error", "detail": str(exc)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# GET /<patient_id>
# ─────────────────────────────────────────────────────────────────────────────

@care_plans_bp.route("/<string:patient_id>", methods=["GET"])
@require_auth
@audit_log(action="read_all", resource_type="care_plan")
def get_patient_care_plans(patient_id: str):
    """List all care plans for a patient."""
    current_user = getattr(request, "current_user", None)
    if current_user.role.name == "patient" and str(current_user.id) != patient_id:
        return jsonify({"error": "Unauthorized"}), 403

    from app.models.patient import PatientProfile
    patient_profile = PatientProfile.query.filter_by(user_id=patient_id).first()
    resolved_id = str(patient_profile.id) if patient_profile else patient_id

    try:
        from app.models.care_plan import CarePlan
        plans = CarePlan.query.filter_by(patient_id=resolved_id).order_by(CarePlan.created_at.desc()).all()
        return jsonify([_serialize_plan(p) for p in plans]), 200
    except Exception as exc:
        logger.error("get_patient_care_plans: %s", exc)
        return jsonify({"error": "Failed to fetch care plans"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# GET /plan/<plan_id>
# ─────────────────────────────────────────────────────────────────────────────

@care_plans_bp.route("/plan/<string:plan_id>", methods=["GET"])
@require_auth
@audit_log(action="read", resource_type="care_plan")
def get_care_plan(plan_id: str):
    """Get a single care plan with its tasks."""
    try:
        from app.models.care_plan import CarePlan, CarePlanTask
        plan = CarePlan.query.filter_by(id=plan_id).first()
        if not plan:
            return jsonify({"error": "Care plan not found"}), 404

        current_user = getattr(request, "current_user", None)
        if current_user.role == "patient" and str(plan.patient_id) != str(current_user.id):
            return jsonify({"error": "Unauthorized"}), 403

        tasks = CarePlanTask.query.filter_by(care_plan_id=plan_id).all()
        result = _serialize_plan(plan)
        result["tasks"] = [_serialize_task(t) for t in tasks]
        return jsonify(result), 200
    except Exception as exc:
        logger.error("get_care_plan: %s", exc)
        return jsonify({"error": "Failed to fetch care plan"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /<plan_id>
# ─────────────────────────────────────────────────────────────────────────────

@care_plans_bp.route("/<string:plan_id>", methods=["PATCH"])
@require_auth
@audit_log(action="update", resource_type="care_plan")
def update_care_plan(plan_id: str):
    """Doctor can edit title, description, goals, status."""
    current_user = getattr(request, "current_user", None)
    if current_user.role not in ("doctor", "admin"):
        return jsonify({"error": "Only doctors can modify care plans"}), 403

    data = request.get_json(silent=True) or {}
    try:
        from app.models.db import db
        from app.models.care_plan import CarePlan
        plan = CarePlan.query.filter_by(id=plan_id).first()
        if not plan:
            return jsonify({"error": "Care plan not found"}), 404

        if "title" in data:
            plan.title = data["title"]
        if "description" in data:
            plan.description = data["description"]
        if "status" in data:
            plan.status = data["status"]
        if "goals" in data:
            plan.goals = {**(plan.goals or {}), **data["goals"]}
        if "end_date" in data:
            plan.end_date = date.fromisoformat(data["end_date"])

        db.session.commit()
        return jsonify({"message": "Care plan updated", "plan": _serialize_plan(plan)}), 200
    except Exception as exc:
        logger.error("update_care_plan: %s", exc)
        return jsonify({"error": "Failed to update care plan"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# GET /<plan_id>/track
# ─────────────────────────────────────────────────────────────────────────────

@care_plans_bp.route("/<string:plan_id>/track", methods=["GET"])
@require_auth
@audit_log(action="track_adherence", resource_type="care_plan")
def track_care_plan(plan_id: str):
    """Run adherence tracking sweep for a care plan."""
    try:
        from app.models.care_plan import CarePlan
        plan = CarePlan.query.filter_by(id=plan_id).first()
        if not plan:
            return jsonify({"error": "Care plan not found"}), 404

        from app.agents.followup_agent import run_track_adherence
        result = run_track_adherence(
            patient_id=str(plan.patient_id),
            plan_id=plan_id,
        )
        return jsonify(result), 200
    except Exception as exc:
        logger.exception("track_care_plan: %s", exc)
        return jsonify({"error": "Tracking failed", "detail": str(exc)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# POST /<plan_id>/tasks/<task_id>/complete
# ─────────────────────────────────────────────────────────────────────────────

@care_plans_bp.route("/<string:plan_id>/tasks/<string:task_id>/complete", methods=["POST"])
@require_auth
@audit_log(action="complete_task", resource_type="care_plan")
def complete_task(plan_id: str, task_id: str):
    """Patient marks a care plan task as completed."""
    try:
        from app.models.db import db
        from app.models.care_plan import CarePlanTask
        task = CarePlanTask.query.filter_by(id=task_id, care_plan_id=plan_id).first()
        if not task:
            return jsonify({"error": "Task not found"}), 404
        task.status = "completed"
        db.session.commit()
        return jsonify({"message": "Task completed", "task": _serialize_task(task)}), 200
    except Exception as exc:
        logger.error("complete_task: %s", exc)
        return jsonify({"error": "Failed to update task"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Serialization helpers
# ─────────────────────────────────────────────────────────────────────────────

def _serialize_plan(plan) -> dict:
    return {
        "id": str(plan.id),
        "patient_id": str(plan.patient_id),
        "doctor_id": str(plan.doctor_id) if plan.doctor_id else None,
        "title": plan.title,
        "description": plan.description,
        "status": plan.status,
        "start_date": plan.start_date.isoformat() if plan.start_date else None,
        "end_date": plan.end_date.isoformat() if plan.end_date else None,
        "goals": plan.goals or {},
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
    }


def _serialize_task(task) -> dict:
    return {
        "id": str(task.id),
        "care_plan_id": str(task.care_plan_id),
        "title": task.title,
        "description": task.description,
        "type": task.type,
        "frequency": task.frequency,
        "time_of_day": task.time_of_day,
        "status": task.status,
        "due_date": task.due_date.isoformat() if task.due_date else None,
    }
