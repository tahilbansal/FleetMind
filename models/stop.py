from sqlalchemy import Column, String, Float, Integer, DateTime, Enum as SAEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base, uuid_pk
from .enums import StopPriority

class Stop(Base):
    """
    A delivery or pickup location. Reusable across route plans.
    """
    __tablename__ = "stops"

    id              = uuid_pk()
    name            = Column(String(128), nullable=False)
    lat             = Column(Float, nullable=False)
    lon             = Column(Float, nullable=False)
    address         = Column(String(256))
    city            = Column(String(64))

    # VRP constraint fields
    demand_kg       = Column(Float, default=0.0)
    demand_m3       = Column(Float, default=0.0)
    time_window_start = Column(Integer, default=480)   # minutes from midnight
    time_window_end   = Column(Integer, default=1080)
    service_time_min  = Column(Integer, default=10)    # unload time at stop
    priority          = Column(SAEnum(StopPriority), default=StopPriority.MEDIUM)

    # Geofence for arrival detection
    geofence_radius_m = Column(Integer, default=200)

    # Contact
    contact_name  = Column(String(64))
    contact_phone = Column(String(20))

    created_at = Column(DateTime, default=func.now())

    # Relationships
    route_legs = relationship("RouteLeg", back_populates="stop")