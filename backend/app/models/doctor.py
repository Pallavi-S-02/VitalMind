from datetime import datetime, time
import uuid
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import db

class DoctorProfile(db.Model):
    __tablename__ = 'doctor_profiles'
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('users.id'), unique=True, nullable=False)
    
    specialization: Mapped[str] = mapped_column(db.String(100), nullable=False)
    license_number: Mapped[str] = mapped_column(db.String(100), nullable=False, unique=True)
    bio: Mapped[str] = mapped_column(db.Text, nullable=True)
    consultation_fee: Mapped[float] = mapped_column(db.Float, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="doctor_profile")
    availability = relationship("DoctorAvailability", back_populates="doctor", cascade="all, delete-orphan")
    
    # Other relationships will be added as models are created
    # appointments = relationship("Appointment", back_populates="doctor")
    # prescriptions = relationship("Prescription", back_populates="doctor")

    def to_dict(self):
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'first_name': self.user.first_name if self.user else None,
            'last_name': self.user.last_name if self.user else None,
            'email': self.user.email if self.user else None,
            'specialization': self.specialization,
            'license_number': self.license_number,
            'bio': self.bio,
            'consultation_fee': self.consultation_fee
        }

class DoctorAvailability(db.Model):
    __tablename__ = 'doctor_availability'
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doctor_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('doctor_profiles.id'), nullable=False)
    
    day_of_week: Mapped[int] = mapped_column(db.Integer, nullable=False) # 0=Monday, 6=Sunday
    start_time: Mapped[time] = mapped_column(db.Time, nullable=False)
    end_time: Mapped[time] = mapped_column(db.Time, nullable=False)
    is_active: Mapped[bool] = mapped_column(db.Boolean, default=True)
    
    doctor = relationship("DoctorProfile", back_populates="availability")
