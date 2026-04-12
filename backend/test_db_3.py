import sys
import logging
from app.models.db import db
from app.models.patient import PatientProfile, MedicalHistory, Allergy
from app.services.patient_service import PatientService
from flask import Flask

logging.basicConfig(level=logging.ERROR, stream=sys.stdout)
app = Flask(__name__)
from dotenv import load_dotenv
load_dotenv()
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres:postgres@localhost:5432/medassist"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    p = PatientProfile.query.first()
    if p:
        new_data = {
            "medical_history": ["Cough", "Cold"],
        }
        res = PatientService.update_patient_profile(p.id, new_data)
        out = res.to_dict()
        print("Immedite return:", out['medical_history'])
