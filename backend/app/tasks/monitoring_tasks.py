"""
monitoring_tasks.py — Celery beat periodic task for continuous patient monitoring.

Invokes the MonitoringAgent every 30 seconds for all active monitored patients.
Integrates with the Redis pub/sub vitals pipeline from IoT Gateway.

Architecture:
  Celery Beat (every 30s)
    → run_monitoring_sweep()
      → for each active patient:
          MonitoringAgent.run_monitoring_cycle(patient_id)
            → LangGraph graph: ingest → baseline → detect → NEWS2 → alert

Also provides:
  - run_single_patient_monitoring(): on-demand check for a specific patient
  - process_vitals_alert_event():   triggered by Redis pub/sub new-vitals events
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def _get_monitored_patient_ids() -> list[str]:
    """
    Retrieve all patient IDs that are currently active in the monitoring system.
    Looks for recent vitals in Redis (active IoT devices) and optionally PostgreSQL.
    """
    patient_ids = []

    # 1. Query Redis for patients with recent vitals events (from IoT gateway)
    try:
        import redis as redis_lib
        r = redis_lib.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True,
        )
        # Keys are set by vitals_service: "vitals:current:<patient_id>"
        keys = r.keys("vitals:current:*")
        redis_patient_ids = [k.replace("vitals:current:", "") for k in keys]
        patient_ids.extend(redis_patient_ids)
        logger.debug("MonitoringTask: found %d patients in Redis vitals cache", len(redis_patient_ids))
    except Exception as exc:
        logger.warning("MonitoringTask: Redis query for monitored patients failed: %s", exc)

    # 2. Fallback: Query PostgreSQL for patients with active devices
    if not patient_ids:
        try:
            from app.models.device import IoTDevice
            from app.models.db import db
            active_devices = IoTDevice.query.filter_by(status="active").distinct(IoTDevice.patient_id).all()
            db_patient_ids = [str(d.patient_id) for d in active_devices]
            patient_ids.extend(db_patient_ids)
            logger.debug("MonitoringTask: found %d patients via active device DB query", len(db_patient_ids))
        except Exception as exc:
            logger.warning("MonitoringTask: PostgreSQL device query failed: %s", exc)

    # Deduplicate
    return list(set(patient_ids))


def run_monitoring_sweep() -> dict:
    """
    Main Celery beat task function — runs a monitoring cycle for every active patient.
    Called every 30 seconds by the Celery beat schedule.

    Returns a summary dict with sweep results (successes, failures, alerts triggered).
    """
    sweep_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    logger.info("MonitoringTask: starting sweep %s", sweep_id)

    try:
        from app.agents.monitoring_agent import MonitoringAgent
    except Exception as exc:
        logger.error("MonitoringTask: failed to import MonitoringAgent: %s", exc)
        return {"sweep_id": sweep_id, "status": "import_error", "error": str(exc)}

    patient_ids = _get_monitored_patient_ids()
    if not patient_ids:
        logger.info("MonitoringTask: no active patients found for sweep %s", sweep_id)
        return {"sweep_id": sweep_id, "patient_count": 0, "status": "no_patients"}

    results = {
        "sweep_id": sweep_id,
        "patient_count": len(patient_ids),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "successes": 0,
        "failures": 0,
        "alerts_triggered": 0,
        "patients_escalated": [],
    }

    for patient_id in patient_ids:
        try:
            result = MonitoringAgent.run_monitoring_cycle(patient_id=patient_id)
            final_response = result.get("final_response") or {}
            error = result.get("error")

            if error:
                logger.warning("MonitoringTask: cycle error for patient %s: %s", patient_id, error)
                results["failures"] += 1
                continue

            escalation_level = final_response.get("escalation_level", 0)
            alert_dispatched = final_response.get("alert_dispatched", False)

            if alert_dispatched:
                results["alerts_triggered"] += 1
                results["patients_escalated"].append({
                    "patient_id": patient_id,
                    "escalation_level": escalation_level,
                    "news2_score": final_response.get("news2_score", 0),
                    "severity": final_response.get("overall_severity", "UNKNOWN"),
                })
                logger.warning(
                    "MonitoringTask: ALERT dispatched for patient %s — level=%d news2=%d",
                    patient_id, escalation_level, final_response.get("news2_score", 0),
                )

            results["successes"] += 1

        except Exception as exc:
            logger.error("MonitoringTask: unhandled error for patient %s: %s", patient_id, exc)
            results["failures"] += 1

    results["completed_at"] = datetime.now(timezone.utc).isoformat()
    results["status"] = "complete"

    logger.info(
        "MonitoringTask: sweep %s complete — %d patients, %d alerts, %d failures",
        sweep_id,
        results["patient_count"],
        results["alerts_triggered"],
        results["failures"],
    )

    return results


def run_single_patient_monitoring(
    patient_id: str,
    vitals_snapshot: Optional[dict] = None,
    physician_phone: Optional[str] = None,
    specialist_phone: Optional[str] = None,
) -> dict:
    """
    On-demand monitoring cycle for a single patient.
    Can be triggered by:
      - Direct API call (doctor requests immediate vitals assessment)
      - Redis pub/sub new-vitals event handler
      - Test/debug invocation

    Args:
        patient_id: UUID of the patient to check
        vitals_snapshot: Optional pre-fetched vitals dict
        physician_phone: Attending physician phone for SMS (if None, uses DB lookup)
        specialist_phone: On-call specialist phone (if None, uses DB lookup)

    Returns:
        MonitoringAgent final state dict
    """
    logger.info("MonitoringTask: on-demand monitoring for patient %s", patient_id)

    try:
        # Try to look up physician phone from DB if not provided
        if not physician_phone:
            try:
                from app.models.patient import PatientProfile
                from app.models.db import db
                profile = PatientProfile.query.filter_by(user_id=patient_id).first()
                if profile and profile.primary_doctor_id:
                    from app.models.doctor import DoctorProfile
                    doctor = DoctorProfile.query.filter_by(user_id=profile.primary_doctor_id).first()
                    if doctor:
                        physician_phone = getattr(doctor, "phone_number", None)
            except Exception:
                pass  # Gracefully proceed without phone

        from app.agents.monitoring_agent import MonitoringAgent
        return MonitoringAgent.run_monitoring_cycle(
            patient_id=patient_id,
            vitals_snapshot=vitals_snapshot,
            physician_phone=physician_phone,
            specialist_phone=specialist_phone,
        )

    except Exception as exc:
        logger.error(
            "MonitoringTask: on-demand monitoring failed for patient %s: %s",
            patient_id, exc,
        )
        return {
            "patient_id": patient_id,
            "error": str(exc),
            "final_response": None,
        }


def process_vitals_alert_event(event_payload: dict) -> None:
    """
    Handle a new-vitals event published to Redis pub/sub channel
    'vitalmind:vitals_events' by the IoT Gateway.

    This is called by a Redis pub/sub subscriber (separate process/thread).
    Triggers an immediate on-demand monitoring cycle for the affected patient.

    Args:
        event_payload: Dict with at least {"patient_id": "...", "vitals": {...}}
    """
    patient_id = event_payload.get("patient_id")
    vitals = event_payload.get("vitals") or event_payload.get("data", {})

    if not patient_id:
        logger.warning("MonitoringTask: vitals event missing patient_id — skipping")
        return

    logger.info("MonitoringTask: processing real-time vitals event for patient %s", patient_id)
    run_single_patient_monitoring(patient_id=patient_id, vitals_snapshot=vitals)


# ─────────────────────────────────────────────────────────────────────────────
# Celery app configuration
# ─────────────────────────────────────────────────────────────────────────────

def make_celery(app=None):
    """
    Create and configure a Celery application instance.
    Call this from your Flask app factory after configuring the app.

    Usage in app factory:
        celery = make_celery(app)

    Then register the beat schedule as shown below.
    """
    try:
        from celery import Celery

        broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
        result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

        celery_app = Celery(
            "vitalmind",
            broker=broker_url,
            backend=result_backend,
        )

        # Configure Celery beat periodic schedule
        celery_app.conf.beat_schedule = {
            "patient-monitoring-sweep": {
                "task": "app.tasks.monitoring_tasks.celery_monitoring_sweep",
                "schedule": 30.0,  # Every 30 seconds
                "options": {
                    "expires": 25,  # Drop if not picked up within 25s (avoid pile-up)
                    "queue": "monitoring",
                },
            },
        }

        celery_app.conf.task_routes = {
            "app.tasks.monitoring_tasks.*": {"queue": "monitoring"},
        }
        celery_app.conf.task_serializer = "json"
        celery_app.conf.result_serializer = "json"
        celery_app.conf.accept_content = ["json"]
        celery_app.conf.timezone = "UTC"
        celery_app.conf.enable_utc = True

        if app is not None:
            # Push Flask application context into Celery tasks
            class ContextTask(celery_app.Task):
                def __call__(self, *args, **kwargs):
                    with app.app_context():
                        return self.run(*args, **kwargs)

            celery_app.Task = ContextTask

        return celery_app

    except ImportError:
        logger.warning(
            "MonitoringTask: Celery not installed — monitoring tasks unavailable. "
            "Install with: pip install celery[redis]"
        )
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Celery task wrappers (registered if make_celery() is called from app factory)
# ─────────────────────────────────────────────────────────────────────────────

# These are thin wrappers; the actual logic lives in the functions above
# so they can be unit-tested without Celery infrastructure.

def register_monitoring_tasks(celery_app) -> None:
    """
    Register Celery tasks on the provided celery_app.
    Call this after make_celery() in your app factory.
    """
    if celery_app is None:
        return

    @celery_app.task(
        name="app.tasks.monitoring_tasks.celery_monitoring_sweep",
        bind=True,
        max_retries=1,
        soft_time_limit=25,  # Kill after 25s to prevent overlap with next beat tick
    )
    def celery_monitoring_sweep(self):
        """Celery beat task: run monitoring sweep for all active patients."""
        try:
            return run_monitoring_sweep()
        except Exception as exc:
            logger.error("MonitoringTask Celery worker error: %s", exc)
            raise

    @celery_app.task(
        name="app.tasks.monitoring_tasks.celery_single_patient_monitoring",
        bind=True,
        max_retries=2,
    )
    def celery_single_patient_monitoring(self, patient_id: str, vitals_snapshot: Optional[dict] = None):
        """Celery task: on-demand monitoring cycle for a single patient."""
        try:
            return run_single_patient_monitoring(patient_id, vitals_snapshot=vitals_snapshot)
        except Exception as exc:
            logger.error("MonitoringTask single-patient Celery worker error for %s: %s", patient_id, exc)
            self.retry(exc=exc, countdown=5)

    logger.info("MonitoringTask: Celery tasks registered (sweep + single-patient)")
