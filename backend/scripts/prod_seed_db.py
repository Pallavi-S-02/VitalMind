#!/usr/bin/env python3
"""
prod_seed_db.py — VitalMind Production Seed Script

⚠️  WARNING: This script DELETES existing patient and doctor data
    before reseeding. Run with care on production databases.

Usage:
    cd backend
    python scripts/prod_seed_db.py

Features:
  - Idempotent role/admin/medication seeding (no duplicates)
  - Wipes and recreates all doctor + patient data cleanly
  - Seeds 5 doctors, 5 patients, prescriptions, appointments,
    a care plan, medical reports, and 24hrs of InfluxDB vitals
"""

import sys
import os
import random
import logging
from datetime import datetime, timedelta, date, timezone
from pathlib import Path

# ── Add backend root to path ─────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from app.models.db import db
from app.models.user import User, Role
from app.models.doctor import DoctorProfile, DoctorAvailability
from app.models.patient import PatientProfile, MedicalHistory, Allergy
from app.models.medication import Medication, Prescription
from app.models.appointment import Appointment
from app.models.report import MedicalReport
from app.models.care_plan import CarePlan, CarePlanTask
from app.integrations.influxdb_client import write_vitals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

SECTION = "=" * 60

# ─────────────────────────────────────────────────────────────────────────────
# STEP 0 – Wipe existing patient & doctor data
# ─────────────────────────────────────────────────────────────────────────────

DOCTOR_EMAILS = [
    "dr.sharma@vitalmind.com",
    "dr.patel@vitalmind.com",
    "dr.singh@vitalmind.com",
    "dr.rao@vitalmind.com",
    "dr.mehta@vitalmind.com",
]
PATIENT_EMAILS = [
    "john@test.com",
    "priya@test.com",
    "rahul@test.com",
    "sunita@test.com",
    "amit@test.com",
]
ALL_SEED_EMAILS = DOCTOR_EMAILS + PATIENT_EMAILS


def wipe_patient_and_doctor_data():
    """
    Delete all seeded patient and doctor data cleanly.
    Works in two phases:
      1. Manually delete non-cascade child tables using ORM profile IDs.
      2. Delete user rows by email (cascades to profiles automatically).
    """
    logger.info(SECTION)
    logger.info("STEP 0 – Wiping existing patient & doctor data …")
    logger.info(SECTION)

