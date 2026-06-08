from sqlalchemy import Column, String, Float, Integer, DateTime, Date, Text, ForeignKey, Index, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base, uuid_pk

class DriverBehaviorLog(Base):
    """
    One record per driver per day. Computed by the behavior scorer agent.
    """
    __tablename__ = "driver_behavior_logs"
    __table_args__ = (
        UniqueConstraint("driver_id", "log_date", name="uq_driver_date"),
        Index("ix_behavior_driver_date", "driver_id", "log_date"),
    )

    id             = uuid_pk()
    driver_id      = Column(String(36), ForeignKey("drivers.id"),     nullable=False)
    route_plan_id  = Column(String(36), ForeignKey("route_plans.id"), nullable=False)
    log_date       = Column(Date, nullable=False)

    # Metrics
    stops_total           = Column(Integer, default=0)
    stops_on_time         = Column(Integer, default=0)
    stops_late            = Column(Integer, default=0)
    stops_skipped         = Column(Integer, default=0)
    avg_dwell_min         = Column(Float)
    target_dwell_min      = Column(Float)
    route_adherence_pct   = Column(Float)
    speed_compliance_pct  = Column(Float)
    total_distance_km     = Column(Float)
    total_duration_min    = Column(Float)

    behavior_score = Column(Float)
    llm_report     = Column(Text)
    created_at = Column(DateTime, default=func.now())

    driver     = relationship("Driver",     back_populates="behavior_logs")
    route_plan = relationship("RoutePlan",  back_populates="behavior_logs")