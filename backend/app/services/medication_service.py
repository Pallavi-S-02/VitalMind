from app.models.db import db
from app.models.medication import Medication, Prescription
from datetime import datetime, date

class MedicationService:
    @staticmethod
    def get_patient_medications(patient_id):
        # We actually want the active prescriptions for the patient
        return Prescription.query.filter_by(patient_id=patient_id).order_by(Prescription.created_at.desc()).all()

    @staticmethod
    def get_patient_prescriptions(patient_id):
        return Prescription.query.filter_by(patient_id=patient_id).order_by(Prescription.created_at.desc()).all()

    @staticmethod
    def get_medication_catalog():
        """Returns the list of all available medications in the database."""
        return Medication.query.order_by(Medication.name.asc()).all()

    @staticmethod
    def create_prescription(data):
        """
        Creates a new prescription record.
        Required fields: patient_id, doctor_id, medication_id, dosage, frequency, start_date
        """
        new_prescription = Prescription(
            patient_id=data['patient_id'],
            doctor_id=data['doctor_id'],
            medication_id=data['medication_id'],
            dosage=data['dosage'],
            frequency=data['frequency'],
            route=data.get('route', 'oral'),
            start_date=date.fromisoformat(data['start_date']) if isinstance(data['start_date'], str) else data['start_date'],
            end_date=date.fromisoformat(data['end_date']) if data.get('end_date') and isinstance(data['end_date'], str) else None,
            instructions=data.get('instructions', ''),
            status='active'
        )
        db.session.add(new_prescription)
        db.session.commit()
        return new_prescription

    @staticmethod
    def add_manual_medication(patient_id, data):
        # This would be for patient self-reporting, can be implemented later
        pass

    @staticmethod
    def generate_schedule(patient_id):
        """
        Generates an AI-optimized medication schedule for the patient.
        """
        from app.services.ai_scheduler_service import AISchedulerService
        from app.models.patient import PatientProfile
        
        # Get active prescriptions
        prescriptions = Prescription.query.filter_by(
            patient_id=patient_id, 
            status='active'
        ).all()
        
        if not prescriptions:
            return {
                "patient_id": patient_id,
                "schedule": "No active medications found. Please add prescriptions first.",
                "medications": []
            }

        # Get patient profile for context (age, history, lifestyle)
        patient = PatientProfile.query.get(patient_id)
        patient_context = {}
        if patient:
            # Basic context for the AI
            patient_context = {
                "age": (datetime.now().date() - patient.date_of_birth).days // 365 if patient.date_of_birth else "Unknown",
                "chronic_conditions": [c.condition_name for c in patient.conditions] if hasattr(patient, 'conditions') else [],
                "lifestyle_notes": "Standard daily routine" # Future: pull from a patient_notes or similar
            }

        # Format prescriptions for AI
        meds_list = [p.to_dict() for p in prescriptions]
        
        # Generate via AI
        schedule_text = AISchedulerService.generate_optimized_schedule(meds_list, patient_context)
        
        return {
            "patient_id": patient_id,
            "schedule": schedule_text,
            "medications": [m['medication_name'] for m in meds_list]
        }
