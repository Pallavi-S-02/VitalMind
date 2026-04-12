from datetime import datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import db

class ConversationLog(db.Model):
    __tablename__ = 'conversation_logs'
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('patient_profiles.id'), nullable=False)
    session_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('symptom_sessions.id'), nullable=True) # Optional, could be general chat
    
    # Store complete chat history as JSON array
    messages: Mapped[list] = mapped_column(JSONB, default=list) # e.g., [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    
    # Metadata about the conversation
    context_type: Mapped[str] = mapped_column(db.String(50), default="general") # symptom_checker, general_query, report_analysis
    
    start_time: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    end_time: Mapped[datetime] = mapped_column(db.DateTime, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    patient = relationship("PatientProfile", backref="conversations")
    session = relationship("SymptomSession", backref="conversation_logs")
