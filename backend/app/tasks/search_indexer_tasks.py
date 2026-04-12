import logging

logger = logging.getLogger(__name__)

def run_index_all_clinical_data():
    """
    Crawls Postgres and syncs recent or all active records into Elasticsearch.
    Scheduled to run every 10-15 minutes by Celery Beat.
    """
    logger.info("Starting Elasticsearch index sweep...")
    patients_synced = 0
    reports_synced = 0
    plans_synced = 0
    
    try:
        from app.models.patient import PatientProfile
        from app.models.report import MedicalReport
        from app.models.care_plan import CarePlan
        from app.services.search_service import SearchService
        from flask import current_app
        
        # We assume celery_worker creates app context.
        # But if standard current_app is unavailable, Celery usually proxies it.
        
        # Sync Patients
        patients = PatientProfile.query.all()
        for p in patients:
            if SearchService.sync_patient(p):
                patients_synced += 1
        
        # Sync Reports
        # Only sync those that have data to index
        reports = MedicalReport.query.filter_by(status="completed").all()
        for r in reports:
            if SearchService.sync_report(r):
                reports_synced += 1
                
        # Sync Care Plans
        plans = CarePlan.query.all()
        for cp in plans:
            if SearchService.sync_care_plan(cp):
                plans_synced += 1
                
        logger.info("ES Sync Complete: %d patients, %d reports, %d care plans.", patients_synced, reports_synced, plans_synced)
        return {
            "status": "success",
            "patients": patients_synced,
            "reports": reports_synced,
            "care_plans": plans_synced
        }
    except Exception as e:
        logger.error("ES Sync failed: %s", str(e))
        return {"status": "error", "error": str(e)}

def register_search_indexer_tasks(celery_app) -> None:
    if celery_app is None:
        return

    @celery_app.task(name='index_all_clinical_data', bind=True)
    def index_all_clinical_data(self):
        return run_index_all_clinical_data()

    logger.info("SearchIndexer: Celery task registered")
