"""
notification_service.py — VitalMind multi-channel notification fan-out dispatcher.

Architecture:
  NotificationService.dispatch()
    ├─ Channel: in_app    → persist to DB + emit Socket.IO push
    ├─ Channel: sms       → TwilioClient.send_sms()
    ├─ Channel: email     → SendGridClient.send_email()
    └─ Channel: push      → Web Push API (via pywebpush)

All channels are attempted independently — a failure in one channel does NOT
prevent delivery via other channels. Every notification is persisted to PostgreSQL
before any channel delivery is attempted (audit trail always complete).

Delivery channels per notification type:
  appointment_reminder    → in_app + email
  medication_reminder     → in_app + push
  vitals_alert            → in_app + push (+ sms for urgent/critical)
  triage_alert            → in_app + push + sms (always)
  lab_result_ready        → in_app + email
  system_alert            → in_app
  doctor_message          → in_app + push
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Notification types and channel routing map
# ─────────────────────────────────────────────────────────────────────────────

NotificationType = Literal[
    "appointment_reminder",
    "medication_reminder",
    "vitals_alert",
    "triage_alert",
    "lab_result_ready",
    "system_alert",
    "doctor_message",
    "alert_acknowledged",
    "shift_summary",
]

ChannelType = Literal["in_app", "sms", "email", "push"]

# Maps notification type → default channels tuple
_DEFAULT_CHANNELS: dict[str, tuple[str, ...]] = {
    "appointment_reminder": ("in_app", "email"),
    "medication_reminder":  ("in_app", "push"),
    "vitals_alert":         ("in_app", "push"),
    "triage_alert":         ("in_app", "push", "sms"),
    "lab_result_ready":     ("in_app", "email"),
    "system_alert":         ("in_app",),
    "doctor_message":       ("in_app", "push"),
    "alert_acknowledged":   ("in_app",),
    "shift_summary":        ("in_app", "email"),
}


@dataclass
class NotificationPayload:
    """
    Canonical notification payload accepted by dispatch().

    Required:
        user_id:     UUID of the recipient user
        title:       Short notification title (≤ 80 chars recommended)
        body:        Notification body text
        type:        One of the NotificationType literals

    Optional:
        priority:    "low" | "normal" | "high" | "critical"
        channels:    Override default channels (if None, use _DEFAULT_CHANNELS mapping)
        action_url:  Deep-link URL shown in notification (e.g. /doctor/monitoring/pid)
        action_data: Arbitrary JSON for frontend routing
        metadata:    Extra key-value pairs stored with the notification
        email:       Recipient email address (required for email channel)
        name:        Recipient display name (used in email greeting)
        phone:       Recipient phone in E.164 (required for SMS channel)
        html_body:   Optional rich HTML body for email channel
    """
    user_id: str
    title: str
    body: str
    type: str

    # Routing
    priority: str = "normal"
    channels: Optional[list[str]] = None
    action_url: Optional[str] = None
    action_data: Optional[dict] = None
    metadata: Optional[dict] = None

    # Channel-specific
    email: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    html_body: Optional[str] = None


@dataclass
class DispatchResult:
    notification_id: str
    delivered_channels: list[str] = field(default_factory=list)
    failed_channels: list[str] = field(default_factory=list)
    degraded_channels: list[str] = field(default_factory=list)   # configured but soft-fail
    errors: dict = field(default_factory=dict)
    db_persisted: bool = False

    def to_dict(self) -> dict:
        return {
            "notification_id": self.notification_id,
            "delivered_channels": self.delivered_channels,
            "failed_channels": self.failed_channels,
            "degraded_channels": self.degraded_channels,
            "errors": self.errors,
            "db_persisted": self.db_persisted,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Main service
# ─────────────────────────────────────────────────────────────────────────────

class NotificationService:
    """
    Stateless fan-out notification dispatcher.
    All methods are class-methods — no instance needed.
    """

    @classmethod
    def dispatch(cls, payload: NotificationPayload) -> DispatchResult:
        """
        Persist and fan-out a notification across all configured channels.

        Returns a DispatchResult summarising per-channel delivery status.
        """
        notification_id = str(uuid.uuid4())
        result = DispatchResult(notification_id=notification_id)

        # ── 1. Persist to DB first (always) ────────────────────────────────
        db_id = cls._persist(notification_id, payload)
        result.db_persisted = db_id is not None
        if db_id:
            notification_id = db_id   # Use actual DB ID
            result.notification_id = notification_id

        # ── 2. Resolve channels ─────────────────────────────────────────────
        channels = payload.channels
        if not channels:
            channels = list(_DEFAULT_CHANNELS.get(payload.type, ("in_app",)))

        # High/critical priority — always add push + SMS if not present
        if payload.priority in ("high", "critical"):
            if "push" not in channels:
                channels.append("push")
            if payload.priority == "critical" and "sms" not in channels and payload.phone:
                channels.append("sms")

        # ── 3. Fan-out per channel ──────────────────────────────────────────
        for channel in channels:
            try:
                if channel == "in_app":
                    cls._deliver_in_app(notification_id, payload)
                    result.delivered_channels.append("in_app")

                elif channel == "push":
                    ok = cls._deliver_push(notification_id, payload)
                    if ok:
                        result.delivered_channels.append("push")
                    else:
                        result.degraded_channels.append("push")

                elif channel == "sms":
                    sms_result = cls._deliver_sms(payload)
                    if sms_result.success:
                        result.delivered_channels.append("sms")
                    elif sms_result.degraded:
                        result.degraded_channels.append("sms")
                    else:
                        result.failed_channels.append("sms")
                        result.errors["sms"] = sms_result.error

                elif channel == "email":
                    email_result = cls._deliver_email(payload)
                    if email_result.success:
                        result.delivered_channels.append("email")
                    elif email_result.degraded:
                        result.degraded_channels.append("email")
                    else:
                        result.failed_channels.append("email")
                        result.errors["email"] = email_result.error

            except Exception as exc:
                logger.error(
                    "NotificationService: channel %s delivery failed for notification %s: %s",
                    channel, notification_id, exc,
                )
                result.failed_channels.append(channel)
                result.errors[channel] = str(exc)

        logger.info(
            "NotificationService: dispatched %s (type=%s) — delivered=%s failed=%s degraded=%s",
            notification_id, payload.type,
            result.delivered_channels, result.failed_channels, result.degraded_channels,
        )
        return result

    # ─────────────────────────────────────────────────────────────────────
    # DB persistence
    # ─────────────────────────────────────────────────────────────────────

    @classmethod
    def _persist(cls, notification_id: str, payload: NotificationPayload) -> Optional[str]:
        """Write notification to PostgreSQL notifications table."""
        try:
            from app.models.notification import Notification
            from app.models.db import db

            notif = Notification(
                id=notification_id,
                user_id=payload.user_id,
                title=payload.title,
                body=payload.body,
                type=payload.type,
                action_data={
                    "action_url": payload.action_url,
                    "priority": payload.priority,
                    "metadata": payload.metadata or {},
                    **(payload.action_data or {}),
                },
                is_read=False,
                created_at=datetime.now(timezone.utc),
            )
            db.session.add(notif)
            db.session.commit()
            logger.debug("NotificationService: persisted notification %s", notification_id)
            return str(notif.id)
        except Exception as exc:
            logger.error("NotificationService: DB persist failed: %s", exc)
            try:
                from app.models.db import db
                db.session.rollback()
            except Exception:
                pass
            return None

    # ─────────────────────────────────────────────────────────────────────
    # In-app channel (Socket.IO push)
    # ─────────────────────────────────────────────────────────────────────

    @classmethod
    def _deliver_in_app(cls, notification_id: str, payload: NotificationPayload) -> None:
        """Emit notification to the user's personal Socket.IO room."""
        try:
            from app.websocket import socketio
            event_data = {
                "id": notification_id,
                "title": payload.title,
                "body": payload.body,
                "type": payload.type,
                "priority": payload.priority,
                "action_url": payload.action_url,
                "action_data": payload.action_data,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "is_read": False,
            }
            socketio.emit(
                "new_notification",
                event_data,
                room=f"user:{payload.user_id}",
                namespace="/notifications",
            )
            logger.debug(
                "NotificationService: in-app delivered to user:%s type=%s",
                payload.user_id, payload.type,
            )
        except Exception as exc:
            logger.error("NotificationService: in-app delivery failed: %s", exc)
            raise

    # ─────────────────────────────────────────────────────────────────────
    # Web Push channel
    # ─────────────────────────────────────────────────────────────────────

    @classmethod
    def _deliver_push(cls, notification_id: str, payload: NotificationPayload) -> bool:
        """
        Send a Web Push notification to all active subscriptions for the user.
        Uses pywebpush. Requires VAPID_PRIVATE_KEY and VAPID_SUBJECT env vars.
        """
        try:
            import os
            from app.models.db import db
            from sqlalchemy import text

            # Load all active push subscriptions for this user
            rows = db.session.execute(
                text("""
                    SELECT endpoint, p256dh, auth
                    FROM push_subscriptions
                    WHERE user_id = :uid AND is_active = true
                """),
                {"uid": payload.user_id},
            ).fetchall()

            if not rows:
                logger.debug("NotificationService: no push subscriptions for user %s", payload.user_id)
                return False

            vapid_private_key = os.getenv("VAPID_PRIVATE_KEY")
            vapid_subject = os.getenv("VAPID_SUBJECT", "mailto:support@vitalmind.ai")

            if not vapid_private_key:
                logger.warning("NotificationService: VAPID_PRIVATE_KEY not set — push skipped")
                return False

            from pywebpush import webpush, WebPushException

            push_data = json.dumps({
                "id": notification_id,
                "title": payload.title,
                "body": payload.body,
                "type": payload.type,
                "priority": payload.priority,
                "action_url": payload.action_url or "/",
                "icon": "/icons/icon-192.png",
                "badge": "/icons/badge-72.png",
            })

            delivered = 0
            for row in rows:
                try:
                    webpush(
                        subscription_info={
                            "endpoint": row.endpoint,
                            "keys": {"p256dh": row.p256dh, "auth": row.auth},
                        },
                        data=push_data,
                        vapid_private_key=vapid_private_key,
                        vapid_claims={"sub": vapid_subject},
                    )
                    delivered += 1
                except WebPushException as exc:
                    status = getattr(exc.response, "status_code", None)
                    if status == 410:
                        # Subscription expired — deactivate
                        db.session.execute(
                            text("UPDATE push_subscriptions SET is_active = false WHERE endpoint = :ep"),
                            {"ep": row.endpoint},
                        )
                        db.session.commit()
                    logger.warning("NotificationService: push to endpoint failed: %s", exc)

            logger.info(
                "NotificationService: push delivered to %d/%d subscriptions for user %s",
                delivered, len(rows), payload.user_id,
            )
            return delivered > 0

        except ImportError:
            logger.warning("NotificationService: pywebpush not installed — push skipped")
            return False
        except Exception as exc:
            logger.error("NotificationService: push delivery failed: %s", exc)
            return False

    # ─────────────────────────────────────────────────────────────────────
    # SMS channel
    # ─────────────────────────────────────────────────────────────────────

    @classmethod
    def _deliver_sms(cls, payload: NotificationPayload):
        """Send SMS via Twilio."""
        from app.integrations.twilio_client import send_sms, TwilioResult

        if not payload.phone:
            logger.warning("NotificationService: SMS requested but no phone on payload")
            return TwilioResult(success=False, error="No phone number provided")

        # Compose concise SMS — strip HTML, truncate to 160 chars
        sms_text = f"{payload.title}\n{payload.body}"
        if len(sms_text) > 160:
            sms_text = sms_text[:157] + "..."

        return send_sms(to=payload.phone, body=sms_text)

    # ─────────────────────────────────────────────────────────────────────
    # Email channel
    # ─────────────────────────────────────────────────────────────────────

    @classmethod
    def _deliver_email(cls, payload: NotificationPayload):
        """Send email via SMTP."""
        from app.utils.email_service import send_smtp_email
        
        if not payload.email:
            logger.warning("NotificationService: email requested but no email on payload")
            from app.utils.email_service import SmtpResult
            return SmtpResult(success=False, error="No email address provided")

        return send_smtp_email(
            to_email=payload.email,
            subject=payload.title,
            text_body=payload.body,
            html_body=payload.html_body,
        )

    # ─────────────────────────────────────────────────────────────────────
    # Convenience factory methods
    # ─────────────────────────────────────────────────────────────────────

    @classmethod
    def notify_appointment_reminder(
        cls,
        user_id: str,
        patient_name: str,
        doctor_name: str,
        appointment_time: str,
        action_url: str,
        email: Optional[str] = None,
    ) -> DispatchResult:
        body = (
            f"Hi {patient_name}, you have an appointment with Dr. {doctor_name} "
            f"on {appointment_time}. Please log in to confirm or reschedule."
        )
        return cls.dispatch(NotificationPayload(
            user_id=user_id,
            title="Upcoming Appointment Reminder",
            body=body,
            type="appointment_reminder",
            priority="normal",
            action_url=action_url,
            email=email,
            name=patient_name,
            html_body=f"""
<h2>Appointment Reminder</h2>
<p>Hi {patient_name},</p>
<p>You have an appointment with <strong>Dr. {doctor_name}</strong> on <strong>{appointment_time}</strong>.</p>
<p><a href="{action_url}">View or manage your appointment</a></p>
<p>VitalMind Health Team</p>
""",
        ))

    @classmethod
    def notify_medication_reminder(
        cls,
        user_id: str,
        patient_name: str,
        medication_name: str,
        dose: str,
        scheduled_time: str,
    ) -> DispatchResult:
        return cls.dispatch(NotificationPayload(
            user_id=user_id,
            title=f"Medication Reminder: {medication_name}",
            body=f"Time to take your {medication_name} ({dose}) scheduled for {scheduled_time}.",
            type="medication_reminder",
            priority="normal",
            action_url="/patient/medications",
        ))

    @classmethod
    def notify_vitals_alert(
        cls,
        user_id: str,
        patient_name: str,
        alert_message: str,
        severity: str,
        patient_id: str,
        phone: Optional[str] = None,
    ) -> DispatchResult:
        priority = "critical" if severity in ("CRITICAL", "HIGH") else "high"
        return cls.dispatch(NotificationPayload(
            user_id=user_id,
            title=f"⚠ Vitals Alert — {severity}",
            body=alert_message,
            type="vitals_alert",
            priority=priority,
            action_url=f"/doctor/monitoring/{patient_id}",
            phone=phone,
            metadata={"patient_id": patient_id, "severity": severity},
        ))

    @classmethod
    def notify_lab_result(
        cls,
        user_id: str,
        patient_name: str,
        report_type: str,
        report_id: str,
        email: Optional[str] = None,
    ) -> DispatchResult:
        return cls.dispatch(NotificationPayload(
            user_id=user_id,
            title="Lab Results Ready",
            body=f"Your {report_type} results are now available. Tap to view.",
            type="lab_result_ready",
            priority="normal",
            action_url=f"/patient/reports/{report_id}",
            email=email,
            name=patient_name,
        ))

    @classmethod
    def mark_read(cls, notification_id: str, user_id: str) -> bool:
        """Mark a notification as read in the DB."""
        try:
            from app.models.notification import Notification
            from app.models.db import db
            notif = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
            if notif and not notif.is_read:
                notif.is_read = True
                db.session.commit()
                return True
            return False
        except Exception as exc:
            logger.error("NotificationService: mark_read failed: %s", exc)
            try:
                from app.models.db import db
                db.session.rollback()
            except Exception:
                pass
            return False

    @classmethod
    def mark_all_read(cls, user_id: str) -> int:
        """Mark all unread notifications for a user as read. Returns count updated."""
        try:
            from app.models.db import db
            from sqlalchemy import text
            result = db.session.execute(
                text("""
                    UPDATE notifications
                    SET is_read = true
                    WHERE user_id = :uid AND is_read = false
                """),
                {"uid": user_id},
            )
            db.session.commit()
            return result.rowcount
        except Exception as exc:
            logger.error("NotificationService: mark_all_read failed: %s", exc)
            try:
                from app.models.db import db
                db.session.rollback()
            except Exception:
                pass
            return 0

    @classmethod
    def get_unread_count(cls, user_id: str) -> int:
        """Fast unread count query."""
        try:
            from app.models.db import db
            from sqlalchemy import text
            row = db.session.execute(
                text("SELECT COUNT(*) FROM notifications WHERE user_id = :uid AND is_read = false"),
                {"uid": user_id},
            ).fetchone()
            return int(row[0]) if row else 0
        except Exception as exc:
            logger.error("NotificationService: unread count failed: %s", exc)
            return 0
