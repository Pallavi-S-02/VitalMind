from datetime import date, datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import db

class MedicalReport(db.Model):
    __tablename__ = 'medical_reports'
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('patient_profiles.id'), nullable=False)
    doctor_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('doctor_profiles.id'), nullable=True) # Optional, patient could upload themselves
    
    title: Mapped[str] = mapped_column(db.String(255), nullable=False)
    type: Mapped[str] = mapped_column(db.String(50), nullable=False) # lab_result, imaging, clinical_note, etc.
    date: Mapped[date] = mapped_column(db.Date, nullable=False)
    
    file_url: Mapped[str] = mapped_column(db.String(1024), nullable=True) # S3 or local path
    summary: Mapped[str] = mapped_column(db.Text, nullable=True) # AI generated summary
    
    # Structured data extracted from the report
    structured_data: Mapped[dict] = mapped_column(JSONB, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    patient = relationship("PatientProfile", backref="reports")
    doctor = relationship("DoctorProfile", backref="uploaded_reports")
