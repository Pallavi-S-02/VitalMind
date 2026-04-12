"""
telemedicine_service.py — Business logic layer for video consultations.

Orchestrates the Daily.co client, appointment DB updates, and Redis presence.

Key responsibilities:
  - room_name ↔ appointment_id mapping  (Redis key: vitalmind:tele:rooms)
  - Ensure idempotent room creation (same appointment → same room)
  - Write `meeting_link` back to the Appointment record
  - Generate role-appropriate tokens (doctor=owner, patient=guest)
  - Auto-create rooms 15 minutes before scheduled appointment (Celery beat task)
  - Tear down rooms and update appointment status on call end
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.integrations.daily_client import get_daily_client
from app.models.db import db
from app.models.appointment import Appointment

logger = logging.getLogger(__name__)

_REDIS_ROOM_TTL = 7200            # 2 hours
_ROOM_PREFIX = "vitalmind-"       # e.g. vitalmind-a3f8b23c


class TelemedicineService:

    # ─────────────────────────────────────────────────────────────
    # Room generation helpers
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _room_name_for_appointment(appointment_id: str) -> str:
        """Deterministic room name derived from appointment ID (URL-safe)."""
        short = re.sub(r"[^a-z0-9]", "", appointment_id.lower())[:16]
        return f"{_ROOM_PREFIX}{short}"

    @staticmethod
    def _store_room_mapping(room_name: str, appointment_id: str, domain_url: str) -> None:
        """Cache room → appointment mapping in Redis."""
        try:
            import redis as redis_lib, json
            r = redis_lib.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                db=int(os.getenv("REDIS_DB", 0)),
                decode_responses=True,
            )
            r.setex(
                f"vitalmind:tele:room:{room_name}",
                _REDIS_ROOM_TTL,
                json.dumps({"appointment_id": appointment_id, "url": domain_url}),
            )
        except Exception as exc:
            logger.warning("TelemedicineService: Redis room cache failed: %s", exc)

    # ─────────────────────────────────────────────────────────────
    # Core operations
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def create_room(appointment_id: str, doctor_id: str) -> dict:
        """
        Create (or retrieve existing) Daily room for an appointment.

        Returns:
            {
              "room_name": str,
              "room_url":  str,          # https://<domain>.daily.co/<room>
              "appointment_id": str,
              "created": bool            # False if room already existed
            }
        """
        daily = get_daily_client()
        room_name = TelemedicineService._room_name_for_appointment(appointment_id)

        # Idempotent: check if room already exists
        existing = daily.get_room(room_name)
        if existing and existing.get("url"):
            logger.info("TelemedicineService: room '%s' already exists", room_name)
            url = existing["url"]
            TelemedicineService._store_room_mapping(room_name, appointment_id, url)
            TelemedicineService._update_appointment_link(appointment_id, url)
            return {
                "room_name": room_name,
                "room_url": url,
                "appointment_id": appointment_id,
                "created": False,
            }

        # Create new room
        room = daily.create_room(
            name=room_name,
            privacy="private",
            max_participants=3,      # doctor + patient + optional observer
            enable_recording=False,
        )

        if not room:
            # Daily not configured → generate a mock room URL for dev
            logger.warning(
                "TelemedicineService: Daily not configured — using mock room URL"
            )
            mock_url = f"https://vitalmind.daily.co/{room_name}"
            TelemedicineService._update_appointment_link(appointment_id, mock_url)
            return {
                "room_name": room_name,
                "room_url": mock_url,
                "appointment_id": appointment_id,
                "created": True,
            }

        url = room["url"]
        TelemedicineService._store_room_mapping(room_name, appointment_id, url)
        TelemedicineService._update_appointment_link(appointment_id, url)

        logger.info(
            "TelemedicineService: created room '%s' for appointment %s",
            room_name, appointment_id,
        )
        return {
            "room_name": room_name,
            "room_url": url,
            "appointment_id": appointment_id,
            "created": True,
        }

    @staticmethod
    def join_room(
        room_name: str,
        user_id: str,
        user_name: str,
        role: str,                  # "doctor" | "patient" | "observer"
    ) -> dict:
        """
        Generate a meeting token for a user to join an existing room.

        Returns:
            {
              "token":    str,
              "room_url": str,
              "room_name": str,
              "is_owner": bool
            }
        """
        daily = get_daily_client()
        is_owner = role in ("doctor", "admin")

        token = daily.create_meeting_token(
            room_name=room_name,
            user_id=user_id,
            user_name=user_name,
            is_owner=is_owner,
        )

        # Get room URL
        room_info = daily.get_room(room_name) or {}
        room_url = room_info.get("url", f"https://vitalmind.daily.co/{room_name}")

        if not token:
            # Mock token for dev environments
            logger.warning("TelemedicineService: mock token generated (Daily not configured)")
            token = f"mock-token-{uuid.uuid4()}"

        return {
            "token": token,
            "room_url": room_url,
            "room_name": room_name,
            "is_owner": is_owner,
            "domain": os.getenv("DAILY_DOMAIN", "vitalmind"),
        }

    @staticmethod
    def end_room(appointment_id: str) -> dict:
        """
        End a call: delete the Daily room and update appointment status.

        Returns:
            { "success": bool, "appointment_id": str, "message": str }
        """
        daily = get_daily_client()
        room_name = TelemedicineService._room_name_for_appointment(appointment_id)

        deleted = daily.delete_room(room_name)

        # Update appointment status → completed
        try:
            appt = Appointment.query.filter_by(id=appointment_id).first()
            if appt:
                appt.status = "completed"
                db.session.commit()
                logger.info("TelemedicineService: appointment %s → completed", appointment_id)
        except Exception as exc:
            logger.error("TelemedicineService: status update failed: %s", exc)
            db.session.rollback()

        # Clean up Redis
        try:
            import redis as redis_lib
            r = redis_lib.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                db=int(os.getenv("REDIS_DB", 0)),
                decode_responses=True,
            )
            r.delete(f"vitalmind:tele:room:{room_name}")
        except Exception:
            pass

        return {
            "success": deleted,
            "appointment_id": appointment_id,
            "message": "Room deleted and appointment marked completed" if deleted else
                       "Appointment completed (room deletion skipped — Daily not configured)",
        }

    @staticmethod
    def get_room_status(appointment_id: str) -> dict:
        """
        Return room presence info (active participants, URL).
        """
        daily = get_daily_client()
        room_name = TelemedicineService._room_name_for_appointment(appointment_id)

        presence = daily.get_room_presence(room_name) or {}
        room_info = daily.get_room(room_name) or {}

        return {
            "room_name": room_name,
            "room_url": room_info.get("url"),
            "participant_count": presence.get("total_count", 0),
            "participants": presence.get("data", []),
            "appointment_id": appointment_id,
        }

    # ─────────────────────────────────────────────────────────────
    # DB helper
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _update_appointment_link(appointment_id: str, meeting_link: str) -> None:
        """Write the meeting URL back to the Appointment record."""
        try:
            appt = Appointment.query.filter_by(id=appointment_id).first()
            if appt:
                appt.meeting_link = meeting_link
                appt.type = "video"
                db.session.commit()
        except Exception as exc:
            logger.error("TelemedicineService: appointment link update failed: %s", exc)
            db.session.rollback()

    # ─────────────────────────────────────────────────────────────
    # Pre-appointment auto-creation (called by Celery beat)
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def provision_upcoming_rooms(minutes_ahead: int = 15) -> list[str]:
        """
        Find video appointments starting within `minutes_ahead` minutes
        that don't yet have a room, and create them.

        Returns list of appointment IDs provisioned.
        """
        now = datetime.now(timezone.utc)
        window_end = now + timedelta(minutes=minutes_ahead)

        try:
            upcoming = (
                Appointment.query
                .filter(
                    Appointment.type == "video",
                    Appointment.status == "scheduled",
                    Appointment.meeting_link.is_(None),
                    Appointment.start_time >= now,
                    Appointment.start_time <= window_end,
                )
                .all()
            )
        except Exception as exc:
            logger.error("TelemedicineService: could not query upcoming appointments: %s", exc)
            return []

        provisioned = []
        for appt in upcoming:
            try:
                result = TelemedicineService.create_room(
                    appointment_id=str(appt.id),
                    doctor_id=str(appt.doctor_id),
                )
                provisioned.append(str(appt.id))
                logger.info(
                    "TelemedicineService: provisioned room for appointment %s at %s",
                    appt.id, appt.start_time,
                )
            except Exception as exc:
                logger.error("TelemedicineService: failed to provision appt %s: %s", appt.id, exc)

        return provisioned
