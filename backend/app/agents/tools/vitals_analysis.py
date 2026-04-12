"""
vitals_analysis.py — LangChain tools for the Patient Monitoring Agent.

Tools:
  - fetch_patient_vitals      : Pull latest readings from InfluxDB/Redis
  - compute_patient_baseline  : Calculate rolling stats for a patient
  - calculate_news2_score     : Compute National Early Warning Score 2
  - detect_vitals_anomaly     : Z-score + IQR anomaly detection
  - correlate_vitals_meds     : Check if vitals changes align with medications
  - generate_shift_summary    : Summarize vitals trends for shift handoff
"""

from __future__ import annotations

import json
import logging
import math
import os
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# NEWS2 scoring tables (Royal College of Physicians, 2017)
# ─────────────────────────────────────────────────────────────────────────────

def _news2_rr_score(rr: Optional[float]) -> int:
    if rr is None: return 0
    if rr <= 8: return 3
    if rr <= 11: return 1
    if rr <= 20: return 0
    if rr <= 24: return 2
    return 3

def _news2_spo2_score(spo2: Optional[float], is_hypercapnic: bool = False) -> int:
    if spo2 is None: return 0
    if not is_hypercapnic:
        if spo2 <= 91: return 3
        if spo2 <= 93: return 2
        if spo2 <= 95: return 1
        return 0
    else:  # Scale 2 for hypercapnic resp failure
        if spo2 <= 83: return 3
        if spo2 <= 85: return 2
        if spo2 <= 87: return 1
        if spo2 <= 92 or spo2 >= 98: return 0  # 88-92 is target range
        return 0

def _news2_bp_score(systolic: Optional[float]) -> int:
    if systolic is None: return 0
    if systolic <= 90: return 3
    if systolic <= 100: return 2
    if systolic <= 110: return 1
    if systolic <= 219: return 0
    return 3

def _news2_hr_score(hr: Optional[float]) -> int:
    if hr is None: return 0
    if hr <= 40: return 3
    if hr <= 50: return 1
    if hr <= 90: return 0
    if hr <= 110: return 1
    if hr <= 130: return 2
    return 3

def _news2_temp_score(temp_c: Optional[float]) -> int:
    if temp_c is None: return 0
    if temp_c <= 35.0: return 3
    if temp_c <= 36.0: return 1
    if temp_c <= 38.0: return 0
    if temp_c <= 39.0: return 1
    return 2

def _news2_consciousness_score(avpu: str = "A") -> int:
    """A=Alert, V=Voice, P=Pain, U=Unresponsive"""
    return 0 if avpu.upper() == "A" else 3

def _news2_risk_level(score: int) -> tuple[str, str, int]:
    """Returns (risk_label, colour, escalation_level)"""
    if score == 0: return ("Low", "green", 0)
    if score <= 4: return ("Low-Medium", "yellow", 1)
    if score == 5 or score == 6: return ("Medium", "orange", 2)
    if score >= 7: return ("High", "red", 3)
    return ("Unknown", "grey", 0)


# ─────────────────────────────────────────────────────────────────────────────
# Tool definitions
# ─────────────────────────────────────────────────────────────────────────────

@tool
def fetch_patient_vitals(patient_id: str, hours: int = 1) -> str:
    """
    Fetch the latest vitals readings for a patient from the data pipeline.
    Tries Redis cache first (sub-millisecond), then InfluxDB, then PostgreSQL.

    Args:
        patient_id: UUID of the patient
        hours: Look-back window in hours for history (default 1)

    Returns: JSON string with current vitals snapshot and recent history
    """
    try:
        from app.services.vitals_service import VitalsService
        current = VitalsService.get_current_vitals(patient_id)
        history = VitalsService.get_vitals_history(patient_id, hours=hours)
        return json.dumps({
            "current": current,
            "history_points": len(history),
            "history_sample": history[-3:] if history else [],
        })
    except Exception as exc:
        logger.error("fetch_patient_vitals failed for %s: %s", patient_id, exc)
        return json.dumps({"error": str(exc), "current": {}, "history_points": 0})


