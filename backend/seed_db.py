import os
from app import create_app
from app.models import db, User, PatientProfile, DoctorProfile, Role
from werkzeug.security import generate_password_hash

app = create_app('development')

def seed_data():
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        
        # Check if users already exist
        if User.query.first():
            print("Database already seeded. Skipping.")
            return

        print("Seeding roles...")
        patient_role = Role(name="patient", description="Patient user")
        doctor_role = Role(name="doctor", description="Doctor user")
        db.session.add_all([patient_role, doctor_role])
        db.session.flush()

        print("Seeding users...")
        
        # Create a patient user
        patient_user = User(
            email="patient@example.com",
            password_hash=generate_password_hash("password123"),
            role=patient_role,
            first_name="John",
            last_name="Doe",
            phone_number="+1234567890"
        )
        db.session.add(patient_user)
        db.session.flush() # To get the user ID
        
        # Create a doctor user
        doctor_user = User(
            email="doctor@example.com",
            password_hash=generate_password_hash("password123"),
            role=doctor_role,
            first_name="Jane",
            last_name="Smith",
            phone_number="+0987654321"
        )
        db.session.add(doctor_user)
        db.session.flush()
        
        print("Seeding profiles...")
        
        # Create patient profile
        patient_profile = PatientProfile(
            user_id=patient_user.id,
            date_of_birth="1980-01-01",
            gender="Male",
            blood_type="O+"
        )
        db.session.add(patient_profile)
        
        # Create doctor profile
        doctor_profile = DoctorProfile(
            user_id=doctor_user.id,
            specialization="Cardiology",
            license_number="MD12345",
            bio="Experienced cardiologist with 10 years of practice.",
            consultation_fee=150.0
        )
        db.session.add(doctor_profile)
        
        db.session.commit()
        print("Database seeded successfully!")

if __name__ == '__main__':
    seed_data()
