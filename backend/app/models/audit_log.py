from datetime import datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import db

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=True) # Optional, could be system action
    
    action: Mapped[str] = mapped_column(db.String(100), nullable=False) # e.g., viewed_report, updated_medication, login
    entity_type: Mapped[str] = mapped_column(db.String(50), nullable=True) # e.g., medical_report, patient_profile
    entity_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=True)
    
    # Store old and new values for changes, or metadata about the action
    details: Mapped[dict] = mapped_column(JSONB, nullable=True)
    
    ip_address: Mapped[str] = mapped_column(db.String(45), nullable=True)
    user_agent: Mapped[str] = mapped_column(db.String(255), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    
    user = relationship("User", backref="audit_logs")