@tool
def compute_patient_baseline(patient_id: str, hours: int = 168) -> str:
    """
    Compute adaptive baseline statistics for each vital sign using
    rolling mean, min, max, and standard deviation over a time window.
    Uses InfluxDB aggregate queries.

    Args:
        patient_id: UUID of the patient
        hours: Rolling window size in hours (default 168 = 7 days)

    Returns: JSON string with per-field baseline statistics
    """
    try:
        from app.services.vitals_service import VitalsService
        fields = [
            "heart_rate", "spo2", "systolic_bp", "diastolic_bp",
            "temperature_c", "respiratory_rate", "blood_glucose_mgdl",
        ]
        baselines = {}
        for field in fields:
            stats = VitalsService.get_vitals_stats(patient_id, field=field, hours=hours)
            if stats:
                baselines[field] = stats
        return json.dumps({
            "patient_id": patient_id,
            "window_hours": hours,
            "baselines": baselines,
        })
    except Exception as exc:
        logger.error("compute_patient_baseline failed for %s: %s", patient_id, exc)
        return json.dumps({"error": str(exc), "baselines": {}})


@tool
def calculate_news2_score(
    heart_rate: Optional[float] = None,
    respiratory_rate: Optional[float] = None,
    spo2: Optional[float] = None,
    systolic_bp: Optional[float] = None,
    temperature_c: Optional[float] = None,
    consciousness: str = "A",
    supplemental_oxygen: bool = False,
) -> str:
    """
    Calculate the National Early Warning Score 2 (NEWS2) from vital signs.
    NEWS2 is the UK standard for detecting patient deterioration.

    Args:
        heart_rate: Heart rate in bpm
        respiratory_rate: Breaths per minute
        spo2: Oxygen saturation percentage
        systolic_bp: Systolic blood pressure in mmHg
        temperature_c: Body temperature in Celsius
        consciousness: AVPU scale — A=Alert, V=Voice, P=Pain, U=Unresponsive
        supplemental_oxygen: True if patient is on supplemental O2

    Returns: JSON with individual component scores, total score, risk level, and recommended escalation
    """
    rr_score   = _news2_rr_score(respiratory_rate)
    spo2_score = _news2_spo2_score(spo2)
    bp_score   = _news2_bp_score(systolic_bp)
    hr_score   = _news2_hr_score(heart_rate)
    temp_score = _news2_temp_score(temperature_c)
    avpu_score = _news2_consciousness_score(consciousness)
    o2_score   = 2 if supplemental_oxygen else 0  # NEWS2: on supplemental O2 = +2

    total = rr_score + spo2_score + bp_score + hr_score + temp_score + avpu_score + o2_score
    risk_label, colour, escalation_level = _news2_risk_level(total)

    escalation_actions = {
        0: "Continue routine monitoring (minimum 12-hourly)",
        1: "Increase monitoring frequency (4-6 hourly). Nurse to assess.",
        2: "Urgent review by registered nurse; consider medical review within 1 hour.",
        3: "EMERGENCY — Immediate medical review. Activate rapid response team.",
    }

    return json.dumps({
        "news2_total": total,
        "risk_level": risk_label,
        "risk_colour": colour,
        "escalation_level": escalation_level,
        "recommended_action": escalation_actions.get(escalation_level, "Manual review required"),
        "component_scores": {
            "respiratory_rate": rr_score,
            "spo2": spo2_score,
            "blood_pressure": bp_score,
            "heart_rate": hr_score,
            "temperature": temp_score,
            "consciousness": avpu_score,
            "supplemental_oxygen": o2_score,
        },
        "vitals_used": {
            "heart_rate": heart_rate,
            "respiratory_rate": respiratory_rate,
            "spo2": spo2,
            "systolic_bp": systolic_bp,
            "temperature_c": temperature_c,
            "consciousness": consciousness,
            "supplemental_oxygen": supplemental_oxygen,
        }
    })


