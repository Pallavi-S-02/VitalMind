"""
telemedicine.py — REST API for VitalMind video consultations (Step 21)

Endpoints
---------
POST /api/v1/telemedicine/rooms/create
    Create or retrieve a Daily room for an appointment.
    Only doctors / admins can invoke this.

POST /api/v1/telemedicine/rooms/<room_name>/join
    Generate a time-limited meeting token for the authenticated user.
    Both patients and doctors call this to enter the room.

POST /api/v1/telemedicine/rooms/<room_name>/end
    Delete the room and mark the appointment completed.
    Only the owning doctor or admin can end a call.

GET  /api/v1/telemedicine/rooms/<room_name>/status
    Return participant count and room metadata.

GET  /api/v1/telemedicine/appointments/<appointment_id>/room
    Convenience: fetch room info directly from an appointment ID.
    Creates the room if it doesn't exist yet.
"""

import logging
from flask import Blueprint, request, jsonify
from app.middleware.auth_middleware import require_auth

logger = logging.getLogger(__name__)

telemedicine_bp = Blueprint("telemedicine", __name__, url_prefix="/api/v1/telemedicine")


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/telemedicine/rooms/create
# ─────────────────────────────────────────────────────────────────────────────

@telemedicine_bp.route("/rooms/create", methods=["POST"])
@require_auth
def create_room():
    """
    Create a Daily.co room for an appointment.

    Request JSON
    ------------
    { "appointment_id": "<uuid>" }

    Response JSON
    -------------
    {
        "room_name":      "vitalmind-a3f8b23c",
        "room_url":       "https://vitalmind.daily.co/vitalmind-a3f8b23c",
        "appointment_id": "<uuid>",
        "created":        true
    }
    """
    current_user = getattr(request, "current_user", None)
    if not current_user:
        return jsonify({"error": "Unauthorized"}), 401

    role = getattr(current_user, "role", "patient")
    if role not in ("doctor", "admin"):
        return jsonify({"error": "Only doctors can create telemedicine rooms"}), 403

    data = request.get_json(silent=True) or {}
    appointment_id = (data.get("appointment_id") or "").strip()

    if not appointment_id:
        return jsonify({"error": "appointment_id is required"}), 400

    # Verify the doctor owns this appointment
    if role == "doctor":
        from app.models.appointment import Appointment
        appt = Appointment.query.filter_by(id=appointment_id).first()
        if not appt:
            return jsonify({"error": "Appointment not found"}), 404
        if str(appt.doctor_id) != str(current_user.id):
            return jsonify({"error": "You do not own this appointment"}), 403

    try:
        from app.services.telemedicine_service import TelemedicineService
        result = TelemedicineService.create_room(
            appointment_id=appointment_id,
            doctor_id=str(current_user.id),
        )
        return jsonify(result), 201 if result.get("created") else 200
    except Exception as exc:
        logger.exception("Telemedicine: create_room failed: %s", exc)
        return jsonify({"error": "Failed to create room", "detail": str(exc)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/telemedicine/rooms/<room_name>/join
# ─────────────────────────────────────────────────────────────────────────────

@telemedicine_bp.route("/rooms/<room_name>/join", methods=["POST"])
@require_auth
def join_room(room_name: str):
    """
    Generate a meeting token for the authenticated user to join a room.

    Response JSON
    -------------
    {
        "token":    "<daily-meeting-token>",
        "room_url": "https://vitalmind.daily.co/...",
        "room_name": "vitalmind-a3f8b23c",
        "is_owner": false,
        "domain":   "vitalmind"
    }
    """
    current_user = getattr(request, "current_user", None)
    if not current_user:
        return jsonify({"error": "Unauthorized"}), 401

    role = getattr(current_user, "role", "patient")
    user_id = str(current_user.id)

    # Construct a display name
    first = getattr(current_user, "first_name", "") or ""
    last = getattr(current_user, "last_name", "") or ""
    user_name = f"{role.title()} {first} {last}".strip() or f"{role.title()} {user_id[:8]}"

    try:
        from app.services.telemedicine_service import TelemedicineService
        result = TelemedicineService.join_room(
            room_name=room_name,
            user_id=user_id,
            user_name=user_name,
            role=role,
        )
        return jsonify(result), 200
    except Exception as exc:
        logger.exception("Telemedicine: join_room failed: %s", exc)
        return jsonify({"error": "Failed to join room"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/telemedicine/rooms/<room_name>/end
# ─────────────────────────────────────────────────────────────────────────────

@telemedicine_bp.route("/rooms/<room_name>/end", methods=["POST"])
@require_auth
def end_room(room_name: str):
    """
    Terminate a room and mark the appointment completed.
    Requires doctor or admin role.

    Request JSON (optional)
    -----------------------
    { "appointment_id": "<uuid>" }   // if omitted, derived from room_name

    Response JSON
    -------------
    { "success": true, "appointment_id": "...", "message": "..." }
    """
    current_user = getattr(request, "current_user", None)
    role = getattr(current_user, "role", "patient") if current_user else "patient"

    if role not in ("doctor", "admin"):
        return jsonify({"error": "Only doctors can end a call"}), 403

    data = request.get_json(silent=True) or {}
    appointment_id = data.get("appointment_id") or room_name.replace("vitalmind-", "")

    try:
        from app.services.telemedicine_service import TelemedicineService
        result = TelemedicineService.end_room(appointment_id=appointment_id)
        return jsonify(result), 200
    except Exception as exc:
        logger.exception("Telemedicine: end_room failed: %s", exc)
        return jsonify({"error": "Failed to end room"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/telemedicine/rooms/<room_name>/status
# ─────────────────────────────────────────────────────────────────────────────

@telemedicine_bp.route("/rooms/<room_name>/status", methods=["GET"])
@require_auth
def room_status(room_name: str):
    """
    Return presence info and room URL.
    """
    data = request.args
    appointment_id = data.get("appointment_id") or room_name.replace("vitalmind-", "")

    try:
        from app.services.telemedicine_service import TelemedicineService
        result = TelemedicineService.get_room_status(appointment_id)
        return jsonify(result), 200
    except Exception as exc:
        logger.exception("Telemedicine: room_status failed: %s", exc)
        return jsonify({"error": "Failed to fetch room status"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/telemedicine/appointments/<appointment_id>/room
# ─────────────────────────────────────────────────────────────────────────────

@telemedicine_bp.route("/appointments/<appointment_id>/room", methods=["GET"])
@require_auth
def get_appointment_room(appointment_id: str):
    """
    Fetch (or create) the room associated with an appointment.
    Creates the room automatically if it doesn't yet exist.
    """
    current_user = getattr(request, "current_user", None)
    role = getattr(current_user, "role", "patient") if current_user else "patient"

    try:
        from app.models.appointment import Appointment
        from app.services.telemedicine_service import TelemedicineService

        appt = Appointment.query.filter_by(id=appointment_id).first()
        if not appt:
            return jsonify({"error": "Appointment not found"}), 404

        # Patients can only access their own appointments
        if role == "patient" and str(appt.patient_id) != str(current_user.id):
            return jsonify({"error": "Unauthorized"}), 403

        # If room already provisioned, return it
        if appt.meeting_link:
            room_name_raw = appt.meeting_link.rstrip("/").split("/")[-1]
            return jsonify({
                "room_name": room_name_raw,
                "room_url": appt.meeting_link,
                "appointment_id": appointment_id,
                "created": False,
            }), 200

        # Auto-create for doctor; patients wait until doctor provisions
        if role in ("doctor", "admin"):
            result = TelemedicineService.create_room(
                appointment_id=appointment_id,
                doctor_id=str(current_user.id),
            )
            return jsonify(result), 201

        return jsonify({
            "error": "Room not yet provisioned. Please ask your doctor to start the call.",
            "appointment_id": appointment_id,
        }), 404

    except Exception as exc:
        logger.exception("Telemedicine: get_appointment_room failed: %s", exc)
        return jsonify({"error": "Failed to fetch room"}), 500
