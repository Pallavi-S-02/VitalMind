"""
iot_gateway.py — VitalMind IoT Device Gateway.

Handles:
  - Device registration and token management (HMAC-SHA256 signed tokens)
  - Incoming vitals payload validation and normalisation
  - Mirror of latest vitals to Redis for sub-millisecond access
  - Forwarding to InfluxDB via influxdb_client module

Device token format:
  "vtk_<base64(patient_id:device_id:timestamp)>.<hmac_signature>"
"""

from __future__ import annotations

import hashlib
import hmac
import base64
import json
import logging
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Optional

from app.integrations.influxdb_client import write_vitals

logger = logging.getLogger(__name__)

_IOT_SECRET = os.getenv("IOT_DEVICE_SECRET", "change-me-in-production-iot-secret")
_REDIS_TTL_SECONDS = 300  # 5 minutes cache for latest vitals


# ─── Vitals payload schema ───────────────────────────────────────────────────

# Accepted field names → canonical name (normalized)
ACCEPTED_FIELDS = {
    "heart_rate", "spo2", "oxygen_saturation",
    "systolic_bp", "blood_pressure_systolic",
    "diastolic_bp", "blood_pressure_diastolic",
    "temperature", "temperature_c",
    "respiratory_rate",
    "blood_glucose", "blood_glucose_mgdl",
    "weight", "weight_kg",
}

# Physiologically plausible ranges for each canonical field
PLAUSIBLE_RANGES: dict[str, tuple[float, float]] = {
    "heart_rate":           (20,  300),
    "spo2":                 (50,  100),
    "systolic_bp":          (50,  300),
    "diastolic_bp":         (20,  200),
    "temperature_c":        (30,  45),
    "respiratory_rate":     (5,   60),
    "blood_glucose_mgdl":   (20,  800),
    "weight_kg":            (1,   500),
}


# ─── Token generation / verification ─────────────────────────────────────────

def generate_device_token(patient_id: str, device_id: str) -> str:
    """
    Generate a signed device authentication token.
    Format: vtk_<base64_payload>.<hmac_hex>
    """
    ts = str(int(time.time()))
    payload_str = f"{patient_id}:{device_id}:{ts}"
    payload_b64 = base64.urlsafe_b64encode(payload_str.encode()).decode()

    sig = hmac.new(
        _IOT_SECRET.encode(),
        payload_b64.encode(),
        hashlib.sha256,
    ).hexdigest()

    return f"vtk_{payload_b64}.{sig}"


def verify_device_token(token: str, patient_id: str, device_id: str) -> bool:
    """
    Verify a device token was issued for this patient+device pair.
    Tokens expire after 365 days (long-lived for IoT devices).
    """
    try:
        if not token.startswith("vtk_"):
            return False

        body = token[4:]  # strip "vtk_"
        payload_b64, provided_sig = body.split(".", 1)

        # Verify signature
        expected_sig = hmac.new(
            _IOT_SECRET.encode(),
            payload_b64.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(provided_sig, expected_sig):
            return False

        # Decode and verify payload
        payload_str = base64.urlsafe_b64decode(payload_b64).decode()
        pid, did, ts_str = payload_str.split(":", 2)

        if pid != str(patient_id) or did != str(device_id):
            return False

        # Check expiry (365 days)
        age_days = (time.time() - int(ts_str)) / 86400
        if age_days > 365:
            logger.warning("IoT token expired for device %s", device_id)
            return False

        return True

    except Exception as exc:
        logger.warning("IoT token verification failed: %s", exc)
        return False


# ─── Payload validation ───────────────────────────────────────────────────────

def validate_vitals_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """
    Validate and normalise a raw vitals payload from an IoT device.

    Returns (cleaned_vitals, warnings_list).
    - cleaned_vitals: dict with only valid, in-range fields
    - warnings_list : list of human-readable validation warnings
    """
    cleaned: dict[str, Any] = {}
    warnings: list[str] = []

    from app.integrations.influxdb_client import VITALS_FIELD_MAP

    for key, value in payload.items():
        if key not in ACCEPTED_FIELDS:
            continue

        # Normalise to canonical name
        canonical = VITALS_FIELD_MAP.get(key, key)

        if value is None:
            warnings.append(f"{key}: null value skipped")
            continue

        try:
            numeric = float(value)
        except (TypeError, ValueError):
            warnings.append(f"{key}: non-numeric value '{value}' skipped")
            continue

        # Plausibility check
        lo, hi = PLAUSIBLE_RANGES.get(canonical, (-1e9, 1e9))
        if not (lo <= numeric <= hi):
            warnings.append(
                f"{key}: value {numeric} outside plausible range [{lo}, {hi}] — skipped"
            )
            continue

        cleaned[canonical] = numeric

    if not cleaned:
        warnings.append("No valid vitals fields in payload")

    return cleaned, warnings


# ─── Redis mirror ─────────────────────────────────────────────────────────────

def _redis_client():
    """Lazy Redis client for vitals caching."""
    try:
        import redis
        return redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True,
        )
    except Exception as exc:
        logger.warning("Redis unavailable for vitals cache: %s", exc)
        return None


