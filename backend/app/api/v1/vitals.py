"""
vitals.py — VitalMind Vitals Query API

Endpoints:
  GET /api/v1/vitals/<patient_id>/current
      Latest vitals (Redis → InfluxDB → Postgres fallback chain)

  GET /api/v1/vitals/<patient_id>/history
      Time-series history from InfluxDB
      Query params: hours (int, default 24), field (str, optional)

  GET /api/v1/vitals/<patient_id>/stats
      Aggregate stats (mean/min/max/stddev) for a specific vital field
      Query params: field (required), hours (int, default 24)

  GET /api/v1/vitals/<patient_id>/audit
      PostgreSQL audit trail of vitals readings (paginated)
"""

import logging
from typing import Optional, Any
from flask import Blueprint, request, jsonify

from app.api.v1.auth import token_required
from app.services.vitals_service import VitalsService

logger = logging.getLogger(__name__)

bp = Blueprint("vitals", __name__, url_prefix="/api/v1/vitals")

VALID_FIELDS = {
    "heart_rate", "spo2", "systolic_bp", "diastolic_bp",
    "temperature_c", "respiratory_rate", "blood_glucose_mgdl", "weight_kg",
}


def _resolve_patient_id(current_user, provided_id: str) -> tuple[Optional[str], Optional[str]]:
    """
    Resolve the mapping between User ID and Patient Profile ID.
    Returns (resolved_patient_profile_id, error_message).
    """
    from app.models.patient import PatientProfile
    
    # If it's a patient, they can only access their own profile
    if current_user.role.name == "patient":
        # Check if they provided their own USER ID or their own PROFILE ID
        profile = PatientProfile.query.filter_by(user_id=current_user.id).first()
        if not profile:
            return None, "Patient profile not found"
            
        if provided_id == str(current_user.id) or provided_id == str(profile.id):
            return str(profile.id), None
        return None, "Unauthorized access"
    
    # If it's a doctor/admin, we trust the provided ID but check if it's a USER ID needing resolution
    profile = PatientProfile.query.get(provided_id)
    if profile:
        return str(profile.id), None
        
    # Maybe it's a user ID?
    profile = PatientProfile.query.filter_by(user_id=provided_id).first()
    if profile:
        return str(profile.id), None
        
    return None, "Patient not found"


# ─── Current vitals ───────────────────────────────────────────────────────────

@bp.route("/<string:patient_id>/current", methods=["GET"])
@token_required
def get_current_vitals(current_user, patient_id):
    """Get the most recent vitals snapshot for a patient."""
    resolved_id, error = _resolve_patient_id(current_user, patient_id)
    if error:
        return jsonify({"message": error}), 403 if "Unauthorized" in error else 404

    data = VitalsService.get_current_vitals(resolved_id)
    return jsonify(data), 200


# ─── Vitals history ───────────────────────────────────────────────────────────

@bp.route("/<string:patient_id>/history", methods=["GET"])
@token_required
def get_vitals_history(current_user, patient_id):
    """Get time-series vitals history for a patient."""
    resolved_id, error = _resolve_patient_id(current_user, patient_id)
    if error:
        return jsonify({"message": error}), 403 if "Unauthorized" in error else 404

    try:
        hours = int(request.args.get("hours", 24))
        hours = max(1, min(hours, 720))  # Cap at 30 days
    except ValueError:
        return jsonify({"message": "hours must be an integer"}), 400

    field = request.args.get("field")
    if field and field not in VALID_FIELDS:
        return jsonify({
            "message": f"Invalid field. Valid fields: {sorted(VALID_FIELDS)}"
        }), 400

    history = VitalsService.get_vitals_history(resolved_id, hours=hours, field=field)

    # Fallback to PostgreSQL audit if InfluxDB returned nothing
    if not history:
        history = VitalsService.get_postgres_history(resolved_id)

    return jsonify({
        "patient_id": resolved_id,
        "hours": hours,
        "field": field,
        "count": len(history),
        "data": history,
    }), 200


# ─── Aggregate stats ──────────────────────────────────────────────────────────

@bp.route("/<string:patient_id>/stats", methods=["GET"])
@token_required
def get_vitals_stats(current_user, patient_id):
    """Get aggregate statistics for a vital field."""
    resolved_id, error = _resolve_patient_id(current_user, patient_id)
    if error:
        return jsonify({"message": error}), 403 if "Unauthorized" in error else 404

    field = request.args.get("field")
    if not field:
        return jsonify({"message": "field query param is required"}), 400
    if field not in VALID_FIELDS:
        return jsonify({
            "message": f"Invalid field. Valid fields: {sorted(VALID_FIELDS)}"
        }), 400

    try:
        hours = int(request.args.get("hours", 24))
        hours = max(1, min(hours, 720))
    except ValueError:
        return jsonify({"message": "hours must be an integer"}), 400

    stats = VitalsService.get_vitals_stats(resolved_id, field=field, hours=hours)
    return jsonify({
        "patient_id": resolved_id,
        "field": field,
        "hours": hours,
        "stats": stats,
    }), 200


# ─── PostgreSQL audit trail ───────────────────────────────────────────────────

@bp.route("/<string:patient_id>/audit", methods=["GET"])
@token_required
def get_vitals_audit(current_user, patient_id):
    """Get the PostgreSQL audit trail of vitals readings."""
    resolved_id, error = _resolve_patient_id(current_user, patient_id)
    if error:
        return jsonify({"message": error}), 403 if "Unauthorized" in error else 404

    try:
        limit = int(request.args.get("limit", 50))
        limit = max(1, min(limit, 500))
    except ValueError:
        return jsonify({"message": "limit must be an integer"}), 400

    readings = VitalsService.get_postgres_history(resolved_id, limit=limit)
    return jsonify({
        "patient_id": resolved_id,
        "count": len(readings),
        "readings": readings,
    }), 200
