from datetime import datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import db

class Appointment(db.Model):
    __tablename__ = 'appointments'
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('patient_profiles.id'), nullable=False)
    doctor_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('doctor_profiles.id'), nullable=False)
    
    start_time: Mapped[datetime] = mapped_column(db.DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(db.DateTime, nullable=False)
    
    status: Mapped[str] = mapped_column(db.String(20), default="scheduled") # scheduled, completed, cancelled, no-show
    type: Mapped[str] = mapped_column(db.String(20), default="in-person") # in-person, video, voice
    
    reason: Mapped[str] = mapped_column(db.Text, nullable=True)
    notes: Mapped[str] = mapped_column(db.Text, nullable=True)
    
    # Telemedicine details
    meeting_link: Mapped[str] = mapped_column(db.String(255), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    patient = relationship("PatientProfile", backref="appointments")
    doctor = relationship("DoctorProfile", backref="appointments")
