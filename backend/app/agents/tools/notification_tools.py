"""
notification_tools.py — LangChain tools for the Patient Monitoring Agent alerting.

Implements the 3-level escalation chain:
  Level 1 → Nurse push notification (in-app Socket.IO event)
  Level 2 → Attending physician SMS (Twilio)
  Level 3 → On-call specialist page (Twilio + Redis pub/sub broadcast)

The actual Twilio/email calls are wrapped so they gracefully degrade
if credentials are not configured (common in dev/test environments).
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _publish_alert_event(alert_payload: dict) -> bool:
    """Publish alert to Redis pub/sub for the WebSocket monitoring dashboard."""
    try:
        import redis as redis_lib
        r = redis_lib.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True,
        )
        r.publish("vitalmind:monitoring_alerts", json.dumps(alert_payload))
        logger.info("Alert published to Redis pub/sub: level=%s", alert_payload.get("level"))
        return True
    except Exception as exc:
        logger.error("Redis alert publish failed: %s", exc)
        return False


def _persist_alert(alert_payload: dict) -> Optional[str]:
    """Persist alert to PostgreSQL alert table for audit and acknowledgment."""
    try:
        from app.models.alert import Alert
        from app.models.db import db
        alert = Alert(
            id=str(uuid.uuid4()),
            patient_id=alert_payload.get("patient_id"),
            alert_type=alert_payload.get("type", "vitals_anomaly"),
            severity=alert_payload.get("severity", "MODERATE"),
            message=alert_payload.get("message", ""),
            data=alert_payload,
            acknowledged=False,
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(alert)
        db.session.commit()
        return str(alert.id)
    except Exception as exc:
        logger.error("Alert persistence failed: %s", exc)
        try:
            from app.models.db import db
            db.session.rollback()
        except Exception:
            pass
        return None


def _send_sms(to_number: str, message: str, patient_id: str) -> bool:
    """Send SMS via Twilio. Gracefully degrades if not configured."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")

    if not all([account_sid, auth_token, from_number]):
        logger.warning(
            "Twilio not configured — SMS skipped for patient %s (would send to %s)",
            patient_id, to_number
        )
        return False

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        client.messages.create(
            body=message,
            from_=from_number,
            to=to_number,
        )
        logger.info("SMS sent to %s for patient %s", to_number, patient_id)
        return True
    except Exception as exc:
        logger.error("Twilio SMS failed: %s", exc)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Tool definitions
# ─────────────────────────────────────────────────────────────────────────────

@tool
def send_nurse_alert(
    patient_id: str,
    patient_name: str,
    alert_message: str,
    news2_score: int,
    vitals_summary: str,
) -> str:
    """
    Level 1 escalation: Send a real-time alert to nursing staff via in-app
    notification (Socket.IO push) and persist to the alerts database.

    Args:
        patient_id: UUID of the patient
        patient_name: Full name of the patient
        alert_message: Human-readable alert description
        news2_score: Computed NEWS2 total score
        vitals_summary: Brief summary of concerning vital signs

    Returns: JSON with alert ID, delivery status, and timestamp
    """
    alert_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    payload = {
        "id": alert_id,
        "type": "vitals_anomaly",
        "level": 1,
        "escalation_target": "nurse",
        "severity": "MODERATE" if news2_score < 7 else "HIGH",
        "patient_id": patient_id,
        "patient_name": patient_name,
        "message": alert_message,
        "news2_score": news2_score,
        "vitals_summary": vitals_summary,
        "timestamp": timestamp,
        "acknowledged": False,
        "channel": "in_app",
    }

    redis_ok = _publish_alert_event(payload)
    db_id = _persist_alert(payload)

    return json.dumps({
        "alert_id": db_id or alert_id,
        "level": 1,
        "target": "nurse",
        "channel": "in_app_socket",
        "redis_published": redis_ok,
        "db_persisted": db_id is not None,
        "timestamp": timestamp,
        "status": "sent" if redis_ok else "queued",
    })


