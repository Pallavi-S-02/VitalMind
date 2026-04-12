"""
vitals_service.py — VitalMind Vitals Service Layer.

Orchestrates vitals data flow between:
  - PostgreSQL (VitalsReading + IoTDevice models, source of truth for readings)
  - InfluxDB (time-series analytics via influxdb_client)
  - Redis (sub-millisecond cache via iot_gateway)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.models.vitals import VitalsReading
from app.models.device import IoTDevice
from app.models.db import db
from app.integrations.influxdb_client import (
    query_latest_vitals,
    query_vitals_history,
    query_aggregate_stats,
)
from app.integrations.iot_gateway import (
    ingest_vitals,
    get_cached_latest_vitals,
    generate_device_token,
    verify_device_token,
)

logger = logging.getLogger(__name__)


class VitalsService:

    # ── Device management ─────────────────────────────────────────────────────

    @staticmethod
    def register_device(patient_id: str, data: dict) -> tuple[IoTDevice, str]:
        """
        Register a new IoT device for a patient and return (device, token).
        Raises ValueError if device_identifier is already registered.
        """
        existing = IoTDevice.query.filter_by(
            device_identifier=data["device_identifier"]
        ).first()
        if existing:
            raise ValueError(
                f"Device '{data['device_identifier']}' is already registered."
            )

        device = IoTDevice(
            id=str(uuid.uuid4()),
            patient_id=patient_id,
            device_type=data.get("device_type", "unknown"),
            device_identifier=data["device_identifier"],
            brand=data.get("brand"),
            model=data.get("model"),
            is_active=True,
            connection_details=data.get("connection_details", {}),
        )
        db.session.add(device)
        db.session.commit()

        token = generate_device_token(patient_id, str(device.id))
        logger.info("Device registered: %s for patient %s", device.id, patient_id)
        return device, token

    @staticmethod
    def get_patient_devices(patient_id: str) -> list[IoTDevice]:
        return IoTDevice.query.filter_by(patient_id=patient_id, is_active=True).all()

    @staticmethod
    def deactivate_device(device_id: str, patient_id: str) -> bool:
        device = IoTDevice.query.filter_by(id=device_id, patient_id=patient_id).first()
        if not device:
            return False
        device.is_active = False
        db.session.commit()
        return True

    # ── Vitals ingestion ──────────────────────────────────────────────────────

    @staticmethod
    def ingest_device_vitals(
        device_id: str,
        token: str,
        raw_payload: dict[str, Any],
        timestamp: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """
        Authenticated vitals ingestion from an IoT device.
        1. Looks up device + patient in PostgreSQL
        2. Verifies HMAC device token
        3. Calls iot_gateway.ingest_vitals (validates, writes InfluxDB, caches Redis)
        4. Also mirrors to PostgreSQL VitalsReading for audit trail
        """
        device = IoTDevice.query.filter_by(id=device_id, is_active=True).first()
        if not device:
            raise PermissionError(f"Device {device_id} not found or inactive")

        if not verify_device_token(token, str(device.patient_id), str(device.id)):
            raise PermissionError("Invalid or expired device token")

        # Update last sync
        device.last_sync = datetime.now(timezone.utc)
        db.session.commit()

        # Run the full ingestion pipeline (inflate → InfluxDB → Redis → pub/sub)
        result = ingest_vitals(
            patient_id=str(device.patient_id),
            device_id=str(device.id),
            source=device.device_type,
            raw_payload=raw_payload,
            timestamp=timestamp,
        )

        # Mirror to PostgreSQL as an audit VitalsReading
        if result["status"] == "accepted":
            vitals = result["vitals_stored"]
            reading = VitalsReading(
                id=str(uuid.uuid4()),
                patient_id=str(device.patient_id),
                device_id=str(device.id),
                timestamp=timestamp or datetime.now(timezone.utc),
                heart_rate=int(vitals.get("heart_rate")) if vitals.get("heart_rate") else None,
                blood_pressure_systolic=int(vitals.get("systolic_bp")) if vitals.get("systolic_bp") else None,
                blood_pressure_diastolic=int(vitals.get("diastolic_bp")) if vitals.get("diastolic_bp") else None,
                temperature=vitals.get("temperature_c"),
                oxygen_saturation=vitals.get("spo2"),
                respiratory_rate=int(vitals.get("respiratory_rate")) if vitals.get("respiratory_rate") else None,
                blood_glucose=vitals.get("blood_glucose_mgdl"),
                weight=vitals.get("weight_kg"),
                source=device.device_type,
            )
            try:
                db.session.add(reading)
                db.session.commit()
            except Exception as exc:
                logger.error("Failed to persist VitalsReading to Postgres: %s", exc)
                db.session.rollback()

        return result

    @staticmethod
    def ingest_manual_vitals(
        patient_id: str,
        raw_payload: dict[str, Any],
        timestamp: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """Manual vitals entry (no device token required — user is authenticated via JWT)."""
        result = ingest_vitals(
            patient_id=patient_id,
            device_id="manual",
            source="manual_entry",
            raw_payload=raw_payload,
            timestamp=timestamp,
        )

        if result["status"] == "accepted":
            vitals = result["vitals_stored"]
            ts = timestamp or datetime.now(timezone.utc)
            reading = VitalsReading(
                id=str(uuid.uuid4()),
                patient_id=patient_id,
                timestamp=ts,
                heart_rate=int(vitals.get("heart_rate")) if vitals.get("heart_rate") else None,
                blood_pressure_systolic=int(vitals.get("systolic_bp")) if vitals.get("systolic_bp") else None,
                blood_pressure_diastolic=int(vitals.get("diastolic_bp")) if vitals.get("diastolic_bp") else None,
                temperature=vitals.get("temperature_c"),
                oxygen_saturation=vitals.get("spo2"),
                respiratory_rate=int(vitals.get("respiratory_rate")) if vitals.get("respiratory_rate") else None,
                blood_glucose=vitals.get("blood_glucose_mgdl"),
                weight=vitals.get("weight_kg"),
                source="manual_entry",
            )
            try:
                db.session.add(reading)
                db.session.commit()
            except Exception as exc:
                logger.error("Failed to persist manual VitalsReading: %s", exc)
                db.session.rollback()

        return result

    # ── Vitals retrieval ──────────────────────────────────────────────────────

    @staticmethod
    def get_current_vitals(patient_id: str) -> dict[str, Any]:
        """
        Get the latest vitals for a patient.
        Try Redis cache first (microseconds), fall back to InfluxDB, then PostgreSQL.
        """
        # 1. Redis hot cache
        cached = get_cached_latest_vitals(patient_id)
        if cached:
            return {**cached, "_source": "cache"}

        # 2. InfluxDB time-series
        influx_data = query_latest_vitals(patient_id)
        if influx_data:
            return {**influx_data, "_source": "influxdb"}

        # 3. PostgreSQL fallback (most recent row)
        reading = (
            VitalsReading.query
            .filter_by(patient_id=patient_id)
            .order_by(VitalsReading.timestamp.desc())
            .first()
        )
        if reading:
            return {
                "heart_rate":         reading.heart_rate,
                "systolic_bp":        reading.blood_pressure_systolic,
                "diastolic_bp":       reading.blood_pressure_diastolic,
                "temperature_c":      reading.temperature,
                "spo2":               reading.oxygen_saturation,
                "respiratory_rate":   reading.respiratory_rate,
                "blood_glucose_mgdl": reading.blood_glucose,
                "weight_kg":          reading.weight,
                "_timestamp":         reading.timestamp.isoformat(),
                "_source":            "postgres",
            }

        return {"_source": "none", "_message": "No vitals recorded yet"}

    @staticmethod
    def get_vitals_history(
        patient_id: str,
        hours: int = 24,
        field: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Time-series history from InfluxDB."""
        return query_vitals_history(patient_id, hours=hours, field=field)

    @staticmethod
    def get_vitals_stats(
        patient_id: str,
        field: str,
        hours: int = 24,
    ) -> dict[str, float]:
        """Aggregate stats (mean/min/max/stddev) from InfluxDB."""
        return query_aggregate_stats(patient_id, field=field, hours=hours)

    @staticmethod
    def get_postgres_history(
        patient_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """PostgreSQL fallback history for audit / when InfluxDB is unavailable."""
        readings = (
            VitalsReading.query
            .filter_by(patient_id=patient_id)
            .order_by(VitalsReading.timestamp.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id":             str(r.id),
                "timestamp":      r.timestamp.isoformat(),
                "heart_rate":     r.heart_rate,
                "systolic_bp":    r.blood_pressure_systolic,
                "diastolic_bp":   r.blood_pressure_diastolic,
                "temperature_c":  r.temperature,
                "spo2":           r.oxygen_saturation,
                "respiratory_rate": r.respiratory_rate,
                "blood_glucose_mgdl": r.blood_glucose,
                "weight_kg":      r.weight,
                "source":         r.source,
            }
            for r in readings
        ]
