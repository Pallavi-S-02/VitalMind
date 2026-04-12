from datetime import date, datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import db
from ..utils.encryption import encrypt_phi, decrypt_phi

class PatientProfile(db.Model):
    __tablename__ = 'patient_profiles'
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('users.id'), unique=True, nullable=False)
    
    # Demographics
    date_of_birth: Mapped[date] = mapped_column(db.Date, nullable=True)
    gender: Mapped[str] = mapped_column(db.String(20), nullable=True)
    blood_type: Mapped[str] = mapped_column(db.String(5), nullable=True)
    height_cm: Mapped[float] = mapped_column(db.Float, nullable=True)
    weight_kg: Mapped[float] = mapped_column(db.Float, nullable=True)
    chronic_diseases: Mapped[dict] = mapped_column(JSONB, nullable=True, default=list)
    
    # Emergency Contact
    emergency_contact_name: Mapped[str] = mapped_column(db.String(100), nullable=True)
    emergency_contact_phone: Mapped[str] = mapped_column(db.String(20), nullable=True)
    emergency_contact_relation: Mapped[str] = mapped_column(db.String(50), nullable=True)
    
    # Encrypted PHI Fields
    _ssn_encrypted: Mapped[str] = mapped_column("ssn_encrypted", db.String(255), nullable=True)
    _address_encrypted: Mapped[str] = mapped_column("address_encrypted", db.Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="patient_profile")
    medical_history = relationship("MedicalHistory", back_populates="patient", cascade="all, delete-orphan")
    allergies = relationship("Allergy", back_populates="patient", cascade="all, delete-orphan")
    
    # Other relationships will be added as models are created
    # appointments = relationship("Appointment", back_populates="patient")
    # medications = relationship("Medication", back_populates="patient")
    # reports = relationship("MedicalReport", back_populates="patient")
    # symptom_sessions = relationship("SymptomSession", back_populates="patient")
    # vitals = relationship("VitalsReading", back_populates="patient")
    # devices = relationship("IoTDevice", back_populates="patient")
    # care_plans = relationship("CarePlan", back_populates="patient")
    # conversations = relationship("ConversationLog", back_populates="patient")

    @property
    def ssn(self):
        return decrypt_phi(self._ssn_encrypted) if self._ssn_encrypted else None

    @ssn.setter
    def ssn(self, value):
        self._ssn_encrypted = encrypt_phi(value) if value else None

    @property
    def address(self):
        return decrypt_phi(self._address_encrypted) if self._address_encrypted else None

    @address.setter
    def address(self, value):
        self._address_encrypted = encrypt_phi(value) if value else None
        
    def to_dict(self):
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'first_name': self.user.first_name if self.user else None,
            'last_name': self.user.last_name if self.user else None,
            'email': self.user.email if self.user else None,
            'date_of_birth': self.date_of_birth.isoformat() if self.date_of_birth else None,
            'gender': self.gender,
            'blood_type': self.blood_type,
            'height_cm': self.height_cm,
            'weight_kg': self.weight_kg,
            'chronic_diseases': self.chronic_diseases or [],
            'emergency_contact_name': self.emergency_contact_name,
            'emergency_contact_phone': self.emergency_contact_phone,
            'emergency_contact_relation': self.emergency_contact_relation,
            'medical_history': [mh.condition_name for mh in self.medical_history],
            'allergies': [a.allergen for a in self.allergies]
        }

class MedicalHistory(db.Model):
    __tablename__ = 'medical_history'
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('patient_profiles.id'), nullable=False)
    
    condition_name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    diagnosis_date: Mapped[date] = mapped_column(db.Date, nullable=True)
    status: Mapped[str] = mapped_column(db.String(50), default="active") # active, resolved, managed
    notes: Mapped[str] = mapped_column(db.Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    patient = relationship("PatientProfile", back_populates="medical_history")

class Allergy(db.Model):
    __tablename__ = 'allergies'
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('patient_profiles.id'), nullable=False)
    
    allergen: Mapped[str] = mapped_column(db.String(100), nullable=False)
    reaction: Mapped[str] = mapped_column(db.String(255), nullable=True)
    severity: Mapped[str] = mapped_column(db.String(50), nullable=True) # mild, moderate, severe
    
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    
    patient = relationship("PatientProfile", back_populates="allergies")
# ─────────────────────────────────────────────────────────────────────────────
# Search Indexing Hooks
# ─────────────────────────────────────────────────────────────────────────────

def on_patient_save(mapper, connection, target):
    """Sync patient to ES after commit."""
    from app.services.search_service import SearchService
    # We use a slight delay or background task in production, 
    # but for this dev environment, direct call is fine.
    SearchService.sync_patient(target)

from sqlalchemy import event
event.listen(PatientProfile, "after_insert", on_patient_save)
event.listen(PatientProfile, "after_update", on_patient_save)
