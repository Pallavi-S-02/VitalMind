"""
analytics_service.py — Query methods for patient trends, doctor caseloads, system health.

All methods return plain Python dicts safe to JSON-serialise.
Heavy aggregations use SQLAlchemy core text() queries for efficiency.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text

from app.models.db import db

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Patient analytics
# ─────────────────────────────────────────────────────────────────────────────

class AnalyticsService:

    # ── Patient ──────────────────────────────────────────────────

    @staticmethod
    def get_patient_overview(patient_id: str) -> dict[str, Any]:
        """
        Returns:
          - recent vitals trend (last 7 days)
          - appointment summary (upcoming count, last visit)
          - care plan adherence
          - medication adherence
          - active alerts count
        """
        result: dict[str, Any] = {
            "patient_id": patient_id,
            "vitals_trend": [],
            "appointments": {"upcoming": 0, "last_visit": None, "total": 0},
            "care_plan": {"adherence_pct": None, "active": False, "title": None},
            "medications": {"active_count": 0},
            "alerts": {"open_count": 0},
        }

        now = datetime.now(timezone.utc)

        # Appointments
        try:
            rows = db.session.execute(
                text("""
                    SELECT
                        COUNT(*) FILTER (WHERE start_time >= :now AND status = 'scheduled') AS upcoming,
                        MAX(start_time) FILTER (WHERE start_time < :now AND status = 'completed') AS last_visit,
                        COUNT(*) AS total
                    FROM appointments
                    WHERE patient_id = :pid
                """),
                {"pid": patient_id, "now": now.isoformat()},
            ).mappings().first()
            if rows:
                result["appointments"] = {
                    "upcoming": rows["upcoming"] or 0,
                    "last_visit": rows["last_visit"].isoformat() if rows["last_visit"] else None,
                    "total": rows["total"] or 0,
                }
        except Exception as exc:
            logger.warning("AnalyticsService.get_patient_overview appointments: %s", exc)

        # Active care plan adherence
        try:
            from app.models.care_plan import CarePlan, CarePlanTask
            plan = CarePlan.query.filter_by(patient_id=patient_id, status="active").first()
            if plan:
                tasks = CarePlanTask.query.filter_by(care_plan_id=str(plan.id)).all()
                done = sum(1 for t in tasks if t.status == "completed")
                total = len(tasks)
                result["care_plan"] = {
                    "active": True,
                    "title": plan.title,
                    "adherence_pct": round((done / total) * 100) if total > 0 else 0,
                    "tasks_done": done,
                    "tasks_total": total,
                }
        except Exception as exc:
            logger.warning("AnalyticsService.get_patient_overview care_plan: %s", exc)

        # Vitals trend (last 7 days from InfluxDB if available, otherwise placeholder)
        try:
            from app.services.vitals_service import VitalsService
            vitals = VitalsService.get_latest_vitals(patient_id, hours=168)  # 7 days
            result["vitals_trend"] = vitals[:20] if vitals else []
        except Exception:
            result["vitals_trend"] = []

        return result

    @staticmethod
    def get_patient_vitals_trend(patient_id: str, days: int = 30) -> dict[str, Any]:
        """Aggregated vitals trend for charting."""
        try:
            from app.services.vitals_service import VitalsService
            vitals = VitalsService.get_latest_vitals(patient_id, hours=days * 24)
            return {"patient_id": patient_id, "days": days, "vitals": vitals or []}
        except Exception as exc:
            logger.warning("get_patient_vitals_trend: %s", exc)
            return {"patient_id": patient_id, "days": days, "vitals": []}

    @staticmethod
    def get_medication_adherence(patient_id: str) -> dict[str, Any]:
        """Medication fill & reminder adherence."""
        try:
            rows = db.session.execute(
                text("""
                    SELECT
                        COUNT(*) AS total_reminders,
                        COUNT(*) FILTER (WHERE is_sent = true) AS sent,
                        medication_name,
                        MAX(scheduled_time) AS last_scheduled
                    FROM medication_reminders
                    WHERE patient_id = :pid AND is_active = true
                    GROUP BY medication_name
                    ORDER BY last_scheduled DESC
                    LIMIT 10
                """),
                {"pid": patient_id},
            ).mappings().all()

            medications = [
                {
                    "name": r["medication_name"],
                    "reminders": r["total_reminders"],
                    "sent": r["sent"],
                    "adherence_pct": round((r["sent"] / r["total_reminders"]) * 100) if r["total_reminders"] else 0,
                    "last_scheduled": r["last_scheduled"].isoformat() if r["last_scheduled"] else None,
                }
                for r in rows
            ]
            total = sum(m["reminders"] for m in medications)
            sent = sum(m["sent"] for m in medications)
            return {
                "patient_id": patient_id,
                "overall_pct": round((sent / total) * 100) if total else 0,
                "medications": medications,
            }
        except Exception as exc:
            logger.warning("get_medication_adherence: %s", exc)
            return {"patient_id": patient_id, "overall_pct": 0, "medications": []}

    # ── Doctor ────────────────────────────────────────────────────

    @staticmethod
    def get_doctor_overview(doctor_id: str) -> dict[str, Any]:
        """
        Returns:
          - today's appointment schedule
          - active patient count / risk distribution
          - pending alerts count
          - appointment completion rate (30 days)
        """
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        # Log for debugging
        logger.info(f"AnalyticsService.get_doctor_overview: did={doctor_id} start={today_start} end={today_end}")

        result: dict[str, Any] = {
            "doctor_id": doctor_id,
            "today_appointments": [],
            "stats": {
                "active_patients": 0,
                "pending_alerts": 0,
                "completion_rate_pct": 0,
                "total_appointments_30d": 0,
            },
            "risk_distribution": {"low": 0, "medium": 0, "high": 0, "critical": 0},
        }

        try:
            from app.models.appointment import Appointment
            from app.models.patient import PatientProfile
            from app.models.user import User
            from sqlalchemy import func, distinct, and_

            # 1. Today's Appointments
            # Use noon-to-noon or just ensure naive match for timestamp without time zone
            naive_start = today_start.replace(tzinfo=None)
            naive_end = today_end.replace(tzinfo=None)
            
            appts = db.session.query(
                Appointment,
                User.first_name,
                User.last_name
            ).join(PatientProfile, PatientProfile.id == Appointment.patient_id)\
             .join(User, User.id == PatientProfile.user_id)\
             .filter(
                Appointment.doctor_id == doctor_id,
                Appointment.start_time >= naive_start,
                Appointment.start_time < naive_end
            ).order_by(Appointment.start_time.asc()).all()

            result["today_appointments"] = [
                {
                    "id": str(a.Appointment.id),
                    "start_time": a.Appointment.start_time.isoformat(),
                    "end_time": a.Appointment.end_time.isoformat(),
                    "status": a.Appointment.status,
                    "type": a.Appointment.type,
                    "reason": a.Appointment.reason,
                    "patient_name": f"{a.first_name} {a.last_name}",
                }
                for a in appts
            ]

            # 2. Statistics
            naive_month_ago = (now - timedelta(days=30)).replace(tzinfo=None)
            
            stats = db.session.query(
                func.count(distinct(Appointment.patient_id)).label("active_patients"),
                func.count(Appointment.id).filter(Appointment.start_time >= naive_month_ago).label("total_30d"),
                func.count(Appointment.id).filter(
                    and_(Appointment.status == 'completed', Appointment.start_time >= naive_month_ago)
                ).label("completed_30d")
            ).filter(
                Appointment.doctor_id == doctor_id,
                Appointment.status != 'cancelled'
            ).first()

            if stats:
                total = stats.total_30d or 0
                completed = stats.completed_30d or 0
                result["stats"] = {
                    "active_patients": stats.active_patients or 0,
                    "total_appointments_30d": total,
                    "completion_rate_pct": round((completed / total) * 100) if total else 0,
                    "pending_alerts": 0,
                }
            
            logger.info(f"AnalyticsService.get_doctor_overview: Stats for {doctor_id}: {result['stats']}")
        except Exception as exc:
            logger.exception("get_doctor_overview error: %s", exc)

        return result

    @staticmethod
    def get_doctor_appointment_history(doctor_id: str, days: int = 30) -> list[dict]:
        """Daily appointment volume for charting."""
        try:
            since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            rows = db.session.execute(
                text("""
                    SELECT
                        DATE(start_time) AS appt_date,
                        COUNT(*) AS count,
                        COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                        COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled
                    FROM appointments
                    WHERE doctor_id = :did AND start_time >= :since
                    GROUP BY appt_date
                    ORDER BY appt_date ASC
                """),
                {"did": doctor_id, "since": since},
            ).mappings().all()
            return [
                {
                    "date": str(r["appt_date"]),
                    "count": r["count"],
                    "completed": r["completed"],
                    "cancelled": r["cancelled"],
                }
                for r in rows
            ]
        except Exception as exc:
            logger.warning("get_doctor_appointment_history: %s", exc)
            return []

    # ── Admin / System ────────────────────────────────────────────

    @staticmethod
    def get_admin_overview() -> dict[str, Any]:
        """System-level metrics for admin dashboard."""
        result: dict[str, Any] = {
            "users": {"total": 0, "patients": 0, "doctors": 0},
            "appointments": {"total": 0, "today": 0, "completed_pct": 0},
            "care_plans": {"active": 0, "total": 0},
            "agents": {"conversations_7d": 0},
            "system": {"db_ok": True},
        }

        now = datetime.now(timezone.utc)

        try:
            rows = db.session.execute(
                text("""
                    SELECT role, COUNT(*) AS cnt FROM users GROUP BY role
                """)
            ).mappings().all()
            role_map = {r["role"]: r["cnt"] for r in rows}
            result["users"] = {
                "total": sum(role_map.values()),
                "patients": role_map.get("patient", 0),
                "doctors": role_map.get("doctor", 0),
                "admins": role_map.get("admin", 0),
            }
        except Exception as exc:
            logger.warning("get_admin_overview users: %s", exc)

        try:
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            stats = db.session.execute(
                text("""
                    SELECT
                        COUNT(*) AS total,
                        COUNT(*) FILTER (WHERE start_time >= :today) AS today_count,
                        COUNT(*) FILTER (WHERE status = 'completed') AS completed
                    FROM appointments
                """),
                {"today": today_start.isoformat()},
            ).mappings().first()
            if stats:
                total = stats["total"] or 0
                completed = stats["completed"] or 0
                result["appointments"] = {
                    "total": total,
                    "today": stats["today_count"] or 0,
                    "completed_pct": round((completed / total) * 100) if total else 0,
                }
        except Exception as exc:
            logger.warning("get_admin_overview appointments: %s", exc)

        try:
            cp_stats = db.session.execute(
                text("SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE status = 'active') AS active FROM care_plans")
            ).mappings().first()
            if cp_stats:
                result["care_plans"] = {
                    "total": cp_stats["total"] or 0,
                    "active": cp_stats["active"] or 0,
                }
        except Exception as exc:
            logger.warning("get_admin_overview care_plans: %s", exc)

        try:
            conv_7d = db.session.execute(
                text("SELECT COUNT(*) AS cnt FROM conversations WHERE created_at >= :since"),
                {"since": (now - timedelta(days=7)).isoformat()},
            ).scalar()
            result["agents"]["conversations_7d"] = conv_7d or 0
        except Exception:
            pass

        return result
