from datetime import datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import db

class IoTDevice(db.Model):
    __tablename__ = 'iot_devices'
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[str] = mapped_column(UUID(as_uuid=True), db.ForeignKey('patient_profiles.id'), nullable=False)
    
    device_type: Mapped[str] = mapped_column(db.String(100), nullable=False) # e.g., smartwatch, blood_pressure_monitor
    device_identifier: Mapped[str] = mapped_column(db.String(100), nullable=False, unique=True) # MAC address or serial number
    brand: Mapped[str] = mapped_column(db.String(100), nullable=True)
    model: Mapped[str] = mapped_column(db.String(100), nullable=True)
    
    is_active: Mapped[bool] = mapped_column(db.Boolean, default=True)
    last_sync: Mapped[datetime] = mapped_column(db.DateTime, nullable=True)
    
    # Connection details or tokens (should ideally be encrypted if sensitive)
    connection_details: Mapped[dict] = mapped_column(JSONB, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    patient = relationship("PatientProfile", backref="devices")