def cache_latest_vitals(patient_id: str, vitals: dict[str, Any]) -> None:
    """Mirror the latest vitals to Redis for fast reads (sub-ms)."""
    r = _redis_client()
    if r is None:
        return
    key = f"vitals:latest:{patient_id}"
    try:
        vitals_with_ts = {**vitals, "_cached_at": datetime.now(timezone.utc).isoformat()}
        r.setex(key, _REDIS_TTL_SECONDS, json.dumps(vitals_with_ts))
    except Exception as exc:
        logger.warning("Redis vitals cache write failed for patient %s: %s", patient_id, exc)


def get_cached_latest_vitals(patient_id: str) -> Optional[dict[str, Any]]:
    """Retrieve latest vitals from Redis cache."""
    r = _redis_client()
    if r is None:
        return None
    key = f"vitals:latest:{patient_id}"
    try:
        raw = r.get(key)
        if raw:
            return json.loads(raw)
    except Exception as exc:
        logger.warning("Redis vitals cache read failed for patient %s: %s", patient_id, exc)
    return None


# ─── Main ingestion entry point ───────────────────────────────────────────────

def ingest_vitals(
    patient_id: str,
    device_id: str,
    source: str,
    raw_payload: dict[str, Any],
    timestamp: Optional[datetime] = None,
) -> dict[str, Any]:
    """
    Full vitals ingestion pipeline:
    1. Validate and normalise the payload
    2. Write to InfluxDB (time-series storage)
    3. Mirror latest to Redis (fast access)
    4. Publish alert event to Redis pub/sub for monitoring agent pickup

    Returns a result dict with status, warnings, and cleaned vitals.
    """
    ts = timestamp or datetime.now(timezone.utc)

    # 1. Validate
    cleaned, warnings = validate_vitals_payload(raw_payload)

    if not cleaned:
        return {
            "status": "rejected",
            "reason": "No valid vitals in payload",
            "warnings": warnings,
        }

    # 2. Write to InfluxDB
    influx_ok = write_vitals(
        patient_id=patient_id,
        vitals=cleaned,
        device_id=device_id,
        source=source,
        timestamp=ts,
    )

    # 3. Mirror to Redis
    cache_latest_vitals(patient_id, cleaned)

    # 4. Publish event to Redis pub/sub for monitoring agent
    _publish_vitals_event(patient_id, device_id, cleaned, ts)

    return {
        "status": "accepted",
        "vitals_stored": cleaned,
        "influxdb_ok": influx_ok,
        "warnings": warnings,
        "timestamp": ts.isoformat(),
    }


def _publish_vitals_event(
    patient_id: str,
    device_id: str,
    vitals: dict[str, Any],
    ts: datetime,
) -> None:
    """Publish a vitals ingestion event to Redis pub/sub for the monitoring agent."""
    r = _redis_client()
    if r is None:
        return
    try:
        event = json.dumps({
            "type": "vitals_update",
            "patient_id": str(patient_id),
            "device_id": str(device_id),
            "vitals": vitals,
            "timestamp": ts.isoformat(),
        })
        r.publish("vitalmind:vitals_events", event)
    except Exception as exc:
        logger.warning("Redis pub/sub publish failed: %s", exc)
