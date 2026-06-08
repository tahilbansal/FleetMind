from sqlalchemy import Column, String, Float, Integer, DateTime, Enum as SAEnum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base, uuid_pk
from .enums import DriverStatus

class Driver(Base):
    """
    A driver assigned to one vehicle at a time.
    """
    __tablename__ = "drivers"

    id             = uuid_pk()
    vehicle_id     = Column(String(36), ForeignKey("vehicles.id"), nullable=True)
    name           = Column(String(128), nullable=False)
    phone          = Column(String(20))
    email          = Column(String(128))
    status         = Column(SAEnum(DriverStatus), default=DriverStatus.AVAILABLE)

    # Shift constraints (minutes from midnight)
    shift_start_min = Column(Integer, default=480)   # 8:00 AM
    shift_end_min   = Column(Integer, default=1080)  # 6:00 PM
    break_duration_min = Column(Integer, default=30)

    # AI-computed rolling score (0–100)
    behavior_score  = Column(Float, default=80.0)

    # Metadata
    joined_at      = Column(DateTime, default=func.now())
    created_at     = Column(DateTime, default=func.now())
    updated_at     = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    vehicle         = relationship("Vehicle",            back_populates="driver")
    behavior_logs   = relationship("DriverBehaviorLog",  back_populates="driver")

    def __repr__(self):
        return f"<Driver {self.name} score={self.behavior_score}>"