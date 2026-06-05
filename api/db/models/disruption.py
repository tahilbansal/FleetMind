from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from ..base import Base

class DisruptionEvent(Base):
    __tablename__ = "disruption_events"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    description = Column(String)   # NL input context
    disruption_type = Column(String)
    distance_before_km = Column(Float)
    distance_after_km = Column(Float)
    replan_time_ms = Column(Float)