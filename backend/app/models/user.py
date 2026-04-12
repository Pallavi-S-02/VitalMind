from datetime import datetime
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import db

class Role(db.Model):
    __tablename__ = 'roles'
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(db.String(50), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(db.String(255), nullable=True)
    permissions: Mapped[dict] = mapped_column(JSONB, default=list) # List of permission strings
    
    users = relationship("User", back_populates="role")

class User(db.Model):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(db.String(120), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(db.String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(db.String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(db.String(50), nullable=False)
    phone_number: Mapped[str] = mapped_column(db.String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(db.Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(db.Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    role_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('roles.id'), nullable=False)
    
    role = relationship("Role", back_populates="users")
    
    # Relationships to profiles
    patient_profile = relationship("PatientProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    doctor_profile = relationship("DoctorProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
