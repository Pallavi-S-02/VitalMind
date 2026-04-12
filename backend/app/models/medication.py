from datetime import date, datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import db

class Medication(db.Model):
    __tablename__ = 'medications'
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    description: Mapped[str] = mapped_column(db.Text, nullable=True)
    side_effects: Mapped[str] = mapped_column(db.Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    prescriptions = relationship("Prescription", back_populates="medication")

    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'description': self.description,
            'side_effects': self.side_effects,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Prescription(db.Model):
    __tablename__ = 'prescriptions'
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('patient_profiles.id'), nullable=False)
    doctor_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('doctor_profiles.id'), nullable=False)
    medication_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('medications.id'), nullable=False)
    
    dosage: Mapped[str] = mapped_column(db.String(100), nullable=False)
    frequency: Mapped[str] = mapped_column(db.String(100), nullable=False)
    route: Mapped[str] = mapped_column(db.String(50), nullable=True) # oral, intravenous, etc.
    
    start_date: Mapped[date] = mapped_column(db.Date, nullable=False)
    end_date: Mapped[date] = mapped_column(db.Date, nullable=True)
    
    instructions: Mapped[str] = mapped_column(db.Text, nullable=True)
    status: Mapped[str] = mapped_column(db.String(20), default="active") # active, completed, discontinued
    
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    patient = relationship("PatientProfile", backref="prescriptions")
    doctor = relationship("DoctorProfile", backref="prescriptions")
    medication = relationship("Medication", back_populates="prescriptions")

    def to_dict(self):
        return {
            'id': str(self.id),
            'patient_id': str(self.patient_id),
            'doctor_id': str(self.doctor_id),
            'medication_id': str(self.medication_id),
            'medication_name': self.medication.name if self.medication else "Unknown",
            'dosage': self.dosage,
            'frequency': self.frequency,
            'route': self.route,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'instructions': self.instructions,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
