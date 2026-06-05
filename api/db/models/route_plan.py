from sqlalchemy import Column, Integer, Float, DateTime, JSON
from datetime import datetime
from ..base import Base

class RoutePlan(Base):
    __tablename__ = "route_plans"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    num_vehicles = Column(Integer)
    num_stops = Column(Integer)
    total_distance_km = Column(Float)
    solve_time_ms = Column(Float)
    routes = Column(JSON)  # The full solution object
    state = Column(JSON)   # The RouteState used to generate this plan