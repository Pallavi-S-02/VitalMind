#!/usr/bin/env python3
"""
seed_db.py — Comprehensive Database Seed Script for VitalMind
"""

import sys
import os
import random
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add backend directory to sys.path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from app.models.db import db
from app.models.user import User, Role
from app.models.doctor import DoctorProfile
from app.models.patient import PatientProfile, MedicalHistory, Allergy
from app.models.medication import Medication
from app.models.appointment import Appointment
from app.models.report import MedicalReport
from app.integrations.influxdb_client import write_vitals
from app.services.search_service import SearchService

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def seed_roles():
    logger.info("--- Seeding Roles ---")
    roles = ["patient", "doctor", "nurse", "admin"]
    role_map = {}
    for r_name in roles:
        try:
            role = Role.query.filter_by(name=r_name).first()
            if not role:
                role = Role(name=r_name, description=f"{r_name.capitalize()} Role")
                db.session.add(role)
                db.session.commit()
                logger.info(f"Created role: {r_name}")
            else:
                logger.info(f"Role already exists: {r_name}")
            role_map[r_name] = role.id
        except Exception as e:
            logger.error(f"Failed to seed role '{r_name}': {e}")
            db.session.rollback()
    return role_map

def seed_admin(role_id):
    logger.info("--- Seeding Admin ---")
    try:
        user = User.query.filter_by(email="admin@vitalmind.com").first()
        if not user:
            user = User(
                email="admin@vitalmind.com",
                first_name="System",
                last_name="Admin",
                role_id=role_id,
                is_active=True,
                is_verified=True
            )
            user.set_password("Admin123!")
            db.session.add(user)
            db.session.commit()
            logger.info("Created Admin user: admin@vitalmind.com")
        else:
            logger.info("Admin user already exists")
    except Exception as e:
        logger.error(f"Failed to seed admin: {e}")
        db.session.rollback()

def seed_doctors(role_id):
    logger.info("--- Seeding Doctors ---")
    doctors_data = [
        ("dr.sharma@vitalmind.com", "Rahul", "Sharma", "Cardiologist", "MED-001", "10 years experience", 100),
        ("dr.patel@vitalmind.com", "Priya", "Patel", "Neurologist", "MED-002", "8 years experience", 120),
        ("dr.singh@vitalmind.com", "Amit", "Singh", "General Physician", "MED-003", "15 years experience", 80),
        ("dr.rao@vitalmind.com", "Sunita", "Rao", "Diabetologist", "MED-004", "12 years experience", 110),
        ("dr.mehta@vitalmind.com", "Vikram", "Mehta", "Orthopedic", "MED-005", "9 years experience", 130),
    ]
    
    doc_map = {}
    for email, first, last, spec, lic, bio, fee in doctors_data:
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                user = User(
                    email=email, first_name=first, last_name=last,
                    role_id=role_id, is_active=True, is_verified=True
                )
                user.set_password("Doctor123!")
                db.session.add(user)
                db.session.flush()
                
                profile = DoctorProfile(
                    user_id=user.id,
                    specialization=spec,
                    license_number=lic,
                    bio=bio,
                    consultation_fee=fee
                )
                db.session.add(profile)
                db.session.commit()
                logger.info(f"Created Doctor: {first} {last} ({spec})")
            else:
                logger.info(f"Doctor already exists: {first} {last}")
                
            doc_map[first] = user.doctor_profile.id
        except Exception as e:
            logger.error(f"Failed to seed doctor '{first} {last}': {e}")
            db.session.rollback()
    return doc_map

