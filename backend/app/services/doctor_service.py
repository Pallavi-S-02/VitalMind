from app.models.db import db
from app.models.doctor import DoctorProfile, DoctorAvailability
from app.models.user import User

class DoctorService:
    @staticmethod
    def get_all_doctors(limit=100, offset=0):
        return DoctorProfile.query.limit(limit).offset(offset).all()

    @staticmethod
    def get_doctor_by_id(doctor_id):
        return DoctorProfile.query.get(doctor_id)

    @staticmethod
    def update_doctor_profile(doctor_id, data):
        doctor = DoctorProfile.query.get(doctor_id)
        if not doctor:
            return None
            
        if 'specialization' in data:
            doctor.specialization = data['specialization']
        if 'license_number' in data:
            doctor.license_number = data['license_number']
        if 'years_of_experience' in data:
            doctor.years_of_experience = data['years_of_experience']
        if 'education' in data:
            doctor.education = data['education']
        if 'hospital_affiliation' in data:
            doctor.hospital_affiliation = data['hospital_affiliation']
        if 'bio' in data:
            doctor.bio = data['bio']
        if 'consultation_fee' in data:
            doctor.consultation_fee = data['consultation_fee']
            
        db.session.commit()
        return doctor

    @staticmethod
    def add_availability(doctor_id, data):
        availability = DoctorAvailability(
            doctor_id=doctor_id,
            day_of_week=data['day_of_week'],
            start_time=data['start_time'],
            end_time=data['end_time'],
            is_available=data.get('is_available', True)
        )
        db.session.add(availability)
        db.session.commit()
        return availability
