"""
care_plan_tasks.py — Celery tasks for care plan adherence monitoring.

Beat task: Run adherence tracking for all active care plans daily.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def run_daily_adherence_sweep() -> dict:
    """
    Daily beat task: iterate all active care plans and run adherence tracking.
    Identifies deviations, sends reminders, generates progress reports.
    """
    logger.info("CarePlanTask: starting daily adherence sweep")
    processed = 0
    errors = 0

    try:
        from app.models.care_plan import CarePlan
        from app.agents.followup_agent import run_track_adherence

        active_plans = CarePlan.query.filter_by(status="active").all()
        logger.info("CarePlanTask: %d active plans found", len(active_plans))

        for plan in active_plans:
            try:
                result = run_track_adherence(
                    patient_id=str(plan.patient_id),
                    plan_id=str(plan.id),
                )
                if result.get("success"):
                    processed += 1
                    logger.debug(
                        "CarePlanTask: plan %s — adherence=%s%% notifications=%s",
                        plan.id,
                        result.get("adherence_analysis", {}).get("overall_adherence_pct", "N/A"),
                        result.get("notifications_sent", []),
                    )
                else:
                    errors += 1
            except Exception as exc:
                logger.error("CarePlanTask: plan %s failed: %s", plan.id, exc)
                errors += 1

    except Exception as exc:
        logger.error("CarePlanTask: sweep failed: %s", exc)
        return {"status": "error", "error": str(exc)}

    logger.info("CarePlanTask: sweep done — processed=%d errors=%d", processed, errors)
    return {"status": "complete", "processed": processed, "errors": errors}


def make_care_plan_celery(app=None):
    """Create Celery app for care plan tasks."""
    try:
        from celery import Celery

        celery_app = Celery(
            "vitalmind_care_plans",
            broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1"),
            backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2"),
        )

        celery_app.conf.beat_schedule = {
            "daily-adherence-sweep": {
                "task": "app.tasks.care_plan_tasks.celery_daily_adherence_sweep",
                "schedule": 86400.0,   # every 24 hours
                "options": {"queue": "care_plans", "expires": 85000},
            },
        }
        celery_app.conf.task_routes = {
            "app.tasks.care_plan_tasks.*": {"queue": "care_plans"},
        }
        celery_app.conf.task_serializer = "json"
        celery_app.conf.result_serializer = "json"
        celery_app.conf.accept_content = ["json"]
        celery_app.conf.timezone = "UTC"
        celery_app.conf.enable_utc = True

        if app is not None:
            class ContextTask(celery_app.Task):
                def __call__(self, *args, **kwargs):
                    with app.app_context():
                        return self.run(*args, **kwargs)
            celery_app.Task = ContextTask

        return celery_app

    except ImportError:
        logger.warning("CarePlanTask: Celery not installed")
        return None


def register_care_plan_tasks(celery_app) -> None:
    if celery_app is None:
        return

    @celery_app.task(
        name="app.tasks.care_plan_tasks.celery_daily_adherence_sweep",
        bind=True,
        max_retries=1,
        soft_time_limit=82000,
    )
    def celery_daily_adherence_sweep(self) -> dict:
        """Daily sweep of all active care plans for adherence tracking."""
        try:
            return run_daily_adherence_sweep()
        except Exception as exc:
            logger.error("CarePlanTask: daily sweep beat task failed: %s", exc)
            raise

    logger.info("CarePlanTask: Celery task registered")
