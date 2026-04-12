import logging
from app.integrations.elasticsearch_client import es_client
from app.utils.anonymize import anonymize_patient_data

logger = logging.getLogger(__name__)

class SearchService:
    
    @staticmethod
    def sync_patient(patient_model) -> bool:
        """Takes a SQLAlchemy PatientProfile, drops PHI, and indexes it."""
        try:
            # We assume patient_model has a to_dict() function
            raw_data = patient_model.to_dict()
            safe_data = anonymize_patient_data(raw_data)
            
            # Additional search-friendly fields
            safe_data["document_type"] = "patient"
            safe_data["id"] = str(patient_model.id)
            
            return es_client.index_document(
                index_name="medassist_patients",
                doc_id=str(patient_model.id),
                document=safe_data
            )
        except Exception as e:
            logger.error("Error syncing patient to ES: %s", e)
            return False

    @staticmethod
    def sync_report(report_model) -> bool:
        """Takes a MedicalReport and indexes its AI structured data."""
        try:
            # Drop the heavy base64 items if present, we only want text
            data = report_model.to_dict()
            doc = {
                "id": str(report_model.id),
                "patient_id": str(report_model.patient_id),
                "filename": data.get("filename", ""),
                "summary": data.get("summary", ""),
                "structured_data": data.get("structured_data", {}),
                "document_type": "report"
            }
            return es_client.index_document(
                index_name="medassist_reports",
                doc_id=str(report_model.id),
                document=doc
            )
        except Exception as e:
            logger.error("Error syncing report to ES: %s", e)
            return False

    @staticmethod
    def sync_care_plan(care_plan_model) -> bool:
        try:
            doc = {
                "id": str(care_plan_model.id),
                "patient_id": str(care_plan_model.patient_id),
                "title": care_plan_model.title,
                "description": care_plan_model.description,
                "status": care_plan_model.status,
                "document_type": "care_plan"
            }
            return es_client.index_document(
                index_name="medassist_care_plans",
                doc_id=str(care_plan_model.id),
                document=doc
            )
        except Exception as e:
            logger.error("Error syncing care plan to ES: %s", e)
            return False

    @staticmethod
    def global_search(query: str, limit: int = 20) -> list:
        """Searches across all clinical indices."""
        return es_client.search(
            index_name="all", # "medassist_*" wildcard applied inside client
            query=query,
            fields=[
                "filename^2", 
                "summary", 
                "title^2", 
                "description", 
                "medical_history", 
                "allergies", 
                "structured_data.medications",
                "structured_data.diagnoses"
            ],
            size=limit
        )
