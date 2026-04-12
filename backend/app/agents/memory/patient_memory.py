"""
patient_memory.py — Patient-specific context retrieval with Redis caching.

Fetches patient history, allergies, medications, and vitals summary from
PostgreSQL via SQLAlchemy, then caches the result in Redis so subsequent
agent invocations within the same session are instantaneous.

Cache key : vitalmind:patient_ctx:{patient_id}
Cache TTL : REDIS_PATIENT_CTX_TTL  (default 15 minutes)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

import redis

logger = logging.getLogger(__name__)

_PATIENT_CTX_PREFIX = "vitalmind:patient_ctx:"
_DEFAULT_TTL = int(os.getenv("REDIS_PATIENT_CTX_TTL", 900))  # 15 min


def _get_redis() -> redis.Redis:
    return redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
    )


class PatientMemory:
    """
    Retrieves and caches comprehensive patient context for agent use.

    The context dict returned by `load()` has the structure:
    {
        "patient_id": str,
        "name": str,
        "date_of_birth": str | None,
        "gender": str | None,
        "blood_type": str | None,
        "allergies": list[str],
        "current_medications": list[{"name": str, "dose": str, "frequency": str}],
        "recent_diagnoses": list[str],
        "chronic_conditions": list[str],
        "last_visit": str | None,
        "emergency_contact": str | None,
    }
    """

    def __init__(self, patient_id: str, ttl: int = _DEFAULT_TTL) -> None:
        self.patient_id = patient_id
        self.ttl = ttl
        self._redis = _get_redis()
        self._cache_key = f"{_PATIENT_CTX_PREFIX}{patient_id}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> dict[str, Any]:
        """
        Return the patient context dict.
        Checks Redis cache first; falls back to PostgreSQL if stale/missing.
        """
        cached = self._load_from_cache()
        if cached:
            logger.debug("Patient %s context loaded from Redis cache.", self.patient_id)
            return cached

        ctx = self._load_from_db()
        self._save_to_cache(ctx)
        return ctx

    def invalidate(self) -> None:
        """Force-evict the cache so next load() re-fetches from DB."""
        try:
            self._redis.delete(self._cache_key)
            logger.info("Patient %s context cache invalidated.", self.patient_id)
        except Exception as exc:
            logger.warning("PatientMemory.invalidate failed: %s", exc)

    def get_medication_names(self) -> list[str]:
        """Convenience: return just a flat list of current medication names."""
        ctx = self.load()
        return [m["name"] for m in ctx.get("current_medications", [])]

    def get_allergy_list(self) -> list[str]:
        """Convenience: return the allergy list."""
        return self.load().get("allergies", [])

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_from_cache(self) -> Optional[dict[str, Any]]:
        try:
            raw = self._redis.get(self._cache_key)
            if raw:
                return json.loads(raw)
        except Exception as exc:
            logger.warning("PatientMemory cache read failed: %s", exc)
        return None

    def _save_to_cache(self, ctx: dict[str, Any]) -> None:
        try:
            self._redis.setex(self._cache_key, self.ttl, json.dumps(ctx, default=str))
        except Exception as exc:
            logger.warning("PatientMemory cache write failed: %s", exc)

    def _load_from_db(self) -> dict[str, Any]:
        """Query PostgreSQL for the patient's full context."""
        try:
            from flask import current_app
            from app.models import User, PatientProfile, Medication, Prescription

            with current_app.app_context():
                # Core user + profile
                user = User.query.get(self.patient_id)
                if not user:
                    logger.warning("PatientMemory: user %s not found.", self.patient_id)
                    return self._empty_context()

                profile: Optional[PatientProfile] = getattr(user, "patient_profile", None)

                # Medications from active prescriptions
                medications = []
                if profile:
                    prescriptions = Prescription.query.filter_by(
                        patient_id=profile.id, status="active"
                    ).all()
                    medications = [
                        {
                            "name": p.medication.name if p.medication else "Unknown",
                            "dose": p.dosage or "",
                            "frequency": p.frequency or "",
                        }
                        for p in prescriptions
                    ]

                ctx = {
                    "patient_id": str(self.patient_id),
                    "name": f"{user.first_name} {user.last_name}",
                    "date_of_birth": (
                        profile.date_of_birth.isoformat() if profile and profile.date_of_birth else None
                    ),
                    "gender": profile.gender if profile else None,
                    "blood_type": profile.blood_type if profile else None,
                    "allergies": profile.allergies if (profile and profile.allergies) else [],
                    "current_medications": medications,
                    "recent_diagnoses": [],   # Extended by ReportReader agent
                    "chronic_conditions": (
                        profile.chronic_conditions if (profile and profile.chronic_conditions) else []
                    ),
                    "last_visit": None,
                    "emergency_contact": (
                        profile.emergency_contact if profile else None
                    ),
                    "loaded_at": datetime.utcnow().isoformat(),
                }
                logger.info("PatientMemory: loaded DB context for patient %s.", self.patient_id)
                return ctx

        except Exception as exc:
            logger.error("PatientMemory._load_from_db failed: %s", exc)
            return self._empty_context()

    def _empty_context(self) -> dict[str, Any]:
        return {
            "patient_id": str(self.patient_id),
            "name": "Unknown",
            "date_of_birth": None,
            "gender": None,
            "blood_type": None,
            "allergies": [],
            "current_medications": [],
            "recent_diagnoses": [],
            "chronic_conditions": [],
            "last_visit": None,
            "emergency_contact": None,
            "loaded_at": datetime.utcnow().isoformat(),
        }