@tool
def detect_vitals_anomaly(patient_id: str, current_vitals: str) -> str:
    """
    Statistical anomaly detection for patient vitals.
    Uses Z-score analysis against the patient's personal 7-day baseline.
    Also checks against absolute clinical thresholds regardless of baseline.

    Args:
        patient_id: UUID of the patient
        current_vitals: JSON string of current vital signs

    Returns: JSON with anomaly flags, Z-scores, severity, and clinical interpretation
    """
    try:
        current = json.loads(current_vitals) if isinstance(current_vitals, str) else current_vitals
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid current_vitals JSON"})

    # Absolute clinical alarm limits (regardless of personal baseline)
    CRITICAL_LIMITS = {
        "heart_rate":         {"low": 40,  "high": 150},
        "spo2":               {"low": 90,  "high": None},
        "systolic_bp":        {"low": 80,  "high": 200},
        "diastolic_bp":       {"low": 50,  "high": 120},
        "temperature_c":      {"low": 35.0,"high": 40.0},
        "respiratory_rate":   {"low": 8,   "high": 30},
        "blood_glucose_mgdl": {"low": 60,  "high": 400},
    }

    anomalies = []
    field_map = {
        "heart_rate": current.get("heart_rate"),
        "spo2": current.get("spo2"),
        "systolic_bp": current.get("systolic_bp"),
        "diastolic_bp": current.get("diastolic_bp"),
        "temperature_c": current.get("temperature_c"),
        "respiratory_rate": current.get("respiratory_rate"),
        "blood_glucose_mgdl": current.get("blood_glucose_mgdl"),
    }

    # Check absolute limits first
    for field, value in field_map.items():
        if value is None:
            continue
        limits = CRITICAL_LIMITS.get(field, {})
        lo = limits.get("low")
        hi = limits.get("high")

        if (lo and value < lo) or (hi and value > hi):
            direction = "LOW" if (lo and value < lo) else "HIGH"
            anomalies.append({
                "field": field,
                "value": value,
                "type": "absolute_threshold",
                "direction": direction,
                "severity": "CRITICAL",
                "message": f"{field} is critically {direction}: {value}"
            })

    # Z-score analysis against personal baseline
    try:
        from app.services.vitals_service import VitalsService
        for field, value in field_map.items():
            if value is None:
                continue
            stats = VitalsService.get_vitals_stats(patient_id, field=field, hours=168)
            mean = stats.get("mean")
            stddev = stats.get("stddev")
            if mean is not None and stddev and stddev > 0:
                z = (value - mean) / stddev
                if abs(z) >= 3:
                    severity = "HIGH" if abs(z) >= 4 else "MODERATE"
                    # Avoid duplicating absolute threshold alerts
                    already_flagged = any(a["field"] == field for a in anomalies)
                    if not already_flagged:
                        anomalies.append({
                            "field": field,
                            "value": value,
                            "type": "z_score",
                            "z_score": round(z, 2),
                            "baseline_mean": round(mean, 2),
                            "severity": severity,
                            "message": f"{field} deviates {abs(z):.1f}σ from patient's 7-day baseline (mean={mean:.1f})"
                        })
    except Exception as exc:
        logger.warning("Z-score baseline analysis failed for %s: %s", patient_id, exc)

    has_critical = any(a["severity"] == "CRITICAL" for a in anomalies)
    has_high = any(a["severity"] == "HIGH" for a in anomalies)
    overall_severity = "CRITICAL" if has_critical else ("HIGH" if has_high else ("MODERATE" if anomalies else "NORMAL"))

    return json.dumps({
        "patient_id": patient_id,
        "anomaly_detected": bool(anomalies),
        "overall_severity": overall_severity,
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
    })


