"""
appointments.py — Complete Appointment REST API (Step 22)

Endpoints
---------
POST   /api/v1/appointments/                         Create / book appointment
GET    /api/v1/appointments/patient/<patient_id>     Patient's appointments
GET    /api/v1/appointments/doctor/<doctor_id>       Doctor's appointments
GET    /api/v1/appointments/<appointment_id>         Single appointment
PUT    /api/v1/appointments/<appointment_id>/cancel  Cancel
PUT    /api/v1/appointments/<appointment_id>/reschedule  Reschedule
PUT    /api/v1/appointments/<appointment_id>/status  Update status (no-show, complete…)
GET    /api/v1/appointments/availability/<doctor_id>/<date>  Available slots
"""

import logging
from datetime import datetime

from flask import Blueprint, request, jsonify

from app.api.v1.auth import token_required
from app.services.appointment_service import AppointmentService
from app.middleware.hipaa_audit import audit_log

logger = logging.getLogger(__name__)

bp = Blueprint("appointments", __name__, url_prefix="/api/v1/appointments")


# ─────────────────────────────────────────────────────────────────────────────
# POST /
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/", methods=["POST"])
@token_required
@audit_log(action="create", resource_type="appointment")
def create_appointment(current_user):
    """Book a new appointment (conflict-checked)."""
    data = request.get_json(silent=True) or {}

    from app.models.patient import PatientProfile
    
    # Patients can only book for themselves
    if current_user.role.name == "patient":
        if str(data.get("patient_id")) != str(current_user.id):
            return jsonify({"message": "Unauthorized"}), 403
        
        # The frontend sends the User ID, but the database expects PatientProfile ID.
        patient_profile = PatientProfile.query.filter_by(user_id=current_user.id).first()
        if not patient_profile:
            return jsonify({"message": "Patient profile not found"}), 404
        data["patient_id"] = str(patient_profile.id)

    elif current_user.role.name == "doctor":
        # A doctor might send a User ID to create an appointment. If so we map it. 
        # But if it's already a Profile ID it will just return None, so we should allow it.
        pass

    try:
        appt = AppointmentService.create_appointment(data)
        return jsonify({
            "message": "Appointment booked successfully",
            "appointment": AppointmentService.to_dict(appt),
        }), 201
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 409
    except Exception as exc:
        import traceback
        logger.exception("create_appointment: %s", exc)
        return jsonify({"message": "Internal server error", "error": str(exc), "trace": traceback.format_exc()}), 500


# ─────────────────────────────────────────────────────────────────────────────
# GET /patient/<patient_id_or_user_id>
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/patient/<string:patient_id>", methods=["GET"])
@token_required
@audit_log(action="read_all", resource_type="appointment")
def get_patient_appointments(current_user, patient_id):
    """List all appointments for a patient, ordered by start_time desc."""
    from app.models.patient import PatientProfile
    
    if current_user.role.name == "patient" and str(current_user.id) != patient_id:
        return jsonify({"message": "Unauthorized"}), 403

    # Resolve User ID -> PatientProfile ID
    patient_profile = PatientProfile.query.filter_by(user_id=patient_id).first()
    resolved_id = str(patient_profile.id) if patient_profile else patient_id

    limit = int(request.args.get("limit", 50))
    appointments = AppointmentService.get_patient_appointments(resolved_id, limit=limit)
    return jsonify([AppointmentService.to_dict(a) for a in appointments]), 200


# ─────────────────────────────────────────────────────────────────────────────
# GET /doctor/<doctor_id_or_user_id>
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/doctor/<string:doctor_id>", methods=["GET"])
@token_required
@audit_log(action="read_doctor", resource_type="appointment")
def get_doctor_appointments(current_user, doctor_id):
    """List all appointments for a doctor, ordered by start_time asc."""
    from app.models.doctor import DoctorProfile
    
    if current_user.role.name == "doctor" and str(current_user.id) != doctor_id:
        return jsonify({"message": "Unauthorized"}), 403

    doctor_profile = DoctorProfile.query.filter_by(user_id=doctor_id).first()
    resolved_id = str(doctor_profile.id) if doctor_profile else doctor_id

    limit = int(request.args.get("limit", 50))
    appointments = AppointmentService.get_doctor_appointments(resolved_id, limit=limit)
    return jsonify([AppointmentService.to_dict(a) for a in appointments]), 200


