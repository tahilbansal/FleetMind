from sqlalchemy import Column, Integer, String, JSON
from models.base import Base

class FleetConfig(Base):
    __tablename__ = "fleet_configs"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, index=True)
    config = Column(JSON)  # Stores the RouteState payload