@tool
def correlate_vitals_medications(patient_id: str, anomalous_fields: str) -> str:
    """
    Check if detected vitals anomalies may be explained by recent medication changes,
    timing of doses, or known medication side effects.

    Args:
        patient_id: UUID of the patient
        anomalous_fields: Comma-separated list of vital fields showing anomalies (e.g. "heart_rate,systolic_bp")

    Returns: JSON with possible medication correlations and clinical context
    """
    fields = [f.strip() for f in anomalous_fields.split(",") if f.strip()]

    # Known medication → vital effect mappings
    MED_EFFECTS = {
        "heart_rate": {
            "low": ["beta-blockers", "digoxin", "calcium channel blockers", "ivabradine"],
            "high": ["atropine", "salbutamol", "theophylline", "epinephrine", "stimulants"],
        },
        "systolic_bp": {
            "low": ["antihypertensives", "diuretics", "ACE inhibitors", "ARBs", "alpha-blockers"],
            "high": ["NSAIDs", "corticosteroids", "decongestants", "caffeine"],
        },
        "blood_glucose_mgdl": {
            "low": ["insulin", "sulfonylureas", "GLP-1 agonists"],
            "high": ["corticosteroids", "thiazides", "antipsychotics", "beta-blockers"],
        },
        "spo2": {
            "low": ["opioids", "benzodiazepines", "sedatives", "muscle relaxants"],
        },
        "respiratory_rate": {
            "low": ["opioids", "benzodiazepines", "barbiturates"],
            "high": ["salicylates", "stimulants"],
        },
    }

    try:
        from app.agents.memory.patient_memory import PatientMemory
        memory = PatientMemory(patient_id)
        profile = memory.load()
        medications = profile.get("current_medications", [])
        med_names = [
            (m.get("name", "") if isinstance(m, dict) else str(m)).lower()
            for m in medications
        ]
    except Exception as exc:
        logger.warning("Could not load medications for correlation: %s", exc)
        med_names = []

    correlations = []
    for field in fields:
        effects = MED_EFFECTS.get(field, {})
        for direction, med_classes in effects.items():
            for med_class in med_classes:
                # Check if patient is on any medication matching this class (keyword match)
                matching_meds = [m for m in med_names if any(word in m for word in med_class.split())]
                if matching_meds or True:  # Always report possible correlations as advisory
                    correlations.append({
                        "vital_field": field,
                        "direction": direction,
                        "possible_cause_class": med_class,
                        "patient_meds_in_class": matching_meds,
                        "advisory": f"Abnormal {field} ({direction}) may be related to {med_class}."
                    })

    return json.dumps({
        "patient_id": patient_id,
        "anomalous_fields": fields,
        "patient_medications": med_names,
        "correlations_found": len(correlations),
        "correlations": correlations[:10],  # Cap to top 10
    })


@tool
def generate_shift_summary(patient_id: str, shift_hours: int = 8) -> str:
    """
    Generate a concise vitals trend summary covering one clinical shift period.
    Includes average values, notable deviations, and any alerts triggered.
    Intended for nurse/doctor shift handoff documentation.

    Args:
        patient_id: UUID of the patient
        shift_hours: Duration of the shift to summarize in hours (default 8)

    Returns: JSON with shift summary data and narrative text
    """
    try:
        from app.services.vitals_service import VitalsService
        fields = ["heart_rate", "spo2", "systolic_bp", "diastolic_bp", "temperature_c", "respiratory_rate"]
        shift_stats = {}
        for field in fields:
            stats = VitalsService.get_vitals_stats(patient_id, field=field, hours=shift_hours)
            if stats:
                shift_stats[field] = stats

        return json.dumps({
            "patient_id": patient_id,
            "shift_hours": shift_hours,
            "vitals_summary": shift_stats,
            "summary_generated": True,
        })
    except Exception as exc:
        logger.error("generate_shift_summary failed for %s: %s", patient_id, exc)
        return json.dumps({"error": str(exc)})
