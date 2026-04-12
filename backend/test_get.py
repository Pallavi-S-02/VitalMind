import sys
from app.models.db import db
from app.models.patient import PatientProfile
from flask import Flask
app = Flask(__name__)
from dotenv import load_dotenv
load_dotenv()
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres:postgres@localhost:5432/medassist"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    p = PatientProfile.query.get('d8dcf382-5ba2-4c6f-a7f5-fc9362ef9a77')
    print("to_dict():", p.to_dict())
