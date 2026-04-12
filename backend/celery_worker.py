"""
celery_worker.py — Celery worker application entry point.

Run with: celery -A celery_worker.celery worker --loglevel=info
Run beat: celery -A celery_worker.celery beat --loglevel=info
"""

import os
from celery import Celery
from celery.schedules import crontab
from app import create_app

app = create_app()

def make_celery(app):
    broker_url = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/1')
    result_backend = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')

    celery_app = Celery(
        app.import_name,
        broker=broker_url,
        backend=result_backend,
    )
    celery_app.conf.update(app.config)
    
    # Common settings
    celery_app.conf.task_serializer = "json"
    celery_app.conf.result_serializer = "json"
    celery_app.conf.accept_content = ["json"]
    celery_app.conf.timezone = "UTC"
    celery_app.conf.enable_utc = True

    # Setup Beat Schedule
    celery_app.conf.beat_schedule = {
        "daily-adherence-sweep": {
            "task": "app.tasks.care_plan_tasks.celery_daily_adherence_sweep",
            "schedule": crontab(hour=0, minute=5),
        },
        "monitoring-sweep": {
            "task": "app.tasks.monitoring_tasks.celery_monitoring_sweep",
            "schedule": 60.0,  # every minute
        },
        "daily-appointment-reminders": {
            "task": "app.tasks.notification_tasks.celery_appointment_reminders",
            "schedule": crontab(hour=8, minute=0),
        },
        "hourly-medication-reminders": {
            "task": "app.tasks.notification_tasks.celery_medication_reminders",
            "schedule": crontab(minute=0),
        },
        "es-index-sweep": {
            "task": "index_all_clinical_data",
            "schedule": 900.0,  # every 15 minutes
        }
    }

    class ContextTask(celery_app.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app.Task = ContextTask

    # Register tasks
    from app.tasks.care_plan_tasks import register_care_plan_tasks
    from app.tasks.monitoring_tasks import register_monitoring_tasks
    from app.tasks.notification_tasks import register_notification_tasks
    from app.tasks.search_indexer_tasks import register_search_indexer_tasks

    register_care_plan_tasks(celery_app)
    register_monitoring_tasks(celery_app)
    register_notification_tasks(celery_app)
    register_search_indexer_tasks(celery_app)

    return celery_app

celery = make_celery(app)
