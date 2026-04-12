import sys
import logging
from app.models.db import db
from app.models.patient import PatientProfile, MedicalHistory, Allergy
from app.services.patient_service import PatientService
from flask import Flask

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
app = Flask(__name__)
from dotenv import load_dotenv
load_dotenv()
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres:postgres@localhost:5432/medassist"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    p = PatientProfile.query.first()
    if p:
        print("Before MH:", [x.condition_name for x in p.medical_history])
        print("Before AL:", [x.allergen for x in p.allergies])
        print("Before CD:", p.chronic_diseases)
        
        new_data = {
            "medical_history": ["Asthma", "Diabetes"],
            "allergies": ["Peanuts"],
            "chronic_diseases": ["Heart Disease"]
        }
        PatientService.update_patient_profile(p.id, new_data)
        
        # Verify
        db.session.expire_all()
        p_check = PatientProfile.query.get(p.id)
        
        print("After MH:", [x.condition_name for x in p_check.medical_history])
        print("After AL:", [x.allergen for x in p_check.allergies])
        print("After CD:", p_check.chronic_diseases)