# ─────────────────────────────────────────────────────────────────────────────
# GET /<appointment_id>
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/<string:appointment_id>", methods=["GET"])
@token_required
@audit_log(action="read", resource_type="appointment")
def get_appointment(current_user, appointment_id):
    appt = AppointmentService.get_appointment(appointment_id)
    if not appt:
        return jsonify({"message": "Appointment not found"}), 404

    # Auth check: patient can only see their own
    if current_user.role.name == "patient":
        from app.models.patient import PatientProfile
        patient_profile = PatientProfile.query.filter_by(user_id=current_user.id).first()
        if not patient_profile or str(appt.patient_id) != str(patient_profile.id):
            return jsonify({"message": "Unauthorized"}), 403

    return jsonify(AppointmentService.to_dict(appt)), 200


# ─────────────────────────────────────────────────────────────────────────────
# PUT /<appointment_id>/cancel
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/<string:appointment_id>/cancel", methods=["PUT"])
@token_required
@audit_log(action="cancel", resource_type="appointment")
def cancel_appointment(current_user, appointment_id):
    """Cancel an appointment. Both patient and doctor can cancel."""
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "")

    try:
        appt = AppointmentService.cancel_appointment(
            appointment_id=appointment_id,
            reason=reason,
            cancelled_by=str(current_user.id),
        )
        if not appt:
            return jsonify({"message": "Appointment not found"}), 404
        return jsonify({
            "message": "Appointment cancelled",
            "appointment": AppointmentService.to_dict(appt),
        }), 200
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    except Exception as exc:
        logger.exception("cancel_appointment: %s", exc)
        return jsonify({"message": "Internal server error"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# PUT /<appointment_id>/reschedule
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/<string:appointment_id>/reschedule", methods=["PUT"])
@token_required
@audit_log(action="reschedule", resource_type="appointment")
def reschedule_appointment(current_user, appointment_id):
    """Reschedule an appointment to a new start_time (conflict-checked)."""
    data = request.get_json(silent=True) or {}
    new_start_raw = data.get("new_start_time") or data.get("start_time")
    if not new_start_raw:
        return jsonify({"message": "new_start_time is required"}), 400

    try:
        new_start = datetime.fromisoformat(new_start_raw.replace("Z", "+00:00"))
        appt = AppointmentService.reschedule_appointment(
            appointment_id=appointment_id,
            new_start_time=new_start,
            reason=data.get("reason"),
        )
        if not appt:
            return jsonify({"message": "Appointment not found"}), 404
        return jsonify({
            "message": "Appointment rescheduled",
            "appointment": AppointmentService.to_dict(appt),
        }), 200
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 409
    except Exception as exc:
        logger.exception("reschedule_appointment: %s", exc)
        return jsonify({"message": "Internal server error"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# PUT /<appointment_id>/status
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/<string:appointment_id>/status", methods=["PUT"])
@token_required
@audit_log(action="update_status", resource_type="appointment")
def update_appointment_status(current_user, appointment_id):
    """Update status: scheduled → confirmed, completed, no-show, etc."""
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if not status:
        return jsonify({"message": "status is required"}), 400

    appt = AppointmentService.update_appointment_status(appointment_id, status)
    if not appt:
        return jsonify({"message": "Appointment not found"}), 404
    return jsonify({
        "message": "Status updated",
        "appointment": AppointmentService.to_dict(appt),
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# GET /availability/<doctor_id>/<date>
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/availability/<string:doctor_id>/<string:date>", methods=["GET"])
@token_required
@audit_log(action="read_availability", resource_type="appointment")
def get_availability(current_user, doctor_id, date):
    """
    Return hourly time slots for a doctor on a specific date.
    Date format: YYYY-MM-DD

    Response:
        {
            "doctor_id": "...",
            "date": "2024-11-20",
            "slots": [{ "start": "...", "end": "...", "available": true }, ...]
        }
    """
    slot_minutes = int(request.args.get("slot_minutes", 30))
    try:
        date_dt = datetime.strptime(date, "%Y-%m-%d")
        slots = AppointmentService.get_doctor_availability(
            doctor_id=doctor_id,
            date=date_dt,
            slot_minutes=slot_minutes,
        )
        return jsonify({
            "doctor_id": doctor_id,
            "date": date,
            "slot_minutes": slot_minutes,
            "total_slots": len(slots),
            "available_count": sum(1 for s in slots if s["available"]),
            "slots": slots,
        }), 200
    except ValueError as exc:
        return jsonify({"message": f"Invalid date format: {exc}"}), 400
    except Exception as exc:
        logger.exception("get_availability: %s", exc)
        return jsonify({"message": "Internal server error"}), 500
