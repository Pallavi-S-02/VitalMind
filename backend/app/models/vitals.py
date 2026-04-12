from datetime import datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import db

class VitalsReading(db.Model):
    __tablename__ = 'vitals_readings'
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('patient_profiles.id'), nullable=False)
    device_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('iot_devices.id'), nullable=True) # If recorded by a device
    
    timestamp: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Common vitals
    heart_rate: Mapped[int] = mapped_column(db.Integer, nullable=True) # bpm
    blood_pressure_systolic: Mapped[int] = mapped_column(db.Integer, nullable=True) # mmHg
    blood_pressure_diastolic: Mapped[int] = mapped_column(db.Integer, nullable=True) # mmHg
    temperature: Mapped[float] = mapped_column(db.Float, nullable=True) # Celsius
    oxygen_saturation: Mapped[float] = mapped_column(db.Float, nullable=True) # %
    respiratory_rate: Mapped[int] = mapped_column(db.Integer, nullable=True) # breaths/min
    blood_glucose: Mapped[float] = mapped_column(db.Float, nullable=True) # mg/dL
    weight: Mapped[float] = mapped_column(db.Float, nullable=True) # kg
    
    # Store other specific readings
    other_data: Mapped[dict] = mapped_column(JSONB, nullable=True)
    
    # Source: manual_entry, apple_health, fitbit, etc.
    source: Mapped[str] = mapped_column(db.String(50), default="manual_entry")
    
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    
    patient = relationship("PatientProfile", backref="vitals")
    device = relationship("IoTDevice", backref="vitals_readings")
