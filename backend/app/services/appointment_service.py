"""
appointment_service.py — Complete booking, cancellation, rescheduling, and availability logic.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, or_, text

from app.models.db import db
from app.models.appointment import Appointment

logger = logging.getLogger(__name__)

# Default appointment slot length in minutes
DEFAULT_SLOT_MINUTES = 30


class AppointmentService:

    # ─────────────────────────────────────────────────────────────
    # Queries
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def get_patient_appointments(patient_id: str, limit: int = 50) -> list[Appointment]:
        return (
            Appointment.query
            .filter_by(patient_id=patient_id)
            .order_by(Appointment.start_time.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_doctor_appointments(doctor_id: str, limit: int = 50) -> list[Appointment]:
        return (
            Appointment.query
            .filter_by(doctor_id=doctor_id)
            .order_by(Appointment.start_time.asc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_appointment(appointment_id: str) -> Optional[Appointment]:
        return Appointment.query.filter_by(id=appointment_id).first()

    @staticmethod
    def get_upcoming_appointments(
        patient_id: Optional[str] = None,
        doctor_id: Optional[str] = None,
        hours_ahead: int = 48,
    ) -> list[Appointment]:
        now = datetime.now(timezone.utc)
        window_end = now + timedelta(hours=hours_ahead)
        q = Appointment.query.filter(
            Appointment.start_time >= now,
            Appointment.start_time <= window_end,
            Appointment.status == "scheduled",
        )
        if patient_id:
            q = q.filter_by(patient_id=patient_id)
        if doctor_id:
            q = q.filter_by(doctor_id=doctor_id)
        return q.order_by(Appointment.start_time.asc()).all()

    # ─────────────────────────────────────────────────────────────
    # Availability
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def get_doctor_availability(
        doctor_id: str,
        date: datetime,
        slot_minutes: int = DEFAULT_SLOT_MINUTES,
    ) -> list[dict]:
        """
        Return open time slots for a doctor on a given date.

        Generates candidate slots from 08:00–18:00 (doctor working hours)
        and filters out slots that overlap with existing non-cancelled appointments.

        Returns list of:
            { "start": ISO8601, "end": ISO8601, "available": bool }
        """
        # Build candidate slots for the whole day (08:00–18:00)
        day_start = date.replace(hour=8, minute=0, second=0, microsecond=0)
        day_end = date.replace(hour=18, minute=0, second=0, microsecond=0)

        slots: list[dict] = []
        current = day_start
        while current + timedelta(minutes=slot_minutes) <= day_end:
            slots.append({
                "start": current.isoformat(),
                "end": (current + timedelta(minutes=slot_minutes)).isoformat(),
                "available": True,
            })
            current += timedelta(minutes=slot_minutes)

        # Fetch booked appointments for that day
        booked = Appointment.query.filter(
            Appointment.doctor_id == doctor_id,
            Appointment.status.in_(["scheduled", "confirmed"]),
            Appointment.start_time >= day_start,
            Appointment.start_time < day_end,
        ).all()

        booked_ranges = [(a.start_time, a.end_time) for a in booked]

        # Mark slots that overlap with booked ranges as unavailable
        for slot in slots:
            slot_start = datetime.fromisoformat(slot["start"])
            slot_end = datetime.fromisoformat(slot["end"])
            for bstart, bend in booked_ranges:
                # Overlap if slot_start < bend AND slot_end > bstart
                if slot_start < bend and slot_end > bstart:
                    slot["available"] = False
                    break

        return slots

    # ─────────────────────────────────────────────────────────────
    # Booking
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def create_appointment(data: dict) -> Appointment:
        """
        Book an appointment.

        Required keys: patient_id, doctor_id, start_time
        Optional:      end_time, type, reason, notes
        """
        start_time = data.get("start_time") or data.get("scheduled_time")
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))

        duration_minutes = int(data.get("duration_minutes", DEFAULT_SLOT_MINUTES))
        end_time = data.get("end_time")
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        elif end_time is None:
            end_time = start_time + timedelta(minutes=duration_minutes)

        # Conflict check
        conflict = AppointmentService._check_conflict(
            doctor_id=str(data["doctor_id"]),
            start_time=start_time,
            end_time=end_time,
        )
        if conflict:
            raise ValueError(
                f"Time slot is already booked. Conflicting appointment: {conflict.id}"
            )

        appointment = Appointment(
            patient_id=str(data["patient_id"]),
            doctor_id=str(data["doctor_id"]),
            start_time=start_time,
            end_time=end_time,
            status="scheduled",
            type=data.get("type", "in-person"),
            reason=data.get("reason"),
            notes=data.get("notes"),
            meeting_link=data.get("meeting_link"),
        )
        db.session.add(appointment)
        db.session.commit()

        logger.info(
            "AppointmentService: booked appointment %s for patient %s with doctor %s at %s",
            appointment.id, data["patient_id"], data["doctor_id"], start_time,
        )

        # Trigger confirmation notification (non-blocking)
        try:
            AppointmentService._send_booking_confirmation(appointment)
        except Exception as e:
            logger.warning("AppointmentService: confirmation notification failed: %s", e)

        return appointment

    @staticmethod
    def _check_conflict(
        doctor_id: str, start_time: datetime, end_time: datetime,
        exclude_id: Optional[str] = None,
    ) -> Optional[Appointment]:
        q = Appointment.query.filter(
            Appointment.doctor_id == doctor_id,
            Appointment.status.in_(["scheduled", "confirmed"]),
            Appointment.start_time < end_time,
            Appointment.end_time > start_time,
        )
        if exclude_id:
            q = q.filter(Appointment.id != exclude_id)
        return q.first()

    # ─────────────────────────────────────────────────────────────
    # Cancellation
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def cancel_appointment(
        appointment_id: str,
        reason: Optional[str] = None,
        cancelled_by: Optional[str] = None,
    ) -> Optional[Appointment]:
        appt = Appointment.query.filter_by(id=appointment_id).first()
        if not appt:
            return None

        if appt.status in ("completed", "cancelled"):
            raise ValueError(f"Appointment already {appt.status}")

        appt.status = "cancelled"
        if reason:
            appt.notes = f"Cancelled: {reason}\n{appt.notes or ''}"
        db.session.commit()

        logger.info("AppointmentService: appointment %s cancelled", appointment_id)

        # Cancellation notification
        try:
            AppointmentService._send_cancellation_notice(appt, reason)
        except Exception as e:
            logger.warning("AppointmentService: cancellation notification failed: %s", e)

        return appt

    # ─────────────────────────────────────────────────────────────
    # Rescheduling
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def reschedule_appointment(
        appointment_id: str,
        new_start_time: datetime,
        new_end_time: Optional[datetime] = None,
        reason: Optional[str] = None,
    ) -> Optional[Appointment]:
        appt = Appointment.query.filter_by(id=appointment_id).first()
        if not appt:
            return None

        if appt.status in ("completed", "cancelled"):
            raise ValueError(f"Cannot reschedule a {appt.status} appointment")

        if new_end_time is None:
            duration = appt.end_time - appt.start_time
            new_end_time = new_start_time + duration

        # Conflict check (excluding current appointment)
        conflict = AppointmentService._check_conflict(
            doctor_id=str(appt.doctor_id),
            start_time=new_start_time,
            end_time=new_end_time,
            exclude_id=appointment_id,
        )
        if conflict:
            raise ValueError(f"New slot conflicts with appointment {conflict.id}")

        old_time = appt.start_time
        appt.start_time = new_start_time
        appt.end_time = new_end_time
        if reason:
            appt.notes = f"Rescheduled: {reason}\n{appt.notes or ''}"
        db.session.commit()

        logger.info(
            "AppointmentService: appointment %s rescheduled from %s to %s",
            appointment_id, old_time, new_start_time,
        )

        # Reschedule notification
        try:
            AppointmentService._send_reschedule_notice(appt, old_time)
        except Exception as e:
            logger.warning("AppointmentService: reschedule notification failed: %s", e)

        return appt

    # ─────────────────────────────────────────────────────────────
    # Status update
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def update_appointment_status(appointment_id: str, status: str) -> Optional[Appointment]:
        appt = Appointment.query.filter_by(id=appointment_id).first()
        if not appt:
            return None
        appt.status = status
        db.session.commit()
        return appt

    # ─────────────────────────────────────────────────────────────
    # Serialization helper
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def to_dict(appt: Appointment) -> dict:
        return {
            "id": str(appt.id),
            "patient_id": str(appt.patient_id),
            "doctor_id": str(appt.doctor_id),
            "start_time": appt.start_time.isoformat() if appt.start_time else None,
            "end_time": appt.end_time.isoformat() if appt.end_time else None,
            "status": appt.status,
            "type": appt.type,
            "reason": appt.reason,
            "notes": appt.notes,
            "meeting_link": appt.meeting_link,
            "created_at": appt.created_at.isoformat() if appt.created_at else None,
        }

    # ─────────────────────────────────────────────────────────────
    # Internal: notification triggers
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _send_booking_confirmation(appt: Appointment) -> None:
        from app.tasks.notification_tasks import send_notification_async
        from app.models.patient import PatientProfile
        from app.models.user import User
        
        email = None
        name = "Patient"
        profile = PatientProfile.query.get(appt.patient_id)
        if profile:
            user = User.query.get(profile.user_id)
            if user:
                name = user.first_name or "Patient"
                email = user.email

        send_notification_async(
            user_id=str(appt.patient_id),
            title="Appointment Confirmed",
            body=(
                f"Your appointment has been booked for "
                f"{appt.start_time.strftime('%A, %B %d at %I:%M %p UTC') if appt.start_time else 'a scheduled time'}."
            ),
            notification_type="appointment_reminder",
            priority="normal",
            action_url="/patient/appointments",
            email=email,
            name=name,
        )

    @staticmethod
    def _send_cancellation_notice(appt: Appointment, reason: Optional[str]) -> None:
        from app.tasks.notification_tasks import send_notification_async
        from app.models.patient import PatientProfile
        from app.models.user import User
        
        email = None
        name = "Patient"
        profile = PatientProfile.query.get(appt.patient_id)
        if profile:
            user = User.query.get(profile.user_id)
            if user:
                name = user.first_name or "Patient"
                email = user.email

        body = "Your appointment has been cancelled."
        if reason:
            body += f" Reason: {reason}"
        send_notification_async(
            user_id=str(appt.patient_id),
            title="Appointment Cancelled",
            body=body,
            notification_type="appointment_reminder",
            priority="high",
            action_url="/patient/appointments",
            email=email,
            name=name,
        )

    @staticmethod
    def _send_reschedule_notice(appt: Appointment, old_time: datetime) -> None:
        from app.tasks.notification_tasks import send_notification_async
        from app.models.patient import PatientProfile
        from app.models.user import User
        
        email = None
        name = "Patient"
        profile = PatientProfile.query.get(appt.patient_id)
        if profile:
            user = User.query.get(profile.user_id)
            if user:
                name = user.first_name or "Patient"
                email = user.email

        send_notification_async(
            user_id=str(appt.patient_id),
            title="Appointment Rescheduled",
            body=(
                f"Your appointment originally at {old_time.strftime('%B %d at %I:%M %p UTC')} "
                f"has been moved to {appt.start_time.strftime('%A, %B %d at %I:%M %p UTC') if appt.start_time else 'a new time'}."
            ),
            notification_type="appointment_reminder",
            priority="high",
            action_url="/patient/appointments",
            email=email,
            name=name,
        )
