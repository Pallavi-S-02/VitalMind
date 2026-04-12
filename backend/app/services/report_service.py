from app.models.db import db
from app.models.report import MedicalReport
from datetime import datetime

class ReportService:
    @staticmethod
    def get_patient_reports(patient_id):
        return MedicalReport.query.filter_by(patient_id=patient_id).order_by(MedicalReport.upload_date.desc()).all()

    @staticmethod
    def get_report_by_id(report_id):
        return MedicalReport.query.get(report_id)

    @staticmethod
    def create_report_record(data):
        report = MedicalReport(
            patient_id=data['patient_id'],
            report_type=data['report_type'],
            file_url=data['file_url'],
            title=data.get('title'),
            summary=data.get('summary'),
            analysis_status='pending'
        )
        db.session.add(report)
        db.session.commit()
        return report

    @staticmethod
    def update_report_status(report_id, status, summary=None, extracted_data=None):
        report = MedicalReport.query.get(report_id)
        if not report:
            return None
            
        report.analysis_status = status
        if summary:
            report.summary = summary
        if extracted_data:
            report.extracted_data = extracted_data
            
        db.session.commit()
        return report
