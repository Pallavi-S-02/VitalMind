import sys
import logging
from app.models.db import db
from app.models.patient import PatientProfile
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
        print("Before:", p.blood_type, p.date_of_birth)
        new_data = {"blood_type": "O-", "date_of_birth": "1990-12-12"}
        PatientService.update_patient_profile(p.id, new_data)
        
        # Verify
        db.session.expire_all()
        p_check = PatientProfile.query.get(p.id)
        print("After:", p_check.blood_type, p_check.date_of_birth)
