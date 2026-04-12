from datetime import datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import db

class Alert(db.Model):
    __tablename__ = 'alerts'
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('patient_profiles.id'), nullable=False)
    
    type: Mapped[str] = mapped_column(db.String(50), nullable=False) # abnormal_vital, missed_medication, emergency_symptom
    severity: Mapped[str] = mapped_column(db.String(20), nullable=False) # low, medium, high, critical
    message: Mapped[str] = mapped_column(db.Text, nullable=False)
    
    # Store related IDs (e.g., vital_reading_id, symptom_session_id)
    related_entity_type: Mapped[str] = mapped_column(db.String(50), nullable=True)
    related_entity_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=True)
    
    is_resolved: Mapped[bool] = mapped_column(db.Boolean, default=False)
    resolved_at: Mapped[datetime] = mapped_column(db.DateTime, nullable=True)
    resolved_by: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=True) # Could be doctor or patient
    resolution_notes: Mapped[str] = mapped_column(db.Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    patient = relationship("PatientProfile", backref="alerts")
    resolver = relationship("User", foreign_keys=[resolved_by])
