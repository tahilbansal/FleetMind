from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base, uuid_pk

class GPSPing(Base):
    """
    Every GPS update from every vehicle.
    """
    __tablename__ = "gps_pings"
    __table_args__ = (
        Index("ix_gps_pings_vehicle_time", "vehicle_id", "recorded_at"),
        Index("ix_gps_pings_plan",         "route_plan_id"),
    )

    id             = uuid_pk()
    vehicle_id     = Column(String(36), ForeignKey("vehicles.id"),    nullable=False)
    route_plan_id  = Column(String(36), ForeignKey("route_plans.id"), nullable=True)

    lat            = Column(Float, nullable=False)
    lon            = Column(Float, nullable=False)
    speed_kmh      = Column(Float, default=0.0)
    heading_deg    = Column(Float)

    geofence_status = Column(String(32))
    nearest_stop_id = Column(String(36), ForeignKey("stops.id"), nullable=True)
    recorded_at    = Column(DateTime, nullable=False, default=func.now())

    vehicle    = relationship("Vehicle",    back_populates="gps_pings")
    route_plan = relationship("RoutePlan",  back_populates="gps_pings")