@tool
def send_physician_sms_alert(
    patient_id: str,
    patient_name: str,
    alert_message: str,
    news2_score: int,
    physician_phone: str,
    vitals_summary: str,
) -> str:
    """
    Level 2 escalation: Page the attending physician via SMS (Twilio) with
    a structured clinical alert message.

    Args:
        patient_id: UUID of the patient
        patient_name: Full name of the patient
        alert_message: Clinical alert description
        news2_score: Computed NEWS2 total score
        physician_phone: Attending physician phone number in E.164 format (e.g. +15551234567)
        vitals_summary: Brief summary of concerning vital signs

    Returns: JSON with SMS delivery status and alert details
    """
    alert_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    sms_body = (
        f"🚨 VITALMIND ALERT — Level 2\n"
        f"Patient: {patient_name} (ID: {patient_id})\n"
        f"NEWS2 Score: {news2_score}\n"
        f"Concern: {alert_message}\n"
        f"Vitals: {vitals_summary}\n"
        f"Time: {timestamp[:19]}Z\n"
        f"Please review immediately and advise nursing staff."
    )

    sms_ok = _send_sms(physician_phone, sms_body, patient_id)

    payload = {
        "id": alert_id,
        "type": "vitals_anomaly",
        "level": 2,
        "escalation_target": "physician",
        "severity": "HIGH",
        "patient_id": patient_id,
        "patient_name": patient_name,
        "message": alert_message,
        "news2_score": news2_score,
        "vitals_summary": vitals_summary,
        "timestamp": timestamp,
        "acknowledged": False,
        "channel": "sms",
        "physician_phone": physician_phone,
    }

    redis_ok = _publish_alert_event(payload)
    db_id = _persist_alert(payload)

    return json.dumps({
        "alert_id": db_id or alert_id,
        "level": 2,
        "target": "physician",
        "channel": "sms",
        "sms_delivered": sms_ok,
        "redis_published": redis_ok,
        "db_persisted": db_id is not None,
        "timestamp": timestamp,
        "status": "sent" if sms_ok else "degraded_in_app_only",
    })


@tool
def send_emergency_specialist_alert(
    patient_id: str,
    patient_name: str,
    alert_message: str,
    news2_score: int,
    specialist_phone: str,
    vitals_summary: str,
    anomaly_details: str,
) -> str:
    """
    Level 3 escalation: EMERGENCY page to on-call specialist via Twilio
    plus a Redis broadcast for all connected clinical staff.
    Reserved for NEWS2 ≥ 7 or immediate life-threatening anomalies.

    Args:
        patient_id: UUID of the patient
        patient_name: Full name of the patient
        alert_message: Emergency alert description
        news2_score: Computed NEWS2 total score (should be ≥7)
        specialist_phone: On-call specialist phone in E.164 format
        vitals_summary: Summary of all vital signs
        anomaly_details: Specific anomaly information for clinical context

    Returns: JSON with full escalation status across all channels
    """
    alert_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    sms_body = (
        f"🔴 EMERGENCY — VITALMIND LEVEL 3 ALERT 🔴\n"
        f"PATIENT: {patient_name} (ID: {patient_id})\n"
        f"NEWS2 SCORE: {news2_score} — IMMEDIATE RESPONSE REQUIRED\n"
        f"ALERT: {alert_message}\n"
        f"VITALS: {vitals_summary}\n"
        f"DETAILS: {anomaly_details}\n"
        f"TIME: {timestamp[:19]}Z\n"
        f"PLEASE ATTEND IMMEDIATELY OR DELEGATE."
    )

    sms_ok = _send_sms(specialist_phone, sms_body, patient_id)

    payload = {
        "id": alert_id,
        "type": "emergency_alert",
        "level": 3,
        "escalation_target": "specialist",
        "severity": "CRITICAL",
        "patient_id": patient_id,
        "patient_name": patient_name,
        "message": alert_message,
        "news2_score": news2_score,
        "vitals_summary": vitals_summary,
        "anomaly_details": anomaly_details,
        "timestamp": timestamp,
        "acknowledged": False,
        "channel": "sms_broadcast",
    }

    redis_ok = _publish_alert_event(payload)
    # Also broadcast on the general emergency channel
    try:
        import redis as redis_lib
        r = redis_lib.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True,
        )
        r.publish("vitalmind:emergency_alerts", json.dumps(payload))
    except Exception:
        pass

    db_id = _persist_alert(payload)

    return json.dumps({
        "alert_id": db_id or alert_id,
        "level": 3,
        "target": "on_call_specialist",
        "sms_delivered": sms_ok,
        "redis_published": redis_ok,
        "emergency_broadcast": redis_ok,
        "db_persisted": db_id is not None,
        "timestamp": timestamp,
        "status": "emergency_dispatched",
    })
