"""
influxdb_client.py — VitalMind InfluxDB time-series wrapper.

Handles all writes and queries for patient vitals data.
Uses InfluxDB 2.x client (influxdb-client library, already in requirements.txt).

Bucket layout:
  bucket: "vitals"
  measurement: "patient_vitals"
  tags:
    patient_id  : UUID string
    device_id   : UUID string (or "manual")
    source      : e.g. "fitbit", "apple_health", "manual_entry"
  fields:
    heart_rate, spo2, systolic_bp, diastolic_bp,
    temperature_c, respiratory_rate, blood_glucose_mgdl, weight_kg
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ─── Lazy client init ────────────────────────────────────────────────────────
_influx_client = None
_write_api = None
_query_api = None

INFLUX_URL    = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUX_TOKEN  = os.getenv("INFLUXDB_TOKEN", "")
INFLUX_ORG    = os.getenv("INFLUXDB_ORG", "vitalmind")
INFLUX_BUCKET = os.getenv("INFLUXDB_BUCKET", "vitals")


def _get_write_api():
    global _influx_client, _write_api
    if _write_api is not None:
        return _write_api
    try:
        from influxdb_client import InfluxDBClient
        from influxdb_client.client.write_api import SYNCHRONOUS
        _influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        _write_api = _influx_client.write_api(write_options=SYNCHRONOUS)
        logger.info("InfluxDB write API initialized")
    except Exception as exc:
        logger.warning("InfluxDB unavailable (write): %s", exc)
    return _write_api


def _get_query_api():
    global _influx_client, _query_api
    if _query_api is not None:
        return _query_api
    try:
        from influxdb_client import InfluxDBClient
        _influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        _query_api = _influx_client.query_api()
        logger.info("InfluxDB query API initialized")
    except Exception as exc:
        logger.warning("InfluxDB unavailable (query): %s", exc)
    return _query_api


# ─── Field mapping ────────────────────────────────────────────────────────────

# Maps incoming payload keys → InfluxDB field names
VITALS_FIELD_MAP = {
    "heart_rate":               "heart_rate",
    "spo2":                     "spo2",
    "oxygen_saturation":        "spo2",
    "blood_pressure_systolic":  "systolic_bp",
    "systolic_bp":              "systolic_bp",
    "blood_pressure_diastolic": "diastolic_bp",
    "diastolic_bp":             "diastolic_bp",
    "temperature":              "temperature_c",
    "temperature_c":            "temperature_c",
    "respiratory_rate":         "respiratory_rate",
    "blood_glucose":            "blood_glucose_mgdl",
    "blood_glucose_mgdl":       "blood_glucose_mgdl",
    "weight":                   "weight_kg",
    "weight_kg":                "weight_kg",
}


# ─── Write ────────────────────────────────────────────────────────────────────

def write_vitals(
    patient_id: str,
    vitals: dict[str, Any],
    device_id: str = "manual",
    source: str = "manual_entry",
    timestamp: Optional[datetime] = None,
) -> bool:
    """
    Write a single vitals reading to InfluxDB.

    Parameters
    ----------
    patient_id : Patient UUID
    vitals     : Dict of vital sign values (e.g. {"heart_rate": 72, "spo2": 98.0})
    device_id  : IoT device UUID or "manual"
    source     : e.g. "fitbit", "apple_health", "manual_entry"
    timestamp  : Reading timestamp; defaults to now (UTC)

    Returns True on success, False on failure.
    """
    write_api = _get_write_api()
    if write_api is None:
        logger.warning("InfluxDB unavailable — vitals write skipped for patient %s", patient_id)
        return False

    ts = timestamp or datetime.now(timezone.utc)

    # Build fields from the vitals dict using the field mapping
    fields: dict[str, float] = {}
    for raw_key, value in vitals.items():
        influx_key = VITALS_FIELD_MAP.get(raw_key)
        if influx_key and value is not None:
            try:
                fields[influx_key] = float(value)
            except (TypeError, ValueError):
                pass

    if not fields:
        logger.warning("No valid fields to write for patient %s", patient_id)
        return False

    try:
        from influxdb_client import Point
        point = (
            Point("patient_vitals")
            .tag("patient_id", str(patient_id))
            .tag("device_id", str(device_id))
            .tag("source", source)
            .time(ts)
        )
        for field_name, field_value in fields.items():
            point = point.field(field_name, field_value)

        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
        logger.debug("Vitals written to InfluxDB for patient %s: %s", patient_id, fields)
        return True

    except Exception as exc:
        logger.error("InfluxDB write failed for patient %s: %s", patient_id, exc)
        return False


# ─── Query ────────────────────────────────────────────────────────────────────

def query_latest_vitals(patient_id: str) -> dict[str, Any]:
    """
    Return the most recent value of each vital sign for a patient.
    Queries the last 24 hours and picks the latest per field.
    """
    query_api = _get_query_api()
    if query_api is None:
        logger.warning("InfluxDB unavailable — returning empty vitals for patient %s", patient_id)
        return {}

    flux = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "patient_vitals")
  |> filter(fn: (r) => r.patient_id == "{patient_id}")
  |> last()
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
'''
    try:
        tables = query_api.query(flux, org=INFLUX_ORG)
        result: dict[str, Any] = {}
        for table in tables:
            for record in table.records:
                values = record.values
                for field in VITALS_FIELD_MAP.values():
                    if field in values and values[field] is not None:
                        # Only overwrite if newer or not yet set
                        if field not in result:
                            result[field] = round(float(values[field]), 2)
                result["_timestamp"] = values.get("_time", datetime.now(timezone.utc)).isoformat()
        return result
    except Exception as exc:
        logger.error("InfluxDB query_latest failed for patient %s: %s", patient_id, exc)
        return {}


def query_vitals_history(
    patient_id: str,
    hours: int = 24,
    field: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Return a time-series list of vitals readings for a patient.

    Parameters
    ----------
    patient_id : Patient UUID
    hours      : Look-back window in hours (default 24)
    field      : Optional specific field to query (e.g. "heart_rate"); all if None

    Returns a list of point dicts: [{"time": "...", "heart_rate": 72, ...}, ...]
    """
    query_api = _get_query_api()
    if query_api is None:
        return []

    field_filter = f'|> filter(fn: (r) => r._field == "{field}")' if field else ""

    flux = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -{hours}h)
  |> filter(fn: (r) => r._measurement == "patient_vitals")
  |> filter(fn: (r) => r.patient_id == "{patient_id}")
  {field_filter}
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])
'''
    try:
        tables = query_api.query(flux, org=INFLUX_ORG)
        rows = []
        for table in tables:
            for record in table.records:
                row = {"time": record.get_time().isoformat()}
                for f in set(VITALS_FIELD_MAP.values()):
                    if record.values.get(f) is not None:
                        row[f] = round(float(record.values[f]), 2)
                rows.append(row)
        return rows
    except Exception as exc:
        logger.error("InfluxDB query_history failed for patient %s: %s", patient_id, exc)
        return []


def query_aggregate_stats(
    patient_id: str,
    field: str,
    hours: int = 24,
) -> dict[str, float]:
    """
    Returns mean, min, max, stddev for a vital field over a time window.
    Used by the monitoring agent for baseline computation.
    """
    query_api = _get_query_api()
    if query_api is None:
        return {}

    base_flux = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -{hours}h)
  |> filter(fn: (r) => r._measurement == "patient_vitals")
  |> filter(fn: (r) => r.patient_id == "{patient_id}")
  |> filter(fn: (r) => r._field == "{field}")
'''
    stats = {}
    try:
        for agg_fn in ("mean", "min", "max", "stddev"):
            flux = base_flux + f'  |> {agg_fn}()'
            tables = query_api.query(flux, org=INFLUX_ORG)
            for table in tables:
                for record in table.records:
                    v = record.get_value()
                    if v is not None:
                        stats[agg_fn] = round(float(v), 3)
        return stats
    except Exception as exc:
        logger.error("InfluxDB aggregate stats failed for patient %s / %s: %s", patient_id, field, exc)
        return {}
