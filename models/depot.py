from sqlalchemy import Column, String, Float, Integer, DateTime, Enum as SAEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base, uuid_pk
from .enums import DepotStatus

class Depot(Base):
    """
    A warehouse or distribution center that vehicles operate from.
    Multi-depot VRP: each route plan can span multiple depots.
    """
    __tablename__ = "depots"

    id                = uuid_pk()
    name              = Column(String(128), nullable=False)
    lat               = Column(Float, nullable=False)
    lon               = Column(Float, nullable=False)
    address           = Column(String(256))
    city              = Column(String(64))
    state             = Column(String(64))
    country           = Column(String(64), default="India")
    capacity_vehicles = Column(Integer, default=20)       # max vehicles housed
    status            = Column(SAEnum(DepotStatus), default=DepotStatus.ACTIVE)
    operating_hours_start = Column(Integer, default=360)  # minutes from midnight (6am)
    operating_hours_end   = Column(Integer, default=1200) # (8pm)
    created_at        = Column(DateTime, default=func.now())
    updated_at        = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    vehicles     = relationship("Vehicle",    back_populates="depot")
    route_plans  = relationship("RoutePlan",  back_populates="depot")
    cost_config  = relationship("CostConfig", back_populates="depot", uselist=False)

    def __repr__(self):
        return f"<Depot {self.name} ({self.city})>"