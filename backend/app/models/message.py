from datetime import datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import db

class DirectConversation(db.Model):
    __tablename__ = 'direct_conversations'
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('patient_profiles.id'), nullable=False)
    doctor_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('doctor_profiles.id'), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    patient = relationship("PatientProfile", backref="direct_conversations")
    doctor = relationship("DoctorProfile", backref="direct_conversations")
    messages = relationship("DirectMessage", back_populates="conversation", order_by="DirectMessage.created_at", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': str(self.id),
            'patient_id': str(self.patient_id),
            'doctor_id': str(self.doctor_id),
            'doctor_name': f"Dr. {self.doctor.user.first_name} {self.doctor.user.last_name}" if self.doctor and self.doctor.user else "Unknown Doctor",
            'patient_name': f"{self.patient.user.first_name} {self.patient.user.last_name}" if self.patient and self.patient.user else "Unknown Patient",
            'last_message': self.messages[-1].content if self.messages else None,
            'last_message_at': self.messages[-1].created_at.isoformat() if self.messages else self.updated_at.isoformat(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class DirectMessage(db.Model):
    __tablename__ = 'direct_messages'
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('direct_conversations.id'), nullable=False)
    sender_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    content: Mapped[str] = mapped_column(db.Text, nullable=False)
    
    is_read: Mapped[bool] = mapped_column(db.Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    
    conversation = relationship("DirectConversation", back_populates="messages")
    sender = relationship("User")

    def to_dict(self):
        return {
            'id': str(self.id),
            'conversation_id': str(self.conversation_id),
            'sender_id': str(self.sender_id),
            'sender_name': self.sender.full_name if self.sender else "Unknown",
            'content': self.content,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat()
        }
