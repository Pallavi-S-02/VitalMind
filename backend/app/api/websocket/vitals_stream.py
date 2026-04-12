"""
vitals_stream.py — Socket.IO WebSocket handler for real-time vitals streaming.

Subscribes to the Redis pub/sub channel 'vitalmind:vitals_events' (published
by the IoT Gateway on every new device reading) and pushes updates to
connected clinical staff clients in their respective Socket.IO rooms.

Room naming convention:
  patient:<patient_id>   — All events for a specific patient
  ward:all               — All patients (monitoring wall)
  physician:<user_id>    — Physician-specific events
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Optional

from app.websocket import socketio

logger = logging.getLogger(__name__)

_subscriber_thread: Optional[threading.Thread] = None
_subscriber_running = False


def _redis_vitals_subscriber():
    """
    Background thread: subscribes to Redis pub/sub and emits to Socket.IO rooms.
    Runs as a daemon thread started when the first clinical client connects.
    """
    try:
        import redis as redis_lib

        r = redis_lib.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True,
        )
        ps = r.pubsub()
        ps.subscribe("vitalmind:vitals_events", "vitalmind:monitoring_alerts", "vitalmind:emergency_alerts")

        logger.info("VitalsStream: Redis subscriber started — listening for vitals + alert events")

        global _subscriber_running
        while _subscriber_running:
            message = ps.get_message(timeout=1.0)
            if message and message["type"] == "message":
                channel = message["channel"]
                try:
                    data = json.loads(message["data"])
                    patient_id = data.get("patient_id")

                    if channel == "vitalmind:vitals_events":
                        # Push vitals update to the patient's room and the ward wall
                        if patient_id:
                            socketio.emit(
                                "vitals_update",
                                data,
                                room=f"patient:{patient_id}",
                                namespace="/monitoring",
                            )
                        socketio.emit(
                            "vitals_update",
                            data,
                            room="ward:all",
                            namespace="/monitoring",
                        )
                        logger.debug("VitalsStream: emitted vitals update for patient %s", patient_id)

                    elif channel in ("vitalmind:monitoring_alerts", "vitalmind:emergency_alerts"):
                        # Push alert to patient room, ward room, and physician room
                        level = data.get("level", 1)
                        event_name = "emergency_alert" if level >= 3 else "monitoring_alert"

                        if patient_id:
                            socketio.emit(
                                event_name,
                                data,
                                room=f"patient:{patient_id}",
                                namespace="/monitoring",
                            )
                        socketio.emit(
                            event_name,
                            data,
                            room="ward:all",
                            namespace="/monitoring",
                        )

                        # Also push to the prescribing physician's personal room if known
                        physician_id = data.get("physician_id")
                        if physician_id:
                            socketio.emit(
                                event_name,
                                data,
                                room=f"physician:{physician_id}",
                                namespace="/monitoring",
                            )

                        severity = data.get("severity", "")
                        logger.info(
                            "VitalsStream: alert emitted — level=%d patient=%s severity=%s",
                            level, patient_id, severity,
                        )

                except json.JSONDecodeError as exc:
                    logger.warning("VitalsStream: could not parse Redis message: %s", exc)
                except Exception as exc:
                    logger.error("VitalsStream: error handling pub/sub message: %s", exc)

        ps.unsubscribe()
        logger.info("VitalsStream: Redis subscriber stopped")

    except Exception as exc:
        logger.error("VitalsStream: Redis subscriber thread crashed: %s", exc)


def start_vitals_subscriber():
    """Start the background Redis pub/sub subscriber thread (idempotent)."""
    global _subscriber_thread, _subscriber_running

    if _subscriber_thread and _subscriber_thread.is_alive():
        return  # Already running

    _subscriber_running = True
    _subscriber_thread = threading.Thread(
        target=_redis_vitals_subscriber,
        name="vitals-redis-subscriber",
        daemon=True,
    )
    _subscriber_thread.start()
    logger.info("VitalsStream: subscriber thread started")


def stop_vitals_subscriber():
    """Signal the background subscriber thread to stop."""
    global _subscriber_running
    _subscriber_running = False
    logger.info("VitalsStream: stop signal sent to subscriber thread")


# ─────────────────────────────────────────────────────────────────────────────
# Socket.IO namespace: /monitoring
# ─────────────────────────────────────────────────────────────────────────────

@socketio.on("connect", namespace="/monitoring")
def handle_monitoring_connect(auth):
    """
    Handle connection to the /monitoring namespace.
    Requires JWT auth and joins the client to appropriate rooms.
    """
    from flask import request
    from app.services.auth_service import AuthService

    if not auth or "token" not in auth:
        logger.warning("MonitoringWS: connection refused — no token")
        return False

    try:
        token = auth["token"]
        if token.startswith("Bearer "):
            token = token[7:]

        decoded = AuthService.decode_token(token)
        if isinstance(decoded, str):
            raise ValueError(decoded)
        user_id = decoded.get("sub")
        role = decoded.get("role", "patient")

        # All clinical staff join the ward wall room
        if role in ("doctor", "nurse", "admin"):
            from flask_socketio import join_room
            join_room("ward:all")
            logger.info("MonitoringWS: %s %s joined ward:all room", role, user_id)

        # Join personal physician room for targeted alerts
        if role == "doctor":
            from flask_socketio import join_room
            join_room(f"physician:{user_id}")

        # Patients join their own room (for personal vitals updates)
        if role == "patient":
            from flask_socketio import join_room
            join_room(f"patient:{user_id}")

        # Start the background subscriber if not already running
        start_vitals_subscriber()

        from flask_socketio import emit
        emit("monitoring_connected", {
            "status": "connected",
            "user_id": user_id,
            "role": role,
            "rooms": ["ward:all"] if role != "patient" else [f"patient:{user_id}"],
        })

        logger.info("MonitoringWS: user %s (%s) connected", user_id, role)
        return True

    except Exception as exc:
        logger.warning("MonitoringWS: connection refused — invalid token: %s", exc)
        return False


@socketio.on("disconnect", namespace="/monitoring")
def handle_monitoring_disconnect():
    """Log monitoring WebSocket disconnections."""
    from flask import request
    logger.info("MonitoringWS: client SID %s disconnected", request.sid)


@socketio.on("join_patient_room", namespace="/monitoring")
def handle_join_patient_room(data):
    """
    Allow clinical staff to join a specific patient's monitoring room.
    Used when a doctor navigates to a patient's detail page.
    """
    from flask_socketio import join_room, emit
    patient_id = data.get("patient_id")
    if patient_id:
        join_room(f"patient:{patient_id}")
        emit("joined_patient_room", {"patient_id": patient_id, "status": "joined"})
        logger.info("MonitoringWS: client joined room patient:%s", patient_id)


@socketio.on("leave_patient_room", namespace="/monitoring")
def handle_leave_patient_room(data):
    """Leave a specific patient's monitoring room."""
    from flask_socketio import leave_room
    patient_id = data.get("patient_id")
    if patient_id:
        leave_room(f"patient:{patient_id}")
        logger.info("MonitoringWS: client left room patient:%s", patient_id)


@socketio.on("acknowledge_alert", namespace="/monitoring")
def handle_acknowledge_alert(data):
    """
    Real-time alert acknowledgment via WebSocket.
    Immediately broadcasts to all ward clients that the alert was acknowledged.
    """
    from flask_socketio import emit
    alert_id = data.get("alert_id")
    acknowledged_by = data.get("acknowledged_by", "unknown")

    if not alert_id:
        return

    # Persist to DB
    try:
        from app.models.alert import Alert
        from app.models.db import db
        from datetime import datetime, timezone

        alert = Alert.query.filter_by(id=alert_id).first()
        if alert and not alert.acknowledged:
            alert.acknowledged = True
            alert.acknowledged_by = acknowledged_by
            alert.acknowledged_at = datetime.now(timezone.utc)
            db.session.commit()
    except Exception as exc:
        logger.error("MonitoringWS: alert ack DB persist failed: %s", exc)

    # Broadcast acknowledgment to all ward clients
    emit(
        "alert_acknowledged",
        {"alert_id": alert_id, "acknowledged_by": acknowledged_by},
        room="ward:all",
        namespace="/monitoring",
        broadcast=True,
    )
    logger.info("MonitoringWS: alert %s acknowledged by %s", alert_id, acknowledged_by)