def wipe_patient_and_doctor_data():
    """
    Hard-wipe all rows associated with the known seed emails.
    SQL order validated against the live schema's FK graph.
    """
    logger.info(SECTION)
    logger.info("STEP 0 – Wiping existing patient & doctor data …")
    logger.info(SECTION)

    from sqlalchemy import text

    existing = User.query.filter(User.email.in_(ALL_SEED_EMAILS)).count()
    if existing == 0:
        logger.info("  No existing seed users — nothing to wipe.")
        return

    logger.info("  Found %d existing seed users to wipe.", existing)

    p = ", ".join(f"'{e}'" for e in PATIENT_EMAILS)
    d = ", ".join(f"'{e}'" for e in DOCTOR_EMAILS)
    a = ", ".join(f"'{e}'" for e in ALL_SEED_EMAILS)

    pat_ids = f"SELECT pp.id FROM patient_profiles pp JOIN users u ON u.id = pp.user_id AND u.email IN ({p})"
    doc_ids = f"SELECT dp.id FROM doctor_profiles dp JOIN users u ON u.id = dp.user_id AND u.email IN ({d})"

    # Full DELETE sequence — validated against live schema FK graph
    STATEMENTS = [
        ("direct_messages",   f"DELETE FROM direct_messages WHERE conversation_id IN (SELECT dc.id FROM direct_conversations dc WHERE dc.patient_id IN ({pat_ids}) OR dc.doctor_id IN ({doc_ids}))"),
        ("direct_convs",      f"DELETE FROM direct_conversations WHERE patient_id IN ({pat_ids}) OR doctor_id IN ({doc_ids})"),
        ("conversation_logs", f"DELETE FROM conversation_logs WHERE patient_id IN ({pat_ids})"),
        ("symptom_sessions",  f"DELETE FROM symptom_sessions WHERE patient_id IN ({pat_ids})"),
        ("alerts",            f"DELETE FROM alerts WHERE patient_id IN ({pat_ids})"),
        ("iot_devices",       f"DELETE FROM iot_devices WHERE patient_id IN ({pat_ids})"),
        ("care_plan_tasks",   f"DELETE FROM care_plan_tasks WHERE care_plan_id IN (SELECT cp.id FROM care_plans cp WHERE cp.patient_id IN ({pat_ids}) OR cp.doctor_id IN ({doc_ids}))"),
        ("care_plans",        f"DELETE FROM care_plans WHERE patient_id IN ({pat_ids}) OR doctor_id IN ({doc_ids})"),
        ("medical_reports",   f"DELETE FROM medical_reports WHERE patient_id IN ({pat_ids}) OR doctor_id IN ({doc_ids})"),
        ("appointments",      f"DELETE FROM appointments WHERE patient_id IN ({pat_ids}) OR doctor_id IN ({doc_ids})"),
        ("prescriptions",     f"DELETE FROM prescriptions WHERE patient_id IN ({pat_ids}) OR doctor_id IN ({doc_ids})"),
        ("medical_history",   f"DELETE FROM medical_history WHERE patient_id IN ({pat_ids})"),
        ("allergies",         f"DELETE FROM allergies WHERE patient_id IN ({pat_ids})"),
        ("notifications",     f"DELETE FROM notifications WHERE user_id IN (SELECT id FROM users WHERE email IN ({a}))"),
        ("audit_logs",        f"DELETE FROM audit_logs WHERE user_id IN (SELECT id FROM users WHERE email IN ({a}))"),
        ("patient_profiles",  f"DELETE FROM patient_profiles WHERE user_id IN (SELECT id FROM users WHERE email IN ({p}))"),
        ("doctor_avail",      f"DELETE FROM doctor_availability WHERE doctor_id IN ({doc_ids})"),
        ("doctor_profiles",   f"DELETE FROM doctor_profiles WHERE user_id IN (SELECT id FROM users WHERE email IN ({d}))"),
        ("users",             f"DELETE FROM users WHERE email IN ({a})"),
    ]

    conn = db.engine.connect()
    trans = conn.begin()
    try:
        for label, sql in STATEMENTS:
            r = conn.execute(text(sql))
            logger.info("    ✓ %-20s %d rows deleted", label, r.rowcount)
        trans.commit()
        logger.info("✅  Wipe complete — %d seed users removed.", existing)
    except Exception as exc:
        trans.rollback()
        logger.error("❌ Wipe failed at step: %s", exc)
        raise
    finally:
        conn.close()






# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 – Roles (idempotent)
# ─────────────────────────────────────────────────────────────────────────────

def seed_roles() -> dict:
    logger.info(SECTION)
    logger.info("STEP 1 – Seeding Roles …")
    logger.info(SECTION)

    role_names = ["patient", "doctor", "nurse", "admin"]
    role_map = {}
    for name in role_names:
        try:
            role = Role.query.filter_by(name=name).first()
            if not role:
                role = Role(name=name, description=f"{name.capitalize()} role")
                db.session.add(role)
                db.session.commit()
                logger.info("  ✅ Created role: %s", name)
            else:
                logger.info("  ➡️  Role already exists: %s", name)
            role_map[name] = role.id
        except Exception as exc:
            db.session.rollback()
            logger.error("  ❌ Failed to seed role '%s': %s", name, exc)
    return role_map


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 – Admin (idempotent)
# ─────────────────────────────────────────────────────────────────────────────

