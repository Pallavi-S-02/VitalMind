from datetime import datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import db

class SymptomSession(db.Model):
    __tablename__ = 'symptom_sessions'
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('patient_profiles.id'), nullable=False)
    
    start_time: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    end_time: Mapped[datetime] = mapped_column(db.DateTime, nullable=True)
    status: Mapped[str] = mapped_column(db.String(20), default="active") # active, completed, abandoned
    
    # AI generated summaries and assessments
    chief_complaint: Mapped[str] = mapped_column(db.Text, nullable=True)
    structured_symptoms: Mapped[dict] = mapped_column(JSONB, nullable=True) # E.g., {"headache": {"severity": 8, "duration": "2 days"}}
    ai_assessment: Mapped[str] = mapped_column(db.Text, nullable=True)
    triage_level: Mapped[str] = mapped_column(db.String(50), nullable=True) # emergency, urgent, routine, self-care
    recommended_action: Mapped[str] = mapped_column(db.Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    patient = relationship("PatientProfile", backref="symptom_sessions")
    
    # A session has many conversation logs
    # conversation_logs = relationship("ConversationLog", back_populates="session")
