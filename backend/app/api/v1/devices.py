"""
devices.py — VitalMind IoT Device Registration & Vitals Ingestion API

Endpoints:
  POST /api/v1/devices/register
      Register a new IoT device for a patient. Returns a device token.

  GET  /api/v1/devices/patient/<patient_id>
      List all active devices for a patient.

  DELETE /api/v1/devices/<device_id>
      Deactivate a device.

  POST /api/v1/devices/<device_id>/vitals
      Ingest a vitals reading from an IoT device (device-token authenticated).
"""

import logging
from flask import Blueprint, request, jsonify

from app.api.v1.auth import token_required
from app.services.vitals_service import VitalsService

logger = logging.getLogger(__name__)

bp = Blueprint("devices", __name__, url_prefix="/api/v1/devices")


# ─── Register device ──────────────────────────────────────────────────────────

@bp.route("/register", methods=["POST"])
@token_required
def register_device(current_user):
    """
    Register a new IoT device.
    ---
    tags: [Devices]
    security:
      - Bearer: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [device_identifier, device_type]
            properties:
              patient_id:
                type: string
                description: Patient UUID (required for doctor/admin; auto-filled for patient)
              device_identifier:
                type: string
                description: Unique MAC address or serial number
                example: "AA:BB:CC:DD:EE:FF"
              device_type:
                type: string
                example: "smartwatch"
              brand:
                type: string
                example: "Apple"
              model:
                type: string
                example: "Watch Series 9"
    responses:
      201:
        description: Device registered. Returns device_id and device_token.
    """
    data = request.get_json() or {}

    # Resolve patient_id
    patient_id = data.get("patient_id")
    if not patient_id:
        if current_user.role.name == "patient":
            patient_id = str(current_user.id)
        else:
            return jsonify({"message": "patient_id is required"}), 400

    if current_user.role.name == "patient" and str(current_user.id) != patient_id:
        return jsonify({"message": "Unauthorized"}), 403

    if not data.get("device_identifier"):
        return jsonify({"message": "device_identifier is required"}), 400

    try:
        device, token = VitalsService.register_device(patient_id, data)
        return jsonify({
            "message": "Device registered successfully",
            "device_id": str(device.id),
            "device_type": device.device_type,
            "device_identifier": device.device_identifier,
            "device_token": token,
            "warning": "Store the device_token securely — it will not be shown again.",
        }), 201

    except ValueError as exc:
        return jsonify({"message": str(exc)}), 409
    except Exception as exc:
        logger.exception("Device registration failed: %s", exc)
        return jsonify({"message": "Device registration failed", "error": str(exc)}), 500


# ─── List devices ─────────────────────────────────────────────────────────────

@bp.route("/patient/<string:patient_id>", methods=["GET"])
@token_required
def list_patient_devices(current_user, patient_id):
    """
    List active IoT devices for a patient.
    ---
    tags: [Devices]
    security:
      - Bearer: []
    """
    if current_user.role.name == "patient" and str(current_user.id) != patient_id:
        return jsonify({"message": "Unauthorized"}), 403

    devices = VitalsService.get_patient_devices(patient_id)
    return jsonify([
        {
            "id": str(d.id),
            "device_type": d.device_type,
            "device_identifier": d.device_identifier,
            "brand": d.brand,
            "model": d.model,
            "last_sync": d.last_sync.isoformat() if d.last_sync else None,
            "is_active": d.is_active,
        }
        for d in devices
    ]), 200


# ─── Deactivate device ────────────────────────────────────────────────────────

@bp.route("/<string:device_id>", methods=["DELETE"])
@token_required
def deactivate_device(current_user, device_id):
    """
    Deactivate a registered device.
    ---
    tags: [Devices]
    security:
      - Bearer: []
    """
    patient_id = str(current_user.id) if current_user.role.name == "patient" else request.args.get("patient_id")
    if not patient_id:
        return jsonify({"message": "patient_id query param required for doctor/admin"}), 400

    success = VitalsService.deactivate_device(device_id, patient_id)
    if not success:
        return jsonify({"message": "Device not found or already inactive"}), 404
    return jsonify({"message": "Device deactivated"}), 200


