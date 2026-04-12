from datetime import date, datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import db

class CarePlan(db.Model):
    __tablename__ = 'care_plans'
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('patient_profiles.id'), nullable=False)
    doctor_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('doctor_profiles.id'), nullable=True) # AI can create initial plans
    
    title: Mapped[str] = mapped_column(db.String(255), nullable=False)
    description: Mapped[str] = mapped_column(db.Text, nullable=True)
    status: Mapped[str] = mapped_column(db.String(20), default="active") # active, completed, cancelled
    
    start_date: Mapped[date] = mapped_column(db.Date, nullable=False, default=date.today)
    end_date: Mapped[date] = mapped_column(db.Date, nullable=True)
    
    # Store goals, milestones, etc.
    goals: Mapped[dict] = mapped_column(JSONB, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    patient = relationship("PatientProfile", backref="care_plans")
    doctor = relationship("DoctorProfile", backref="created_care_plans")
    tasks = relationship("CarePlanTask", back_populates="care_plan", cascade="all, delete-orphan")

class CarePlanTask(db.Model):
    __tablename__ = 'care_plan_tasks'
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    care_plan_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('care_plans.id'), nullable=False)
    
    title: Mapped[str] = mapped_column(db.String(255), nullable=False)
    description: Mapped[str] = mapped_column(db.Text, nullable=True)
    type: Mapped[str] = mapped_column(db.String(50), nullable=False) # exercise, diet, medication_reminder, reading
    
    frequency: Mapped[str] = mapped_column(db.String(100), nullable=True) # daily, weekly, specific days
    time_of_day: Mapped[str] = mapped_column(db.String(50), nullable=True) # morning, afternoon, evening
    
    status: Mapped[str] = mapped_column(db.String(20), default="pending") # pending, completed, skipped
    due_date: Mapped[date] = mapped_column(db.Date, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    care_plan = relationship("CarePlan", back_populates="tasks")
