from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Enum as SAEnum, JSON, Text
from datetime import datetime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base, uuid_pk
from .enums import DisruptionType, DisruptionSource

class DisruptionEvent(Base):
    __tablename__ = "disruption_events"

    id             = uuid_pk()
    route_plan_id  = Column(String(36), ForeignKey("route_plans.id"), nullable=False)

    source         = Column(SAEnum(DisruptionSource), nullable=False)
    disruption_type = Column(SAEnum(DisruptionType), nullable=False)

    description    = Column(String)   # NL input context
    raw_input      = Column(Text)
    structured_event = Column(JSON)

    distance_before_km = Column(Float)
    distance_after_km = Column(Float)
    cost_before    = Column(Float)
    cost_after     = Column(Float)
    replan_time_ms = Column(Float)

    resolution     = Column(String(64))
    new_plan_id    = Column(String(36), ForeignKey("route_plans.id"), nullable=True)
    timestamp      = Column(DateTime, default=func.now())

    route_plan = relationship("RoutePlan", back_populates="disruption_events", foreign_keys=[route_plan_id])