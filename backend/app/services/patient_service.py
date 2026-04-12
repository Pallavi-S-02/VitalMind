from app.models.db import db
from app.models.patient import PatientProfile, MedicalHistory, Allergy
from app.models.user import User

class PatientService:
    @staticmethod
    def get_all_patients(limit=100, offset=0):
        return PatientProfile.query.limit(limit).offset(offset).all()

    @staticmethod
    def get_patient_by_id(patient_id):
        import uuid
        try:
            if isinstance(patient_id, str):
                patient_id = uuid.UUID(patient_id)
            return PatientProfile.query.get(patient_id)
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def get_patient_by_user_id(user_id):
        return PatientProfile.query.filter_by(user_id=user_id).first()

    @staticmethod
    def update_patient_profile(patient_id, data):
        patient = PatientProfile.query.get(patient_id)
        if not patient:
            return None
            
        if 'date_of_birth' in data:
            dob_val = data['date_of_birth']
            if dob_val:
                from datetime import date
                patient.date_of_birth = date.fromisoformat(dob_val.split('T')[0]) if isinstance(dob_val, str) else dob_val
            else:
                patient.date_of_birth = None
        if 'gender' in data:
            patient.gender = data['gender']
        if 'blood_type' in data:
            patient.blood_type = data['blood_type']
        if 'emergency_contact_name' in data:
            patient.emergency_contact_name = data['emergency_contact_name']
        if 'emergency_contact_phone' in data:
            patient.emergency_contact_phone = data['emergency_contact_phone']
        if 'emergency_contact_relation' in data:
            patient.emergency_contact_relation = data['emergency_contact_relation']
        if 'ssn' in data:
            patient.ssn = data['ssn']
        if 'address' in data:
            patient.address = data['address']
        if 'height_cm' in data:
            patient.height_cm = data['height_cm']
        if 'weight_kg' in data:
            patient.weight_kg = data['weight_kg']
        if 'chronic_diseases' in data:
            patient.chronic_diseases = data['chronic_diseases']
            
        # Sync medical history if provided
        if 'medical_history' in data:
            # Simple sync: remove old and add new
            # In a production app, we'd more carefully merge or transition statuses
            MedicalHistory.query.filter_by(patient_id=patient_id).delete()
            for condition in data['medical_history']:
                if condition.strip():
                    new_history = MedicalHistory(
                        patient_id=patient_id,
                        condition_name=condition.strip(),
                        status='active'
                    )
                    db.session.add(new_history)

        # Sync allergies if provided
        if 'allergies' in data:
            Allergy.query.filter_by(patient_id=patient_id).delete()
            for allergen in data['allergies']:
                if allergen.strip():
                    new_allergy = Allergy(
                        patient_id=patient_id,
                        allergen=allergen.strip()
                    )
                    db.session.add(new_allergy)

        db.session.commit()
        return patient

    @staticmethod
    def add_medical_history(patient_id, data):
        history = MedicalHistory(
            patient_id=patient_id,
            condition_name=data['condition_name'],
            diagnosis_date=data.get('diagnosis_date'),
            status=data.get('status', 'active'),
            notes=data.get('notes')
        )
        db.session.add(history)
        db.session.commit()
        return history

    @staticmethod
    def add_allergy(patient_id, data):
        allergy = Allergy(
            patient_id=patient_id,
            allergen=data['allergen'],
            reaction=data.get('reaction'),
            severity=data.get('severity')
        )
        db.session.add(allergy)
        db.session.commit()
        return allergy
