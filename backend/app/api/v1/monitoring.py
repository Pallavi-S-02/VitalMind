"""
monitoring.py — REST API endpoints for the Patient Monitoring Agent.

Endpoints:
  POST /api/v1/monitoring/<patient_id>/run
      Trigger an on-demand monitoring cycle for a specific patient.

  GET  /api/v1/monitoring/<patient_id>/status
      Retrieve the latest monitoring cycle result for a patient.

  GET  /api/v1/monitoring/alerts
      List all active monitoring alerts (with optional filters).

  POST /api/v1/monitoring/alerts/<alert_id>/acknowledge
      Mark a monitoring alert as acknowledged by a clinician.

  GET  /api/v1/monitoring/<patient_id>/news2
      Compute and return the live NEWS2 score for a patient.

  GET  /api/v1/monitoring/<patient_id>/shift-summary
      Generate an SBAR shift handoff summary for a patient.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from flask import Blueprint, jsonify, request

from app.api.v1.auth import token_required

logger = logging.getLogger(__name__)

monitoring_bp = Blueprint("monitoring", __name__, url_prefix="/api/v1/monitoring")


# ─────────────────────────────────────────────────────────────────────────────
# On-demand monitoring cycle
# ─────────────────────────────────────────────────────────────────────────────

@monitoring_bp.route("/<patient_id>/run", methods=["POST"])
@token_required
def run_patient_monitoring(current_user, patient_id: str):
    """
    Trigger an immediate monitoring cycle for a patient.
    ---
    tags:
      - Patient Monitoring
    security:
      - Bearer: []
    parameters:
      - name: patient_id
        in: path
        type: string
        required: true
        description: UUID of the patient to monitor
    requestBody:
      content:
        application/json:
          schema:
            type: object
            properties:
              physician_phone:
                type: string
                description: Attending physician phone (E.164 format) for Level 2 alerts
              specialist_phone:
                type: string
                description: On-call specialist phone for Level 3 emergency alerts
    responses:
      200:
        description: Monitoring cycle result
      403:
        description: Insufficient permissions
      500:
        description: Monitoring agent error
    """
    # Only doctors, nurses, and admins can trigger manual monitoring cycles
    if current_user.role not in ("doctor", "nurse", "admin"):
        # Patients can trigger their own monitoring only
        if current_user.role == "patient" and str(current_user.id) != patient_id:
            return jsonify({"error": "Insufficient permissions to monitor this patient"}), 403

    body = request.get_json(silent=True) or {}
    physician_phone: Optional[str] = body.get("physician_phone")
    specialist_phone: Optional[str] = body.get("specialist_phone")

    try:
        from app.tasks.monitoring_tasks import run_single_patient_monitoring
        result = run_single_patient_monitoring(
            patient_id=patient_id,
            physician_phone=physician_phone,
            specialist_phone=specialist_phone,
        )

        final_response = result.get("final_response") or {}
        error = result.get("error")

        if error:
            return jsonify({
                "success": False,
                "patient_id": patient_id,
                "error": error,
            }), 500

        return jsonify({
            "success": True,
            "patient_id": patient_id,
            "monitoring_result": final_response,
        }), 200

    except Exception as exc:
        logger.error("MonitoringAPI: on-demand cycle failed for patient %s: %s", patient_id, exc)
        return jsonify({"error": "Monitoring cycle failed", "detail": str(exc)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# NEWS2 score endpoint
# ─────────────────────────────────────────────────────────────────────────────

@monitoring_bp.route("/<patient_id>/news2", methods=["GET"])
@token_required
def get_news2_score(current_user, patient_id: str):
    """
    Compute the live NEWS2 early warning score for a patient.
    ---
    tags:
      - Patient Monitoring
    security:
      - Bearer: []
    parameters:
      - name: patient_id
        in: path
        type: string
        required: true
    responses:
      200:
        description: NEWS2 score with component breakdown
      404:
        description: No vitals data available
      500:
        description: Computation error
    """
    if current_user.role not in ("doctor", "nurse", "admin", "patient"):
        return jsonify({"error": "Unauthorized"}), 403

    # Patients can only view their own NEWS2
    if current_user.role == "patient" and str(current_user.id) != patient_id:
        return jsonify({"error": "You can only view your own health scores"}), 403

    try:
        from app.services.vitals_service import VitalsService
        from app.agents.tools.vitals_analysis import calculate_news2_score

        vitals = VitalsService.get_current_vitals(patient_id)
        if not vitals:
            return jsonify({"error": "No current vitals data available for this patient"}), 404

        raw = calculate_news2_score.invoke({
            "heart_rate": vitals.get("heart_rate"),
            "respiratory_rate": vitals.get("respiratory_rate"),
            "spo2": vitals.get("spo2"),
            "systolic_bp": vitals.get("systolic_bp"),
            "temperature_c": vitals.get("temperature_c"),
            "consciousness": vitals.get("consciousness", "A"),
            "supplemental_oxygen": vitals.get("supplemental_oxygen", False),
        })

        news2_data = json.loads(raw)
        return jsonify({
            "patient_id": patient_id,
            "vitals_used": news2_data.get("vitals_used", {}),
            "news2": news2_data,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }), 200

    except Exception as exc:
        logger.error("MonitoringAPI: NEWS2 computation failed for patient %s: %s", patient_id, exc)
        return jsonify({"error": "NEWS2 computation failed", "detail": str(exc)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Shift summary endpoint
# ─────────────────────────────────────────────────────────────────────────────

@monitoring_bp.route("/<patient_id>/shift-summary", methods=["GET"])
@token_required
def get_shift_summary(current_user, patient_id: str):
    """
    Generate an SBAR-style shift handoff summary for a patient.
    ---
    tags:
      - Patient Monitoring
    security:
      - Bearer: []
    parameters:
      - name: patient_id
        in: path
        type: string
        required: true
      - name: shift_hours
        in: query
        type: integer
        default: 8
        description: Shift duration in hours to summarize
    responses:
      200:
        description: SBAR shift summary
      403:
        description: Patients cannot access shift summaries
    """
    if current_user.role == "patient":
        return jsonify({"error": "Shift summaries are for clinical staff only"}), 403

    shift_hours = request.args.get("shift_hours", 8, type=int)
    shift_hours = max(1, min(shift_hours, 24))  # Clamp between 1-24 hours

    try:
        from app.agents.tools.vitals_analysis import generate_shift_summary

        raw = generate_shift_summary.invoke({
            "patient_id": patient_id,
            "shift_hours": shift_hours,
        })
        summary_data = json.loads(raw)

        return jsonify({
            "patient_id": patient_id,
            "shift_hours": shift_hours,
            "summary": summary_data,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }), 200

    except Exception as exc:
        logger.error("MonitoringAPI: shift summary failed for patient %s: %s", patient_id, exc)
        return jsonify({"error": "Shift summary generation failed", "detail": str(exc)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Alerts list endpoint
# ─────────────────────────────────────────────────────────────────────────────

@monitoring_bp.route("/alerts", methods=["GET"])
@token_required
def list_monitoring_alerts(current_user):
    """
    List monitoring alerts with optional filtering.
    ---
    tags:
      - Patient Monitoring
    security:
      - Bearer: []
    parameters:
      - name: patient_id
        in: query
        type: string
        description: Filter alerts by patient UUID
      - name: severity
        in: query
        type: string
        enum: [CRITICAL, HIGH, MODERATE]
      - name: acknowledged
        in: query
        type: boolean
        description: Filter by acknowledgment status (true/false)
      - name: limit
        in: query
        type: integer
        default: 50
    responses:
      200:
        description: List of monitoring alerts
    """
    if current_user.role not in ("doctor", "nurse", "admin"):
        return jsonify({"error": "Alert viewing requires clinical staff role"}), 403

    patient_id = request.args.get("patient_id")
    severity = request.args.get("severity")
    acknowledged_param = request.args.get("acknowledged")
    limit = request.args.get("limit", 50, type=int)
    limit = min(limit, 200)  # Cap at 200

    try:
        from app.models.alert import Alert
        query = Alert.query.order_by(Alert.created_at.desc())

        if patient_id:
            query = query.filter(Alert.patient_id == patient_id)
        if severity:
            query = query.filter(Alert.severity == severity.upper())
        if acknowledged_param is not None:
            is_ack = acknowledged_param.lower() in ("true", "1", "yes")
            query = query.filter(Alert.acknowledged == is_ack)

        alerts = query.limit(limit).all()

        return jsonify({
            "alerts": [
                {
                    "id": str(a.id),
                    "patient_id": str(a.patient_id) if a.patient_id else None,
                    "alert_type": a.alert_type,
                    "severity": a.severity,
                    "message": a.message,
                    "acknowledged": a.acknowledged,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "data": a.data if hasattr(a, "data") else {},
                }
                for a in alerts
            ],
            "total": len(alerts),
            "limit": limit,
        }), 200

    except Exception as exc:
        logger.error("MonitoringAPI: alert list query failed: %s", exc)
        return jsonify({"error": "Could not retrieve alerts", "detail": str(exc)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Alert acknowledgment endpoint
# ─────────────────────────────────────────────────────────────────────────────

@monitoring_bp.route("/alerts/<alert_id>/acknowledge", methods=["POST"])
@token_required
def acknowledge_alert(current_user, alert_id: str):
    """
    Acknowledge a monitoring alert.
    ---
    tags:
      - Patient Monitoring
    security:
      - Bearer: []
    parameters:
      - name: alert_id
        in: path
        type: string
        required: true
        description: UUID of the alert to acknowledge
    requestBody:
      content:
        application/json:
          schema:
            type: object
            properties:
              note:
                type: string
                description: Optional clinical note for the acknowledgment
    responses:
      200:
        description: Alert acknowledged successfully
      403:
        description: Patients cannot acknowledge alerts
      404:
        description: Alert not found
    """
    if current_user.role == "patient":
        return jsonify({"error": "Alert acknowledgment requires clinical staff role"}), 403

    body = request.get_json(silent=True) or {}
    note = body.get("note", "")

    try:
        from app.models.alert import Alert
        from app.models.db import db

        alert = Alert.query.filter_by(id=alert_id).first()
        if not alert:
            return jsonify({"error": "Alert not found"}), 404

        if alert.acknowledged:
            return jsonify({
                "message": "Alert already acknowledged",
                "alert_id": alert_id,
                "acknowledged": True,
            }), 200

        alert.acknowledged = True
        alert.acknowledged_by = str(current_user.id)
        alert.acknowledged_at = datetime.now(timezone.utc)
        if note:
            alert.acknowledgment_note = note

        db.session.commit()

        logger.info(
            "MonitoringAPI: alert %s acknowledged by user %s (%s)",
            alert_id, current_user.id, current_user.role,
        )

        return jsonify({
            "success": True,
            "alert_id": alert_id,
            "acknowledged": True,
            "acknowledged_by": str(current_user.id),
            "acknowledged_at": alert.acknowledged_at.isoformat(),
        }), 200

    except Exception as exc:
        logger.error("MonitoringAPI: alert acknowledgment failed for %s: %s", alert_id, exc)
        try:
            from app.models.db import db
            db.session.rollback()
        except Exception:
            pass
        return jsonify({"error": "Acknowledgment failed", "detail": str(exc)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Anomaly detection endpoint (inline, no full agent run)
# ─────────────────────────────────────────────────────────────────────────────

@monitoring_bp.route("/<patient_id>/anomaly-check", methods=["GET"])
@token_required
def check_anomaly(current_user, patient_id: str):
    """
    Run statistical anomaly detection on the patient's current vitals.
    Lighter-weight than a full monitoring cycle — no alert dispatch.
    ---
    tags:
      - Patient Monitoring
    security:
      - Bearer: []
    parameters:
      - name: patient_id
        in: path
        type: string
        required: true
    responses:
      200:
        description: Anomaly detection result
      404:
        description: No vitals data available
    """
    if current_user.role == "patient" and str(current_user.id) != patient_id:
        return jsonify({"error": "You may only check your own vitals"}), 403

    try:
        from app.services.vitals_service import VitalsService
        from app.agents.tools.vitals_analysis import detect_vitals_anomaly

        vitals = VitalsService.get_current_vitals(patient_id)
        if not vitals:
            return jsonify({"error": "No current vitals data available"}), 404

        raw = detect_vitals_anomaly.invoke({
            "patient_id": patient_id,
            "current_vitals": json.dumps(vitals),
        })
        anomaly_result = json.loads(raw)

        return jsonify({
            "patient_id": patient_id,
            "vitals": vitals,
            "anomaly_check": anomaly_result,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }), 200

    except Exception as exc:
        logger.error("MonitoringAPI: anomaly check failed for patient %s: %s", patient_id, exc)
        return jsonify({"error": "Anomaly check failed", "detail": str(exc)}), 500