# ─── Vitals ingestion from IoT device ─────────────────────────────────────────

@bp.route("/<string:device_id>/vitals", methods=["POST"])
def ingest_device_vitals(device_id):
    """
    Ingest vitals from an IoT device.
    No user JWT needed — authenticated by device_token in the request body.
    ---
    tags: [Devices]
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [device_token, vitals]
            properties:
              device_token:
                type: string
                description: Token obtained during device registration
              vitals:
                type: object
                description: Vitals payload
                example:
                  heart_rate: 72
                  spo2: 98.5
                  systolic_bp: 120
                  diastolic_bp: 80
                  temperature: 37.1
              timestamp:
                type: string
                format: date-time
                description: Optional ISO8601 reading timestamp
    responses:
      200:
        description: Vitals accepted and stored
      401:
        description: Invalid or missing device token
      422:
        description: Payload rejected — no valid vitals fields
    """
    data = request.get_json() or {}
    device_token = data.get("device_token", "")
    raw_vitals = data.get("vitals", {})

    if not device_token:
        return jsonify({"message": "device_token is required"}), 401

    if not raw_vitals:
        return jsonify({"message": "vitals payload is required"}), 400

    # Optional explicit timestamp
    timestamp = None
    if data.get("timestamp"):
        try:
            from datetime import datetime
            timestamp = datetime.fromisoformat(data["timestamp"])
        except ValueError:
            return jsonify({"message": "Invalid timestamp format — use ISO 8601"}), 400

    try:
        result = VitalsService.ingest_device_vitals(
            device_id=device_id,
            token=device_token,
            raw_payload=raw_vitals,
            timestamp=timestamp,
        )
    except PermissionError as exc:
        return jsonify({"message": str(exc)}), 401
    except Exception as exc:
        logger.exception("Vitals ingestion error for device %s: %s", device_id, exc)
        return jsonify({"message": "Ingestion failed", "error": str(exc)}), 500

    if result["status"] == "rejected":
        return jsonify({"message": result["reason"], "warnings": result["warnings"]}), 422

    return jsonify({
        "status": "accepted",
        "vitals_stored": result["vitals_stored"],
        "timestamp": result["timestamp"],
        "warnings": result.get("warnings", []),
    }), 200


# ─── Manual vitals entry ──────────────────────────────────────────────────────

@bp.route("/vitals/manual", methods=["POST"])
@token_required
def ingest_manual_vitals(current_user):
    """
    Manually enter vitals (no device required).
    ---
    tags: [Devices]
    security:
      - Bearer: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              heart_rate: {type: number}
              spo2: {type: number}
              systolic_bp: {type: number}
              diastolic_bp: {type: number}
              temperature: {type: number}
              respiratory_rate: {type: number}
              blood_glucose: {type: number}
              weight: {type: number}
    responses:
      200:
        description: Manual vitals stored
    """
    data = request.get_json() or {}
    # Resolve patient profile
    if current_user.role.name == "patient":
        from app.models.patient import PatientProfile
        profile = PatientProfile.query.filter_by(user_id=current_user.id).first()
        if not profile:
            return jsonify({"message": "Patient profile not found"}), 404
        patient_id = str(profile.id)
    else:
        patient_id = data.get("patient_id")

    if not patient_id:
        return jsonify({"message": "patient_id required"}), 400

    try:
        result = VitalsService.ingest_manual_vitals(patient_id=patient_id, raw_payload=data)
    except Exception as exc:
        logger.exception("Manual vitals ingestion error: %s", exc)
        return jsonify({"message": "Failed to store vitals", "error": str(exc)}), 500

    if result["status"] == "rejected":
        return jsonify({"message": result["reason"], "warnings": result["warnings"]}), 422

    return jsonify({
        "status": "accepted",
        "vitals_stored": result["vitals_stored"],
        "timestamp": result["timestamp"],
        "warnings": result.get("warnings", []),
    }), 200