def seed_patients(role_id):
    logger.info("--- Seeding Patients ---")
    # Format: email, first, last, gender, blood_type, conditions, allergies
    patients_data = [
        ("john@test.com", "John", "Doe", "Male", "O+", ["Type 2 Diabetes", "Hypertension"], ["Penicillin"]),
        ("priya@test.com", "Priya", "Sharma", "Female", "A+", ["Hypertension"], []),
        ("rahul@test.com", "Rahul", "Kumar", "Male", "B+", ["Coronary Artery Disease", "Diabetes"], ["Aspirin"]),
        ("sunita@test.com", "Sunita", "Patel", "Female", "AB+", ["Pregnancy", "Gestational Diabetes"], ["Sulfa drugs"]),
        ("amit@test.com", "Amit", "Singh", "Male", "O-", ["Asthma", "Obesity"], ["NSAIDs"]),
    ]
    
    pat_map = {}
    for email, first, last, gender, btype, conds, alls in patients_data:
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                user = User(
                    email=email, first_name=first, last_name=last,
                    role_id=role_id, is_active=True, is_verified=True
                )
                user.set_password("Patient123!")
                db.session.add(user)
                db.session.flush()
                
                # Approximate date of birth logic to ensure consistent seeding
                # This could be exact from prompt but for simplicity defaulting to arbitrary date mapping.
                age_map = {"John": 45, "Priya": 32, "Rahul": 67, "Sunita": 28, "Amit": 55}
                dob = datetime.now() - timedelta(days=365 * age_map.get(first, 30))
                
                profile = PatientProfile(
                    user_id=user.id,
                    gender=gender,
                    blood_type=btype,
                    date_of_birth=dob.date()
                )
                db.session.add(profile)
                db.session.flush()
                
                for c in conds:
                    db.session.add(MedicalHistory(patient_id=profile.id, condition_name=c, diagnosis_date=datetime.now().date(), status="active"))
                for a in alls:
                    db.session.add(Allergy(patient_id=profile.id, allergen=a, severity="moderate"))
                
                db.session.commit()
                SearchService.sync_patient(profile)
                logger.info(f"Created Patient: {first} {last}")
            else:
                logger.info(f"Patient already exists: {first} {last}")
            
            pat_map[first] = user.patient_profile.id
        except Exception as e:
            logger.error(f"Failed to seed patient '{first} {last}': {e}")
            db.session.rollback()
    return pat_map

def seed_medications(pat_map):
    logger.info("--- Seeding Medications ---")
    meds = {
        "John": [("Metformin", "500mg", "twice daily"), ("Ramipril", "5mg", "once daily"), ("Aspirin", "75mg", "once daily")],
        "Priya": [("Amlodipine", "5mg", "once daily"), ("Atenolol", "50mg", "once daily")],
        "Rahul": [("Warfarin", "5mg", "once daily"), ("Atorvastatin", "40mg", "once daily"), ("Metoprolol", "25mg", "twice daily")],
        "Sunita": [("Folic Acid", "5mg", "once daily"), ("Iron supplements", "Unknown", "once daily")],
        "Amit": [("Salbutamol", "Unknown", "as needed"), ("Montelukast", "10mg", "once daily")]
    }
    
    from app.models.medication import Prescription
    
    for pat_name, pat_meds in meds.items():
        pat_id = pat_map.get(pat_name)
        if not pat_id:
            continue
            
        try:
            doc = DoctorProfile.query.first()
            if not doc:
                continue
                
            for name, dose, freq in pat_meds:
                # 1. Ensure Medication exists in the library
                med = Medication.query.filter_by(name=name).first()
                if not med:
                    med = Medication(name=name, description=f"{name} medication")
                    db.session.add(med)
                    db.session.flush()
                
                # 2. Add Prescription for this patient
                exists = Prescription.query.filter_by(patient_id=pat_id, medication_id=med.id).first()
                if not exists:
                    db.session.add(Prescription(
                        patient_id=pat_id,
                        doctor_id=doc.id,
                        medication_id=med.id,
                        dosage=dose,
                        frequency=freq,
                        start_date=datetime.now().date(),
                        status="active"
                    ))
            db.session.commit()
            logger.info(f"Created Medications/Prescriptions for {pat_name}")
        except Exception as e:
            logger.error(f"Failed to seed meds for '{pat_name}': {e}")
            db.session.rollback()

def seed_appointments(pat_map, doc_map):
    logger.info("--- Seeding Appointments ---")
    now = datetime.now(timezone.utc)
    appts = [
        ("John", "Rahul", now + timedelta(hours=2), "Cardiology"),
        ("Priya", "Priya", now + timedelta(days=1, hours=11), "Neurology"), # Assuming 11am tomorrow roughly 1 day
        ("Rahul", "Rahul", now + timedelta(days=2, hours=15), "Cardiology"),
        ("Sunita", "Sunita", now + timedelta(days=7), "Diabetology"),
        ("Amit", "Amit", now + timedelta(hours=4), "General")
    ]
    
    for pat_name, doc_name, start_dt, reason in appts:
        pat_id = pat_map.get(pat_name)
        doc_id = doc_map.get(doc_name)
        if not pat_id or not doc_id:
            logger.warning(f"Skipping appt {pat_name} -> {doc_name} due to missing ID")
            continue
        try:
            exists = Appointment.query.filter_by(patient_id=pat_id, doctor_id=doc_id, status="scheduled").first()
            if not exists:
                db.session.add(Appointment(
                    patient_id=pat_id, doctor_id=doc_id, start_time=start_dt, end_time=start_dt + timedelta(minutes=30),
                    status="scheduled", type="in_person", reason=reason
                ))
                db.session.commit()
                logger.info(f"Created Appointment for {pat_name} with Dr. {doc_name}")
            else:
                 logger.info(f"Appointment already exists for {pat_name} with Dr. {doc_name}")
        except Exception as e:
            logger.error(f"Failed to seed appt for '{pat_name}': {e}")
            db.session.rollback()

