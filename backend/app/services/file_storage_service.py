"""
file_storage_service.py — High-level service handling MedicalReport database logic operations.
"""

import uuid
import logging
from datetime import datetime, date
from typing import Optional, Dict, Any

from app.models.db import db
from app.models.report import MedicalReport
from app.integrations.s3_client import s3_client

logger = logging.getLogger(__name__)

class FileStorageService:
    @staticmethod
    def upload_new_report(patient_id: str, filename: str, file_bytes: bytes, mime_type: str = 'application/pdf') -> Optional[dict]:
        """
        Takes raw file bytes from API, creates a database record in 'processing' state,
        uploads to MinIO, and returns the constructed pending object.
        """
        try:
            # 1. Generate unique file key to prevent collisions
            ext = filename.split('.')[-1] if '.' in filename else 'bin'
            file_key = f"{patient_id}/{uuid.uuid4().hex}_{filename}"
            
            # 2. Upload to S3
            upload_res = s3_client.upload_file_bytes(file_bytes, file_key, content_type=mime_type)
            if not upload_res:
                logger.error("FileStorageService: S3 upload failed for %s", filename)
                return None
                
            # 3. Create Patient Database Record
            report_record = MedicalReport(
                patient_id=patient_id,
                title=filename,
                type="lab_result", # default, the agent will update this
                date=date.today(),
                file_url=file_key, # Stores S3 key
                structured_data={"status": "processing"} # Initial processing state
            )
            
            db.session.add(report_record)
            db.session.commit()
            
            return {
                "id": str(report_record.id),
                "title": report_record.title,
                "status": "processing"
            }
            
        except Exception as e:
            logger.error("FileStorageService: Failed to upload new report: %s", e)
            db.session.rollback()
            return None

    def get_report_with_presigned_url(report_id: str, patient_id: Optional[str] = None) -> Optional[dict]:
        """
        Fetches the report from the DB and generates a temporary signed URL for the frontend viewer.
        Supports filtering by patient_id for security, or None for staff access.
        """
        try:
            query = db.session.query(MedicalReport).filter(MedicalReport.id == report_id)
            if patient_id:
                query = query.filter(MedicalReport.patient_id == patient_id)
                
            report = query.first()
            if not report:
                return None
                
            # Generate temporary view URL (valid for 1 hour)
            temp_url = s3_client.get_presigned_url(report.file_url) if report.file_url else None
            
            return {
                "id": str(report.id),
                "title": report.title,
                "type": report.type,
                "date": report.date.isoformat(),
                "file_url": temp_url,
                "summary": report.summary,
                "structured_data": report.structured_data,
                "created_at": report.created_at.isoformat()
            }
        except Exception as e:
            logger.error("FileStorageService: Error getting report %s: %s", report_id, e)
            return None

    @staticmethod
    def get_patient_reports(patient_id: str) -> list[dict]:
        """
        List all reports for a specific patient.
        """
        try:
            reports = db.session.query(MedicalReport).filter_by(patient_id=patient_id).order_by(MedicalReport.created_at.desc()).all()
            
            return [
                {
                    "id": str(r.id),
                    "title": r.title,
                    "type": r.type,
                    "date": r.date.isoformat(),
                    # For list views, check if 'status' exists inside structured_data, effectively "completed" or "processing"
                    "status": r.structured_data.get("status", "completed") if r.structured_data else "processing"
                }
                for r in reports
            ]
        except Exception as e:
            logger.error("FileStorageService: Error getting reports for patient %s: %s", patient_id, e)
            return []
