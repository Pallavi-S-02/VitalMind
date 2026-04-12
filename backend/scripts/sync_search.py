#!/usr/bin/env python3
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from app.models.db import db
from app.models.patient import PatientProfile
from app.models.report import MedicalReport
from app.models.care_plan import CarePlan
from app.services.search_service import SearchService

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def sync_all():
    app = create_app()
    with app.app_context():
        logger.info("Starting Search Synchronization...")
        patients = PatientProfile.query.all()
        for p in patients:
            SearchService.sync_patient(p)
            logger.info(f"Synced Patient: {p.user.first_name} {p.user.last_name}")
        
        reports = MedicalReport.query.all()
        for r in reports:
            SearchService.sync_report(r)
            
        plans = CarePlan.query.all()
        for cp in plans:
            SearchService.sync_care_plan(cp)

        logger.info("Search Synchronization Completed! ✅")

if __name__ == "__main__":
    sync_all()