def seed_care_plans(pat_map):
    logger.info("--- Seeding Care Plan for John ---")
    john_id = pat_map.get("John")
    if not john_id:
        return
    try:
        from app.models.care_plan import CarePlan, CarePlanTask
        exists = CarePlan.query.filter_by(patient_id=john_id, title="Diabetes Management Plan").first()
        if not exists:
            cp = CarePlan(
                patient_id=john_id, title="Diabetes Management Plan",
                goals={
                    "1": "Reduce HbA1c below 7% in 3 months",
                    "2": "Walk 30 minutes daily",
                    "3": "Reduce carbohydrate intake",
                    "4": "Monitor glucose twice daily"
                }
            )
            db.session.add(cp)
            db.session.flush()
            db.session.add(CarePlanTask(care_plan_id=cp.id, title="Daily medication reminders", type="medication_reminder", frequency="daily"))
            db.session.commit()
            SearchService.sync_care_plan(cp)
            logger.info("Created Care Plan for John")
        else:
            logger.info("Care Plan for John already exists")
    except Exception as e:
        logger.error(f"Failed to seed care plan: {e}")
        db.session.rollback()

def seed_reports(pat_map):
    logger.info("--- Seeding Medical Reports ---")
    for pat_name, pat_id in pat_map.items():
        try:
            exists = MedicalReport.query.filter_by(patient_id=pat_id).first()
            if not exists:
                rp = MedicalReport(
                    patient_id=pat_id, 
                    title=f"{pat_name} Lab Report",
                    type="lab_result",
                    date=datetime.now().date(),
                    file_url=f"dummy/{pat_name}_Lab.pdf"
                )
                db.session.add(rp)
                db.session.commit()
                SearchService.sync_report(rp)
                logger.info(f"Created Medical Report for {pat_name}")
            else:
                logger.info(f"Medical Report already exists for {pat_name}")
        except Exception as e:
            logger.error(f"Failed to seed report for '{pat_name}': {e}")
            db.session.rollback()

def seed_vitals(pat_map):
    logger.info("--- Seeding InfluxDB Vitals ---")
    now = datetime.now(timezone.utc)
    for pat_name, pat_id in pat_map.items():
        try:
            is_critical = (pat_name == "Rahul")
            for h in range(24):
                ts = now - timedelta(hours=23 - h)
                vitals_payload = {}
                
                if pat_name == "John":
                    vitals_payload = {
                        "heart_rate": random.randint(75, 85),
                        "systolic_bp": 130,
                        "diastolic_bp": 85,
                        "spo2": random.randint(97, 98),
                        "temperature_c": round(random.uniform(37.0, 37.2), 1)
                    }
                elif pat_name == "Rahul":
                    vitals_payload = {
                        "heart_rate": random.randint(110, 120),
                        "systolic_bp": 90,
                        "diastolic_bp": 60,
                        "spo2": random.randint(91, 93),
                        "temperature_c": round(random.uniform(38.5, 39.0), 1),
                        "news2_score": random.randint(8, 10)
                    }
                else:
                    vitals_payload = {
                        "heart_rate": random.randint(65, 80),
                        "systolic_bp": 120,
                        "diastolic_bp": 80,
                        "spo2": random.randint(96, 99),
                        "temperature_c": 36.6
                    }
                
                write_vitals(str(pat_id), vitals_payload, source="seed_script", timestamp=ts)
            logger.info(f"Written 24hr vitals to InfluxDB for {pat_name} (Critical: {is_critical})")
        except Exception as e:
            logger.error(f"Failed to seed vitals for '{pat_name}': {e}")

def main():
    app = create_app()
    with app.app_context():
        logger.info("Starting VitalMind database seeding...")
        role_map = seed_roles()
        seed_admin(role_map.get("admin"))
        
        doc_map = seed_doctors(role_map.get("doctor"))
        pat_map = seed_patients(role_map.get("patient"))
        
        seed_medications(pat_map)
        seed_appointments(pat_map, doc_map)
        seed_care_plans(pat_map)
        seed_reports(pat_map)
        seed_vitals(pat_map)
        
        logger.info("✅ Database seeding completed successfully!")

if __name__ == "__main__":
    main()
