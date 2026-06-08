from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base, uuid_pk

class CostConfig(Base):
    """
    Cost parameters per depot.
    """
    __tablename__ = "cost_configs"
    __table_args__ = (
        UniqueConstraint("depot_id", name="uq_cost_config_depot"),
    )

    id                    = uuid_pk()
    depot_id              = Column(String(36), ForeignKey("depots.id"), nullable=False)
    fuel_cost_per_km      = Column(Float, default=8.5)
    driver_cost_per_hr    = Column(Float, default=150.0)
    vehicle_fixed_per_day = Column(Float, default=500.0)
    stockout_penalty      = Column(Float, default=2000.0)
    is_active             = Column(Boolean, default=True)
    updated_at            = Column(DateTime, default=func.now(), onupdate=func.now())

    depot = relationship("Depot", back_populates="cost_config")