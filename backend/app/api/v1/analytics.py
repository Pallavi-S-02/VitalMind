"""
analytics.py — REST API for analytics dashboards (Step 25)

Endpoints
---------
GET /api/v1/analytics/patient/<patient_id>          Patient health overview
GET /api/v1/analytics/patient/<patient_id>/vitals   Vitals trend chart data
GET /api/v1/analytics/patient/<patient_id>/meds     Medication adherence stats
GET /api/v1/analytics/doctor/<doctor_id>            Doctor caseload overview
GET /api/v1/analytics/doctor/<doctor_id>/history    Appointment volume chart data
GET /api/v1/analytics/admin/overview                System-level metrics (admin only)
"""

import logging
from flask import Blueprint, request, jsonify
from app.middleware.auth_middleware import require_auth

logger = logging.getLogger(__name__)

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/v1/analytics")


# ─────────────────────────────────────────────────────────────────────────────
# Patient endpoints
# ─────────────────────────────────────────────────────────────────────────────

@analytics_bp.route("/patient/<string:patient_id>", methods=["GET"])
@require_auth
def patient_overview(patient_id: str):
    current_user = getattr(request, "current_user", None)
    if current_user.role.name == "patient" and str(current_user.id) != patient_id:
        return jsonify({"error": "Unauthorized"}), 403
        
    # Resolve Patient Profile ID if a User ID was sent
    from app.models.patient import PatientProfile
    patient_profile = PatientProfile.query.filter_by(user_id=patient_id).first()
    resolved_id = str(patient_profile.id) if patient_profile else patient_id
    
    try:
        from app.services.analytics_service import AnalyticsService
        return jsonify(AnalyticsService.get_patient_overview(resolved_id)), 200
    except Exception as exc:
        logger.exception("patient_overview: %s", exc)
        return jsonify({"error": "Failed to load analytics"}), 500


@analytics_bp.route("/patient/<string:patient_id>/vitals", methods=["GET"])
@require_auth
def patient_vitals_trend(patient_id: str):
    days = int(request.args.get("days", 30))
    from app.models.patient import PatientProfile
    patient_profile = PatientProfile.query.filter_by(user_id=patient_id).first()
    resolved_id = str(patient_profile.id) if patient_profile else patient_id
    
    try:
        from app.services.analytics_service import AnalyticsService
        return jsonify(AnalyticsService.get_patient_vitals_trend(resolved_id, days=days)), 200
    except Exception as exc:
        logger.exception("patient_vitals_trend: %s", exc)
        return jsonify({"error": "Failed to load vitals trend"}), 500


@analytics_bp.route("/patient/<string:patient_id>/meds", methods=["GET"])
@require_auth
def patient_medication_adherence(patient_id: str):
    from app.models.patient import PatientProfile
    patient_profile = PatientProfile.query.filter_by(user_id=patient_id).first()
    resolved_id = str(patient_profile.id) if patient_profile else patient_id
    
    try:
        from app.services.analytics_service import AnalyticsService
        return jsonify(AnalyticsService.get_medication_adherence(resolved_id)), 200
    except Exception as exc:
        logger.exception("patient_medication_adherence: %s", exc)
        return jsonify({"error": "Failed to load medication adherence"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Doctor endpoints
# ─────────────────────────────────────────────────────────────────────────────

@analytics_bp.route("/doctor/<string:doctor_id>", methods=["GET"])
@require_auth
def doctor_overview(doctor_id: str):
    current_user = getattr(request, "current_user", None)
    if current_user.role.name == "doctor" and str(current_user.id) != doctor_id:
        return jsonify({"error": "Unauthorized"}), 403
        
    from app.models.doctor import DoctorProfile
    doctor_profile = DoctorProfile.query.filter_by(user_id=doctor_id).first()
    resolved_id = str(doctor_profile.id) if doctor_profile else doctor_id
    
    try:
        from app.services.analytics_service import AnalyticsService
        return jsonify(AnalyticsService.get_doctor_overview(resolved_id)), 200
    except Exception as exc:
        logger.exception("doctor_overview: %s", exc)
        return jsonify({"error": "Failed to load analytics"}), 500


@analytics_bp.route("/doctor/<string:doctor_id>/history", methods=["GET"])
@require_auth
def doctor_appointment_history(doctor_id: str):
    days = int(request.args.get("days", 30))
    from app.models.doctor import DoctorProfile
    doctor_profile = DoctorProfile.query.filter_by(user_id=doctor_id).first()
    resolved_id = str(doctor_profile.id) if doctor_profile else doctor_id
    
    try:
        from app.services.analytics_service import AnalyticsService
        return jsonify(AnalyticsService.get_doctor_appointment_history(resolved_id, days=days)), 200
    except Exception as exc:
        logger.exception("doctor_appointment_history: %s", exc)
        return jsonify({"error": "Failed to load appointment history"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Admin endpoint
# ─────────────────────────────────────────────────────────────────────────────

@analytics_bp.route("/admin/overview", methods=["GET"])
@require_auth
def admin_overview():
    current_user = getattr(request, "current_user", None)
    if current_user.role != "admin":
        return jsonify({"error": "Admin only"}), 403
    try:
        from app.services.analytics_service import AnalyticsService
        return jsonify(AnalyticsService.get_admin_overview()), 200
    except Exception as exc:
        logger.exception("admin_overview: %s", exc)
        return jsonify({"error": "Failed to load system overview"}), 500