def seed_admin(role_id):
    logger.info(SECTION)
    logger.info("STEP 2 – Seeding Admin …")
    logger.info(SECTION)

    email = "admin@vitalmind.com"
    try:
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(
                email=email,
                first_name="System",
                last_name="Admin",
                role_id=role_id,
                is_active=True,
                is_verified=True,
            )
            user.set_password("Admin123!")
            db.session.add(user)
            db.session.commit()
            logger.info("  ✅ Created admin: %s", email)
        else:
            logger.info("  ➡️  Admin already exists: %s", email)
    except Exception as exc:
        db.session.rollback()
        logger.error("  ❌ Failed to seed admin: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 – Doctors
# ─────────────────────────────────────────────────────────────────────────────

DOCTORS = [
    {
        "email": "dr.sharma@vitalmind.com",
        "first": "Rahul",
        "last": "Sharma",
        "spec": "Cardiologist",
        "license": "MED-001",
        "bio": "10 years experience in Cardiology",
        "fee": 100.0,
        "key": "Sharma",          # used to link patients to this doctor
    },
    {
        "email": "dr.patel@vitalmind.com",
        "first": "Priya",
        "last": "Patel",
        "spec": "Neurologist",
        "license": "MED-002",
        "bio": "8 years experience in Neurology",
        "fee": 120.0,
        "key": "Patel",
    },
    {
        "email": "dr.singh@vitalmind.com",
        "first": "Amit",
        "last": "Singh",
        "spec": "General Physician",
        "license": "MED-003",
        "bio": "15 years experience in General Medicine",
        "fee": 80.0,
        "key": "Singh",
    },
    {
        "email": "dr.rao@vitalmind.com",
        "first": "Sunita",
        "last": "Rao",
        "spec": "Diabetologist",
        "license": "MED-004",
        "bio": "12 years experience in Diabetology",
        "fee": 110.0,
        "key": "Rao",
    },
    {
        "email": "dr.mehta@vitalmind.com",
        "first": "Vikram",
        "last": "Mehta",
        "spec": "Orthopedic",
        "license": "MED-005",
        "bio": "9 years experience in Orthopedics",
        "fee": 130.0,
        "key": "Mehta",
    },
]

def seed_doctors(role_id) -> dict:
    logger.info(SECTION)
    logger.info("STEP 3 – Seeding Doctors …")
    logger.info(SECTION)

    doc_map = {}  # key → profile_id
    for d in DOCTORS:
        try:
            user = User(
                email=d["email"],
                first_name=d["first"],
                last_name=d["last"],
                role_id=role_id,
                is_active=True,
                is_verified=True,
            )
            user.set_password("Doctor123!")
            db.session.add(user)
            db.session.flush()

            profile = DoctorProfile(
                user_id=user.id,
                specialization=d["spec"],
                license_number=d["license"],
                bio=d["bio"],
                consultation_fee=d["fee"],
            )
            db.session.add(profile)
            db.session.flush()

            db.session.commit()
            doc_map[d["key"]] = profile.id
            logger.info("  ✅ Created doctor: Dr. %s %s (%s)", d["first"], d["last"], d["spec"])
        except Exception as exc:
            db.session.rollback()
            logger.error("  ❌ Failed doctor '%s %s': %s", d["first"], d["last"], exc)

    return doc_map


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 – Patients
# ─────────────────────────────────────────────────────────────────────────────

PATIENTS = [
    {
        "email": "john@test.com",
        "first": "John",
        "last": "Doe",
        "age": 45,
        "gender": "male",
        "blood_type": "O+",
        "conditions": ["Type 2 Diabetes", "Hypertension"],
        "allergies": [("Penicillin", "moderate")],
        "key": "John",
    },
    {
        "email": "priya@test.com",
        "first": "Priya",
        "last": "Sharma",
        "age": 32,
        "gender": "female",
        "blood_type": "A+",
        "conditions": ["Hypertension"],
        "allergies": [],
        "key": "Priya",
    },
    {
        "email": "rahul@test.com",
        "first": "Rahul",
        "last": "Kumar",
        "age": 67,
        "gender": "male",
        "blood_type": "B+",
        "conditions": ["Coronary Artery Disease", "Diabetes"],
        "allergies": [("Aspirin", "severe")],
        "key": "Rahul",
    },
    {
        "email": "sunita@test.com",
        "first": "Sunita",
        "last": "Patel",
        "age": 28,
        "gender": "female",
        "blood_type": "AB+",
        "conditions": ["Pregnancy", "Gestational Diabetes"],
        "allergies": [("Sulfa drugs", "moderate")],
        "key": "Sunita",
    },
    {
        "email": "amit@test.com",
        "first": "Amit",
        "last": "Singh",
        "age": 55,
        "gender": "male",
        "blood_type": "O-",
        "conditions": ["Asthma", "Obesity"],
        "allergies": [("NSAIDs", "moderate")],
        "key": "Amit",
    },
]

def seed_patients(role_id) -> dict:
    logger.info(SECTION)
    logger.info("STEP 4 – Seeding Patients …")
    logger.info(SECTION)

    pat_map = {}  # key → profile_id
    for p in PATIENTS:
        try:
            dob = (datetime.now() - timedelta(days=365 * p["age"])).date()

            user = User(
                email=p["email"],
                first_name=p["first"],
                last_name=p["last"],
                role_id=role_id,
                is_active=True,
                is_verified=True,
            )
            user.set_password("Patient123!")
            db.session.add(user)
            db.session.flush()

            profile = PatientProfile(
                user_id=user.id,
                date_of_birth=dob,
                gender=p["gender"],
                blood_type=p["blood_type"],
            )
            db.session.add(profile)
            db.session.flush()

            # Medical history
            for cond in p["conditions"]:
                db.session.add(MedicalHistory(
                    patient_id=profile.id,
                    condition_name=cond,
                    diagnosis_date=date.today(),
                    status="active",
                ))

            # Allergies
            for allergen, severity in p["allergies"]:
                db.session.add(Allergy(
                    patient_id=profile.id,
                    allergen=allergen,
                    severity=severity,
                ))

            db.session.commit()
            pat_map[p["key"]] = profile.id
            logger.info("  ✅ Created patient: %s %s (age %s)", p["first"], p["last"], p["age"])
        except Exception as exc:
            db.session.rollback()
            logger.error("  ❌ Failed patient '%s %s': %s", p["first"], p["last"], exc)

    return pat_map


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 – Medications & Prescriptions (catalog idempotent)
# ─────────────────────────────────────────────────────────────────────────────

PRESCRIPTIONS = {
    "John":   [
        ("Metformin",    "500mg",   "twice daily",  "oral"),
        ("Ramipril",     "5mg",     "once daily",   "oral"),
        ("Aspirin",      "75mg",    "once daily",   "oral"),
    ],
    "Priya":  [
        ("Amlodipine",   "5mg",     "once daily",   "oral"),
        ("Atenolol",     "50mg",    "once daily",   "oral"),
    ],
    "Rahul":  [
        ("Warfarin",     "5mg",     "once daily",   "oral"),
        ("Atorvastatin", "40mg",    "once daily",   "oral"),
        ("Metoprolol",   "25mg",    "twice daily",  "oral"),
    ],
    "Sunita": [
        ("Folic Acid",         "5mg",    "once daily",  "oral"),
        ("Iron supplements",   "1 tab",  "once daily",  "oral"),
    ],
    "Amit":   [
        ("Salbutamol",   "inhaler", "as needed",    "inhalation"),
        ("Montelukast",  "10mg",    "once daily",   "oral"),
    ],
}

def seed_medications(pat_map: dict, doc_map: dict):
    logger.info(SECTION)
    logger.info("STEP 5 – Seeding Medications & Prescriptions …")
    logger.info(SECTION)

    # Use the first available doctor as the prescriber (Sharma)
    prescriber_id = doc_map.get("Sharma") or next(iter(doc_map.values()), None)
    if not prescriber_id:
        logger.error("  ❌ No doctors found — skipping medications.")
        return

    for pat_key, meds in PRESCRIPTIONS.items():
        pat_id = pat_map.get(pat_key)
        if not pat_id:
            logger.warning("  ⚠️  Patient '%s' not found — skipping.", pat_key)
            continue

        try:
            for med_name, dosage, frequency, route in meds:
                # Catalog entry (idempotent)
                med = Medication.query.filter_by(name=med_name).first()
                if not med:
                    med = Medication(name=med_name, description=f"{med_name} medication")
                    db.session.add(med)
                    db.session.flush()

                # Prescription
                db.session.add(Prescription(
                    patient_id=pat_id,
                    doctor_id=prescriber_id,
                    medication_id=med.id,
                    dosage=dosage,
                    frequency=frequency,
                    route=route,
                    start_date=date.today(),
                    status="active",
                ))

            db.session.commit()
            logger.info("  ✅ Prescriptions created for %s (%d meds)", pat_key, len(meds))
        except Exception as exc:
            db.session.rollback()
            logger.error("  ❌ Failed prescriptions for '%s': %s", pat_key, exc)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 – Appointments
# ─────────────────────────────────────────────────────────────────────────────

def seed_appointments(pat_map: dict, doc_map: dict):
    logger.info(SECTION)
    logger.info("STEP 6 – Seeding Appointments …")
    logger.info(SECTION)

    now = datetime.now(timezone.utc)

    # (patient_key, doctor_key, start_offset, reason)
    appts = [
        ("John",   "Sharma", now + timedelta(hours=2),                 "Cardiology follow-up"),
        ("Priya",  "Patel",  now + timedelta(days=1, hours=11),        "Neurology consultation"),
        ("Rahul",  "Sharma", now + timedelta(days=2, hours=15),        "Cardiology review"),
        ("Sunita", "Rao",    now + timedelta(days=7),                  "Diabetology check-up"),
        ("Amit",   "Singh",  now + timedelta(hours=4),                 "General physician visit"),
    ]

    for pat_key, doc_key, start_dt, reason in appts:
        pat_id = pat_map.get(pat_key)
        doc_id = doc_map.get(doc_key)

        if not pat_id or not doc_id:
            logger.warning("  ⚠️  Skipping appointment %s → Dr.%s (missing IDs)", pat_key, doc_key)
            continue
        try:
            db.session.add(Appointment(
                patient_id=pat_id,
                doctor_id=doc_id,
                start_time=start_dt.replace(tzinfo=None),   # store as naive UTC
                end_time=(start_dt + timedelta(minutes=30)).replace(tzinfo=None),
                status="scheduled",
                type="in-person",
                reason=reason,
            ))
            db.session.commit()
            logger.info("  ✅ Appointment: %s → Dr. %s (%s)", pat_key, doc_key, reason)
        except Exception as exc:
            db.session.rollback()
            logger.error("  ❌ Failed appointment %s → Dr.%s: %s", pat_key, doc_key, exc)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 7 – InfluxDB Vitals
# ─────────────────────────────────────────────────────────────────────────────

def seed_vitals(pat_map: dict):
    logger.info(SECTION)
    logger.info("STEP 7 – Seeding InfluxDB Vitals (last 24 hours) …")
    logger.info(SECTION)

    now = datetime.now(timezone.utc)

    vitals_config = {
        "John": {           # stable diabetic
            "heart_rate":    (75, 85),
            "systolic_bp":   (128, 132),
            "diastolic_bp":  (83, 87),
            "spo2":          (97, 98),
            "temperature_c": (37.0, 37.2),
        },
        "Priya": {          # hypertension — slightly elevated bp
            "heart_rate":   (70, 80),
            "systolic_bp":  (135, 145),
            "diastolic_bp": (88, 92),
            "spo2":         (97, 99),
            "temperature_c":(36.5, 36.9),
        },
        "Rahul": {          # CRITICAL — high HR, low BP, low SpO2, fever
            "heart_rate":    (110, 120),
            "systolic_bp":   (88, 92),
            "diastolic_bp":  (58, 62),
            "spo2":          (91, 93),
            "temperature_c": (38.5, 39.0),
            "news2_score":   (8, 10),
        },
        "Sunita": {         # pregnant — slightly elevated HR
            "heart_rate":   (80, 92),
            "systolic_bp":  (118, 125),
            "diastolic_bp": (75, 82),
            "spo2":         (97, 99),
            "temperature_c":(36.6, 37.0),
        },
        "Amit": {           # asthma — slightly lower SpO2
            "heart_rate":   (68, 78),
            "systolic_bp":  (120, 128),
            "diastolic_bp": (78, 85),
            "spo2":         (94, 97),
            "temperature_c":(36.4, 36.8),
        },
    }

    for pat_key, pat_id in pat_map.items():
        config = vitals_config.get(pat_key)
        if not config:
            continue

        successes = 0
        for h in range(24):
            ts = now - timedelta(hours=23 - h)
            payload = {}
            for field, (lo, hi) in config.items():
                if isinstance(lo, float) or isinstance(hi, float):
                    payload[field] = round(random.uniform(lo, hi), 1)
                else:
                    payload[field] = random.randint(lo, hi)

            ok = write_vitals(str(pat_id), payload, source="prod_seed", timestamp=ts)
            if ok:
                successes += 1

        is_critical = (pat_key == "Rahul")
        logger.info(
            "  %s Vitals: %s — %d/24 points written%s",
            "✅" if successes == 24 else "⚠️ ",
            pat_key,
            successes,
            " (CRITICAL pattern)" if is_critical else "",
        )


# ─────────────────────────────────────────────────────────────────────────────
# STEP 8 – Care Plan for John
# ─────────────────────────────────────────────────────────────────────────────

def seed_care_plan(pat_map: dict, doc_map: dict):
    logger.info(SECTION)
    logger.info("STEP 8 – Seeding Care Plan for John …")
    logger.info(SECTION)

    john_id = pat_map.get("John")
    doc_id  = doc_map.get("Sharma")
    if not john_id:
        logger.error("  ❌ John not found — skipping care plan.")
        return

    try:
        cp = CarePlan(
            patient_id=john_id,
            doctor_id=doc_id,
            title="Diabetes Management Plan",
            description="Comprehensive 3-month plan to manage Type 2 Diabetes and Hypertension.",
            status="active",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=90),
            goals={
                "1": "Reduce HbA1c below 7% in 3 months",
                "2": "Walk 30 minutes daily",
                "3": "Reduce carbohydrate intake",
                "4": "Monitor glucose twice daily",
            },
        )
        db.session.add(cp)
        db.session.flush()

        tasks = [
            ("Take morning medications", "medication_reminder", "daily",    "morning"),
            ("Take evening medications", "medication_reminder", "daily",    "evening"),
            ("30-minute walk",           "exercise",            "daily",    "morning"),
            ("Blood glucose reading",    "reading",             "daily",    "morning"),
            ("Evening glucose check",    "reading",             "daily",    "evening"),
            ("Low-carb meal tracking",   "diet",                "daily",    "afternoon"),
        ]
        for title, task_type, freq, time_of_day in tasks:
            db.session.add(CarePlanTask(
                care_plan_id=cp.id,
                title=title,
                type=task_type,
                frequency=freq,
                time_of_day=time_of_day,
                status="pending",
            ))

        db.session.commit()
        logger.info("  ✅ Care Plan created for John (6 tasks)")
    except Exception as exc:
        db.session.rollback()
        logger.error("  ❌ Failed care plan: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 9 – Medical Reports (one per patient)
# ─────────────────────────────────────────────────────────────────────────────

REPORT_DETAILS = {
    "John":   ("Annual Diabetes Panel",         "John Doe — HbA1c: 8.2%, Fasting Glucose: 145 mg/dL"),
    "Priya":  ("Hypertension Blood Work",        "Priya Sharma — BP trend: 138/90 mmHg average"),
    "Rahul":  ("Cardiac Enzyme Panel",           "Rahul Kumar — Troponin: 0.05 ng/mL (borderline elevated)"),
    "Sunita": ("Gestational Diabetes Screening", "Sunita Patel — OGTT result: 155 mg/dL at 1hr"),
    "Amit":   ("Pulmonary Function Test",        "Amit Singh — FEV1: 72% predicted, consistent with mild asthma"),
}

def seed_reports(pat_map: dict, doc_map: dict):
    logger.info(SECTION)
    logger.info("STEP 9 – Seeding Medical Reports …")
    logger.info(SECTION)

    doc_id = doc_map.get("Sharma")

    for pat_key, pat_id in pat_map.items():
        title, summary = REPORT_DETAILS.get(pat_key, (f"{pat_key} Lab Report", ""))
        try:
            db.session.add(MedicalReport(
                patient_id=pat_id,
                doctor_id=doc_id,
                title=title,
                type="LAB_RESULT",
                date=date.today(),
                file_url=None,        # no actual file needed
                summary=summary,
                structured_data={"status": "completed", "seeded": True},
            ))
            db.session.commit()
            logger.info("  ✅ Report: %s — %s", pat_key, title)
        except Exception as exc:
            db.session.rollback()
            logger.error("  ❌ Failed report for '%s': %s", pat_key, exc)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    app = create_app()
    with app.app_context():
        logger.info(SECTION)
        logger.info("  VitalMind — Production Seed Script")
        logger.info(SECTION)

        # 0. Wipe — must succeed before we continue
        wipe_patient_and_doctor_data()

        # 1–2. Roles & Admin (idempotent)
        role_map = seed_roles()
        seed_admin(role_map.get("admin"))

        # 3–4. Doctors & Patients (fresh)
        doc_map = seed_doctors(role_map.get("doctor"))
        pat_map = seed_patients(role_map.get("patient"))

        if not doc_map:
            logger.error("❌ No doctors were created — aborting remaining steps.")
            return
        if not pat_map:
            logger.error("❌ No patients were created — aborting remaining steps.")
            return

        # 5–9. Dependent data
        seed_medications(pat_map, doc_map)
        seed_appointments(pat_map, doc_map)
        seed_vitals(pat_map)
        seed_care_plan(pat_map, doc_map)
        seed_reports(pat_map, doc_map)

        logger.info(SECTION)
        logger.info("🎉  Production seed completed successfully!")
        logger.info(SECTION)
        logger.info("")
        logger.info("  Test Credentials")
        logger.info("  ────────────────────────────────────")
        logger.info("  Admin    : admin@vitalmind.com   / Admin123!")
        logger.info("  Doctor   : dr.sharma@vitalmind.com / Doctor123!")
        logger.info("  Patient  : john@test.com          / Patient123!")
        logger.info("  ────────────────────────────────────")
        logger.info("  Other patients  : priya@test.com, rahul@test.com,")
        logger.info("                    sunita@test.com, amit@test.com")
        logger.info("  Other doctors   : dr.patel, dr.singh, dr.rao, dr.mehta")
        logger.info("  All passwords   : Doctor123! / Patient123!")
        logger.info(SECTION)


if __name__ == "__main__":
    main()
