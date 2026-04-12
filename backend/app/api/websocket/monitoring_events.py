"""
monitoring_events.py — Socket.IO event handlers for monitoring-specific server-side events.

Provides server-initiated push utilities:
  - push_vitals_update()   : Push a new vitals reading to a patient's room
  - push_monitoring_alert(): Push a monitoring alert to ward + physician rooms
  - push_news2_update()    : Push a NEWS2 score change notification

These are called by the MonitoringAgent / Celery tasks after processing.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.websocket import socketio

logger = logging.getLogger(__name__)


def push_vitals_update(patient_id: str, vitals: dict[str, Any]) -> None:
    """
    Server-push a real-time vitals update to all clients subscribed to a patient.

    Args:
        patient_id: UUID of the patient
        vitals: Dict of vital sign values (heart_rate, spo2, etc.)
    """
    try:
        socketio.emit(
            "vitals_update",
            {
                "patient_id": patient_id,
                "vitals": vitals,
                "event_type": "vitals_update",
            },
            room=f"patient:{patient_id}",
            namespace="/monitoring",
        )
        socketio.emit(
            "vitals_update",
            {
                "patient_id": patient_id,
                "vitals": vitals,
                "event_type": "vitals_update",
            },
            room="ward:all",
            namespace="/monitoring",
        )
        logger.debug("MonitoringEvents: pushed vitals update for patient %s", patient_id)
    except Exception as exc:
        logger.error("MonitoringEvents: push_vitals_update failed for %s: %s", patient_id, exc)


def push_monitoring_alert(
    patient_id: str,
    alert_data: dict[str, Any],
    physician_id: str | None = None,
) -> None:
    """
    Server-push a monitoring alert to the ward wall and optional physician room.

    Args:
        patient_id: UUID of the affected patient
        alert_data: Alert payload dict (from notification_tools.py)
        physician_id: UUID of the attending physician (for targeted Level 2+ alerts)
    """
    try:
        level = alert_data.get("level", 1)
        event_name = "emergency_alert" if level >= 3 else "monitoring_alert"

        # Push to patient room
        socketio.emit(
            event_name,
            alert_data,
            room=f"patient:{patient_id}",
            namespace="/monitoring",
        )

        # Push to all ward staff
        socketio.emit(
            event_name,
            alert_data,
            room="ward:all",
            namespace="/monitoring",
        )

        # Push to specific physician if provided
        if physician_id:
            socketio.emit(
                event_name,
                alert_data,
                room=f"physician:{physician_id}",
                namespace="/monitoring",
            )

        logger.info(
            "MonitoringEvents: pushed %s (level=%d) for patient %s",
            event_name, level, patient_id,
        )
    except Exception as exc:
        logger.error("MonitoringEvents: push_monitoring_alert failed for %s: %s", patient_id, exc)


def push_news2_update(
    patient_id: str,
    news2_score: int,
    risk_level: str,
    escalation_level: int,
) -> None:
    """
    Push a NEWS2 score update to ward clients.
    Triggered after every monitoring cycle to keep the dashboard scores live.

    Args:
        patient_id: UUID of the patient
        news2_score: Computed total NEWS2 score
        risk_level: Risk category string (Low, Low-Medium, Medium, High)
        escalation_level: 0-3 escalation level
    """
    try:
        socketio.emit(
            "news2_update",
            {
                "patient_id": patient_id,
                "news2_score": news2_score,
                "risk_level": risk_level,
                "escalation_level": escalation_level,
                "event_type": "news2_update",
            },
            room=f"patient:{patient_id}",
            namespace="/monitoring",
        )
        socketio.emit(
            "news2_update",
            {
                "patient_id": patient_id,
                "news2_score": news2_score,
                "risk_level": risk_level,
                "escalation_level": escalation_level,
                "event_type": "news2_update",
            },
            room="ward:all",
            namespace="/monitoring",
        )
    except Exception as exc:
        logger.error("MonitoringEvents: push_news2_update failed for %s: %s", patient_id, exc)
