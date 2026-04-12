"""
patient_history.py — LangChain tool for retrieving patient clinical history.

Pulls structured patient data (medications, allergies, diagnoses, vitals)
from the PatientMemory cache (Redis → PostgreSQL) and formats it for
injection into agent reasoning chains.
"""

from __future__ import annotations

import logging
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def get_patient_history(patient_id: str) -> str:
    """
    Retrieve the complete clinical history for a patient.

    Returns allergies, current medications, chronic conditions, and
    recent diagnoses from the patient's medical record.

    Args:
        patient_id: The UUID of the patient whose history to retrieve

    Returns:
        Formatted clinical summary string ready for agent reasoning
    """
    if not patient_id:
        return "No patient ID provided — cannot retrieve history."

    try:
        from app.agents.memory.patient_memory import PatientMemory
        memory = PatientMemory(patient_id)
        ctx = memory.load()

        lines = [
            f"=== Patient Profile ===",
            f"Name: {ctx.get('name', 'Unknown')}",
            f"Date of Birth: {ctx.get('date_of_birth', 'Not on record')}",
            f"Gender: {ctx.get('gender', 'Not specified')}",
            f"Blood Type: {ctx.get('blood_type', 'Unknown')}",
            "",
            f"=== Allergies ===",
        ]

        allergies = ctx.get("allergies", [])
        lines.append(", ".join(allergies) if allergies else "No known drug allergies documented.")

        lines += ["", "=== Current Medications ==="]
        meds = ctx.get("current_medications", [])
        if meds:
            for m in meds:
                if isinstance(m, dict):
                    lines.append(f"  • {m.get('name', 'Unknown')} — {m.get('dose', '')} {m.get('frequency', '')}")
                else:
                    lines.append(f"  • {m}")
        else:
            lines.append("No active medications on record.")

        lines += ["", "=== Chronic Conditions ==="]
        conditions = ctx.get("chronic_conditions", [])
        lines.append(", ".join(conditions) if conditions else "None documented.")

        lines += ["", "=== Recent Diagnoses ==="]
        diagnoses = ctx.get("recent_diagnoses", [])
        lines.append(", ".join(diagnoses) if diagnoses else "None on record.")

        return "\n".join(lines)

    except Exception as exc:
        logger.error("get_patient_history failed for %s: %s", patient_id, exc)
        return f"Unable to retrieve patient history at this time. Error: {exc}"


@tool
def get_patient_medications(patient_id: str) -> str:
    """
    Retrieve just the current medication list for a patient.
    Use this when you only need medications, not the full history.

    Args:
        patient_id: The UUID of the patient

    Returns:
        Comma-separated list of current medication names
    """
    try:
        from app.agents.memory.patient_memory import PatientMemory
        memory = PatientMemory(patient_id)
        meds = memory.get_medication_names()
        if not meds:
            return "No active medications on record."
        return "Current medications: " + ", ".join(meds)
    except Exception as exc:
        logger.error("get_patient_medications failed: %s", exc)
        return f"Unable to retrieve medications. Error: {exc}"


@tool
def get_patient_allergies(patient_id: str) -> str:
    """
    Retrieve the known allergy list for a patient.

    Args:
        patient_id: The UUID of the patient

    Returns:
        Comma-separated list of known allergies
    """
    try:
        from app.agents.memory.patient_memory import PatientMemory
        memory = PatientMemory(patient_id)
        allergies = memory.get_allergy_list()
        if not allergies:
            return "No known drug allergies documented."
        return "Known allergies: " + ", ".join(allergies)
    except Exception as exc:
        logger.error("get_patient_allergies failed: %s", exc)
        return f"Unable to retrieve allergies. Error: {exc}"
