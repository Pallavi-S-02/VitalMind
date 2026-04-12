"""
scheduling.py — LangChain tools for the Follow-Up / Care-Plan Agent to
programmatically book, cancel, and reschedule appointments.

All tools are implemented as @tool decorated functions that delegate to
AppointmentService, keeping the agent layer thin and the business logic testable.
"""

from __future__ import annotations

import logging
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def book_appointment(
    patient_id: str,
    doctor_id: str,
    start_time: str,
    type: str = "in-person",
    reason: str = "",
    duration_minutes: int = 30,
) -> dict:
    """
    Book an appointment for a patient with a specific doctor.

    Args:
        patient_id: UUID of the patient.
        doctor_id: UUID of the doctor.
        start_time: ISO 8601 datetime string (e.g. '2024-11-20T14:00:00Z').
        type: 'in-person', 'video', or 'voice'. Defaults to 'in-person'.
        reason: Patient's stated reason for the appointment.
        duration_minutes: Appointment duration (default 30 minutes).

    Returns:
        dict with appointment details or error message.
    """
    try:
        from app.services.appointment_service import AppointmentService
        appt = AppointmentService.create_appointment({
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "start_time": start_time,
            "type": type,
            "reason": reason,
            "duration_minutes": duration_minutes,
        })
        return {
            "success": True,
            "appointment_id": str(appt.id),
            "start_time": appt.start_time.isoformat(),
            "end_time": appt.end_time.isoformat(),
            "status": appt.status,
            "type": appt.type,
        }
    except ValueError as exc:
        return {"success": False, "error": str(exc)}
    except Exception as exc:
        logger.error("scheduling.book_appointment failed: %s", exc)
        return {"success": False, "error": "Internal error booking appointment"}


@tool
def cancel_appointment(
    appointment_id: str,
    reason: str = "",
) -> dict:
    """
    Cancel an existing appointment.

    Args:
        appointment_id: UUID of the appointment to cancel.
        reason: Optional reason for cancellation.

    Returns:
        dict with success status and updated appointment info.
    """
    try:
        from app.services.appointment_service import AppointmentService
        appt = AppointmentService.cancel_appointment(
            appointment_id=appointment_id,
            reason=reason,
        )
        if not appt:
            return {"success": False, "error": "Appointment not found"}
        return {
            "success": True,
            "appointment_id": str(appt.id),
            "status": appt.status,
        }
    except ValueError as exc:
        return {"success": False, "error": str(exc)}
    except Exception as exc:
        logger.error("scheduling.cancel_appointment failed: %s", exc)
        return {"success": False, "error": "Internal error cancelling appointment"}


@tool
def reschedule_appointment(
    appointment_id: str,
    new_start_time: str,
    reason: str = "",
) -> dict:
    """
    Reschedule an existing appointment to a new time.

    Args:
        appointment_id: UUID of the appointment to reschedule.
        new_start_time: ISO 8601 datetime string for the new slot.
        reason: Optional reason for rescheduling.

    Returns:
        dict with updated appointment details or error.
    """
    try:
        from datetime import datetime
        from app.services.appointment_service import AppointmentService
        new_dt = datetime.fromisoformat(new_start_time.replace("Z", "+00:00"))
        appt = AppointmentService.reschedule_appointment(
            appointment_id=appointment_id,
            new_start_time=new_dt,
            reason=reason,
        )
        if not appt:
            return {"success": False, "error": "Appointment not found"}
        return {
            "success": True,
            "appointment_id": str(appt.id),
            "new_start_time": appt.start_time.isoformat(),
            "new_end_time": appt.end_time.isoformat(),
            "status": appt.status,
        }
    except ValueError as exc:
        return {"success": False, "error": str(exc)}
    except Exception as exc:
        logger.error("scheduling.reschedule_appointment failed: %s", exc)
        return {"success": False, "error": "Internal error rescheduling appointment"}


@tool
def get_doctor_availability(
    doctor_id: str,
    date: str,
    slot_minutes: int = 30,
) -> dict:
    """
    Return available appointment slots for a doctor on a specific date.

    Args:
        doctor_id: UUID of the doctor.
        date: Date string in YYYY-MM-DD format.
        slot_minutes: Duration of each slot in minutes (default 30).

    Returns:
        dict with list of available slots: [{"start": ..., "end": ..., "available": bool}]
    """
    try:
        from datetime import datetime
        from app.services.appointment_service import AppointmentService
        date_dt = datetime.strptime(date, "%Y-%m-%d")
        slots = AppointmentService.get_doctor_availability(
            doctor_id=doctor_id,
            date=date_dt,
            slot_minutes=slot_minutes,
        )
        available = [s for s in slots if s["available"]]
        return {
            "doctor_id": doctor_id,
            "date": date,
            "total_slots": len(slots),
            "available_count": len(available),
            "slots": slots,
        }
    except Exception as exc:
        logger.error("scheduling.get_doctor_availability failed: %s", exc)
        return {"error": str(exc), "slots": []}


@tool
def get_patient_appointments(
    patient_id: str,
    limit: int = 10,
) -> dict:
    """
    Retrieve the appointment history for a patient.

    Args:
        patient_id: UUID of the patient.
        limit: Maximum number of appointments to return (default 10).

    Returns:
        dict with list of appointment dicts.
    """
    try:
        from app.services.appointment_service import AppointmentService
        appointments = AppointmentService.get_patient_appointments(
            patient_id=patient_id,
            limit=limit,
        )
        return {
            "patient_id": patient_id,
            "count": len(appointments),
            "appointments": [AppointmentService.to_dict(a) for a in appointments],
        }
    except Exception as exc:
        logger.error("scheduling.get_patient_appointments failed: %s", exc)
        return {"error": str(exc), "appointments": []}


# Convenience list for agent tool registration
SCHEDULING_TOOLS = [
    book_appointment,
    cancel_appointment,
    reschedule_appointment,
    get_doctor_availability,
    get_patient_appointments,
]
