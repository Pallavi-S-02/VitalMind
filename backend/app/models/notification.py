from datetime import datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import db

class Notification(db.Model):
    __tablename__ = 'notifications'
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    
    title: Mapped[str] = mapped_column(db.String(255), nullable=False)
    body: Mapped[str] = mapped_column(db.Text, nullable=False)
    type: Mapped[str] = mapped_column(db.String(50), nullable=False) # appointment_reminder, medication_reminder, system_alert
    
    # Store dynamic action links or data
    action_data: Mapped[dict] = mapped_column(JSONB, nullable=True)
    
    is_read: Mapped[bool] = mapped_column(db.Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    
    user = relationship("User", backref="notifications")
