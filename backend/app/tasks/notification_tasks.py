"""
notification_tasks.py — Celery tasks for async notification delivery.

Provides:
  - celery_send_notification()         : Single notification (async, with retry)
  - celery_send_bulk_notifications()   : Fan-out to multiple users
  - celery_appointment_reminders()     : Beat task: daily appointment reminders
  - celery_medication_reminders()      : Beat task: medication schedule reminders

All Celery tasks here are thin wrappers around NotificationService to keep
business logic testable without Celery infrastructure.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Core async notification task
# ─────────────────────────────────────────────────────────────────────────────

def send_notification_async(
    user_id: str,
    title: str,
    body: str,
    notification_type: str,
    priority: str = "normal",
    channels: Optional[list] = None,
    action_url: Optional[str] = None,
    action_data: Optional[dict] = None,
    email: Optional[str] = None,
    name: Optional[str] = None,
    phone: Optional[str] = None,
    html_body: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """
    Construct a NotificationPayload and dispatch via NotificationService.
    Returns DispatchResult.to_dict().
    """
    from app.services.notification_service import NotificationService, NotificationPayload

    payload = NotificationPayload(
        user_id=user_id,
        title=title,
        body=body,
        type=notification_type,
        priority=priority,
        channels=channels,
        action_url=action_url,
        action_data=action_data,
        metadata=metadata,
        email=email,
        name=name,
        phone=phone,
        html_body=html_body,
    )

    result = NotificationService.dispatch(payload)
    return result.to_dict()


def send_bulk_notifications_async(
    user_payloads: list[dict],
) -> dict:
    """
    Send notifications to multiple users.

    Args:
        user_payloads: List of dicts, each a full kwarg set for send_notification_async()

    Returns:
        Summary dict: {"total": N, "delivered": M, "failed": K, "results": [...]}
    """
    from app.services.notification_service import NotificationService, NotificationPayload

    results = []
    delivered = 0
    failed = 0

    for payload_dict in user_payloads:
        try:
            payload = NotificationPayload(**payload_dict)
            result = NotificationService.dispatch(payload)
            results.append(result.to_dict())
            if result.delivered_channels:
                delivered += 1
            else:
                failed += 1
        except Exception as exc:
            logger.error("send_bulk: failed for payload %s: %s", payload_dict.get("user_id"), exc)
            failed += 1
            results.append({"error": str(exc)})

    return {
        "total": len(user_payloads),
        "delivered": delivered,
        "failed": failed,
        "results": results,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Scheduled beat functions
# ─────────────────────────────────────────────────────────────────────────────

def run_appointment_reminders() -> dict:
    """
    Beat task: find appointments in the next 24 hours and send reminders.
    Designed to run once per hour.
    """
    logger.info("NotificationTask: running appointment reminder sweep")
    now = datetime.now(timezone.utc)
    window_start = now
    window_end = now + timedelta(hours=24)

    reminded = 0
    failed = 0

    try:
        from app.models.db import db
        from sqlalchemy import text
        from app.services.notification_service import NotificationService

        rows = db.session.execute(
            text("""
                SELECT
                    a.id, a.patient_id, a.doctor_id, a.scheduled_at,
                    u.email AS patient_email,
                    pp.first_name || ' ' || pp.last_name AS patient_name,
                    dp.first_name || ' ' || dp.last_name AS doctor_name
                FROM appointments a
                JOIN users u ON u.id = a.patient_id
                LEFT JOIN patient_profiles pp ON pp.user_id = a.patient_id
                LEFT JOIN doctor_profiles dp ON dp.user_id = a.doctor_id
                WHERE a.scheduled_at BETWEEN :start AND :end
                  AND a.status = 'confirmed'
                  AND a.reminder_sent = false
            """),
            {"start": window_start.isoformat(), "end": window_end.isoformat()},
        ).fetchall()

        for row in rows:
            try:
                appt_time = row.scheduled_at
                result = NotificationService.notify_appointment_reminder(
                    user_id=str(row.patient_id),
                    patient_name=row.patient_name or "Patient",
                    doctor_name=row.doctor_name or "Doctor",
                    appointment_time=appt_time.strftime("%A, %B %d at %I:%M %p UTC"),
                    action_url=f"/patient/appointments",
                    email=row.patient_email,
                )
                if result.delivered_channels:
                    # Mark reminder sent
                    db.session.execute(
                        text("UPDATE appointments SET reminder_sent = true WHERE id = :id"),
                        {"id": str(row.id)},
                    )
                    db.session.commit()
                    reminded += 1
                else:
                    failed += 1
            except Exception as exc:
                logger.error("NotificationTask: appointment reminder failed for %s: %s", row.id, exc)
                failed += 1

    except Exception as exc:
        logger.error("NotificationTask: appointment reminder sweep failed: %s", exc)
        return {"status": "error", "error": str(exc)}

    logger.info("NotificationTask: appointment reminders — sent=%d failed=%d", reminded, failed)
    return {"status": "complete", "reminded": reminded, "failed": failed}


def run_appointment_reminders_1h() -> dict:
    """
    Beat task: find appointments starting in the next 1 hour and send
    a final "Starting soon" reminder. Runs every 15 minutes.
    """
    logger.info("NotificationTask: running 1-hour appointment reminder sweep")
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(hours=1)

    reminded = 0
    failed = 0

    try:
        from app.models.db import db
        from sqlalchemy import text
        from app.services.notification_service import NotificationService

        rows = db.session.execute(
            text("""
                SELECT
                    a.id, a.patient_id, a.doctor_id, a.start_time,
                    u.email AS patient_email,
                    pp.first_name || ' ' || pp.last_name AS patient_name,
                    dp.first_name || ' ' || dp.last_name AS doctor_name,
                    a.meeting_link, a.type
                FROM appointments a
                JOIN users u ON u.id = a.patient_id
                LEFT JOIN patient_profiles pp ON pp.user_id = a.patient_id
                LEFT JOIN doctor_profiles dp ON dp.user_id = a.doctor_id
                WHERE a.start_time BETWEEN :start AND :end
                  AND a.status = 'scheduled'
                  AND (a.reminder_1h_sent IS NULL OR a.reminder_1h_sent = false)
            """),
            {"start": now.isoformat(), "end": window_end.isoformat()},
        ).fetchall()

        for row in rows:
            try:
                time_str = row.start_time.strftime("%I:%M %p UTC") if row.start_time else ""
                join_info = (
                    f" Join via: {row.meeting_link}"
                    if row.meeting_link and row.type == "video"
                    else ""
                )
                result = NotificationService.dispatch(
                    __import__(
                        "app.services.notification_service",
                        fromlist=["NotificationPayload"]
                    ).NotificationPayload(
                        user_id=str(row.patient_id),
                        title="Appointment Starting Soon",
                        body=f"Your appointment with Dr. {row.doctor_name} starts at {time_str}.{join_info}",
                        type="appointment_reminder",
                        priority="high",
                        action_url="/patient/appointments",
                        email=row.patient_email,
                        name=row.patient_name,
                    )
                )
                if result.delivered_channels:
                    try:
                        db.session.execute(
                            text("UPDATE appointments SET reminder_1h_sent = true WHERE id = :id"),
                            {"id": str(row.id)},
                        )
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                    reminded += 1
                else:
                    failed += 1
            except Exception as exc:
                logger.error("NotificationTask: 1h reminder failed for %s: %s", row.id, exc)
                failed += 1

    except Exception as exc:
        logger.error("NotificationTask: 1h reminder sweep failed: %s", exc)
        return {"status": "error", "error": str(exc)}

    logger.info("NotificationTask: 1h reminders — sent=%d failed=%d", reminded, failed)
    return {"status": "complete", "reminded": reminded, "failed": failed}


def run_medication_reminders() -> dict:
    """
    Beat task: send medication reminders for doses due in the next 30 minutes.
    Designed to run every 15 minutes.
    """
    logger.info("NotificationTask: running medication reminder sweep")
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(minutes=30)

    reminded = 0
    failed = 0

    try:
        from app.models.db import db
        from sqlalchemy import text
        from app.services.notification_service import NotificationService

        rows = db.session.execute(
            text("""
                SELECT
                    mr.id, mr.patient_id, mr.medication_name, mr.dose, mr.scheduled_time,
                    pp.first_name AS patient_name
                FROM medication_reminders mr
                LEFT JOIN patient_profiles pp ON pp.user_id = mr.patient_id
                WHERE mr.scheduled_time BETWEEN :now AND :end
                  AND mr.is_sent = false
                  AND mr.is_active = true
            """),
            {"now": now.isoformat(), "end": window_end.isoformat()},
        ).fetchall()

        for row in rows:
            try:
                result = NotificationService.notify_medication_reminder(
                    user_id=str(row.patient_id),
                    patient_name=row.patient_name or "Patient",
                    medication_name=row.medication_name,
                    dose=row.dose or "",
                    scheduled_time=row.scheduled_time.strftime("%I:%M %p"),
                )
                if result.delivered_channels:
                    db.session.execute(
                        text("UPDATE medication_reminders SET is_sent = true WHERE id = :id"),
                        {"id": str(row.id)},
                    )
                    db.session.commit()
                    reminded += 1
                else:
                    failed += 1
            except Exception as exc:
                logger.error("NotificationTask: medication reminder failed for %s: %s", row.id, exc)
                failed += 1

    except Exception as exc:
        logger.error("NotificationTask: medication reminder sweep failed: %s", exc)
        return {"status": "error", "error": str(exc)}

    logger.info("NotificationTask: medication reminders — sent=%d failed=%d", reminded, failed)
    return {"status": "complete", "reminded": reminded, "failed": failed}


# ─────────────────────────────────────────────────────────────────────────────
# Celery app + task registration
# ─────────────────────────────────────────────────────────────────────────────

def make_notification_celery(app=None):
    """
    Create a Celery app for notification tasks.
    Reuses the same broker/backend config as monitoring_tasks.
    """
    try:
        from celery import Celery

        broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
        result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

        celery_app = Celery(
            "vitalmind_notifications",
            broker=broker_url,
            backend=result_backend,
        )

        celery_app.conf.beat_schedule = {
            "appointment-reminders-24h": {
                "task": "app.tasks.notification_tasks.celery_appointment_reminders",
                "schedule": 3600.0,   # Every hour
                "options": {"queue": "notifications", "expires": 3500},
            },
            "appointment-reminders-1h": {
                "task": "app.tasks.notification_tasks.celery_appointment_reminders_1h",
                "schedule": 900.0,    # Every 15 minutes
                "options": {"queue": "notifications", "expires": 800},
            },
            "medication-reminders": {
                "task": "app.tasks.notification_tasks.celery_medication_reminders",
                "schedule": 900.0,    # Every 15 minutes
                "options": {"queue": "notifications", "expires": 800},
            },
        }

        celery_app.conf.task_routes = {
            "app.tasks.notification_tasks.*": {"queue": "notifications"},
        }
        celery_app.conf.task_serializer = "json"
        celery_app.conf.result_serializer = "json"
        celery_app.conf.accept_content = ["json"]
        celery_app.conf.timezone = "UTC"
        celery_app.conf.enable_utc = True

        if app is not None:
            class ContextTask(celery_app.Task):
                def __call__(self, *args, **kwargs):
                    with app.app_context():
                        return self.run(*args, **kwargs)
            celery_app.Task = ContextTask

        return celery_app

    except ImportError:
        logger.warning("NotificationTask: Celery not installed — async notifications unavailable")
        return None


def register_notification_tasks(celery_app) -> None:
    """Register all notification Celery tasks on the given celery_app."""
    if celery_app is None:
        return

    @celery_app.task(
        name="app.tasks.notification_tasks.celery_send_notification",
        bind=True,
        max_retries=3,
        default_retry_delay=30,
    )
    def celery_send_notification(
        self,
        user_id: str,
        title: str,
        body: str,
        notification_type: str,
        **kwargs,
    ) -> dict:
        """Celery task: send a single notification with retry logic."""
        try:
            return send_notification_async(
                user_id=user_id,
                title=title,
                body=body,
                notification_type=notification_type,
                **kwargs,
            )
        except Exception as exc:
            logger.error("NotificationTask: send_notification failed: %s", exc)
            raise self.retry(exc=exc)

    @celery_app.task(
        name="app.tasks.notification_tasks.celery_send_bulk_notifications",
        bind=True,
        max_retries=1,
    )
    def celery_send_bulk_notifications(self, user_payloads: list[dict]) -> dict:
        """Celery task: send notifications to a list of users."""
        try:
            return send_bulk_notifications_async(user_payloads)
        except Exception as exc:
            logger.error("NotificationTask: bulk notification failed: %s", exc)
            raise self.retry(exc=exc)

    @celery_app.task(
        name="app.tasks.notification_tasks.celery_appointment_reminders",
        bind=True,
        max_retries=1,
        soft_time_limit=3400,
    )
    def celery_appointment_reminders(self) -> dict:
        """Celery beat task: hourly appointment reminder sweep."""
        try:
            return run_appointment_reminders()
        except Exception as exc:
            logger.error("NotificationTask: appointment reminders beat task failed: %s", exc)
            raise

    @celery_app.task(
        name="app.tasks.notification_tasks.celery_appointment_reminders_1h",
        bind=True,
        max_retries=1,
        soft_time_limit=800,
    )
    def celery_appointment_reminders_1h(self) -> dict:
        """Celery beat task: 15-minute sweep for appointments starting within 1 hour."""
        try:
            return run_appointment_reminders_1h()
        except Exception as exc:
            logger.error("NotificationTask: 1h reminders beat task failed: %s", exc)
            raise

    @celery_app.task(
        name="app.tasks.notification_tasks.celery_medication_reminders",
        bind=True,
        max_retries=1,
        soft_time_limit=800,
    )
    def celery_medication_reminders(self) -> dict:
        """Celery beat task: 15-minute medication reminder sweep."""
        try:
            return run_medication_reminders()
        except Exception as exc:
            logger.error("NotificationTask: medication reminders beat task failed: %s", exc)
            raise

    logger.info("NotificationTask: all 5 Celery tasks registered")
