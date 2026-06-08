from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Enum as SAEnum, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base, uuid_pk
from .enums import VehicleStatus, VehicleCategory

class VehicleType(Base):
    """
    Template for vehicle capabilities. Decouples specs from individual vehicles.
    """
    __tablename__ = "vehicle_types"

    id               = uuid_pk()
    name             = Column(String(64), nullable=False, unique=True)
    category         = Column(SAEnum(VehicleCategory), nullable=False)
    capacity_kg      = Column(Float, nullable=False)     # max payload weight
    capacity_m3      = Column(Float, nullable=False)     # max payload volume
    fuel_cost_per_km = Column(Float, nullable=False)     # ₹ per km
    max_range_km     = Column(Float, default=500.0)      # max daily range
    avg_speed_kmh    = Column(Integer, default=40)       # for ETA calculations
    is_refrigerated  = Column(Boolean, default=False)
    co2_per_km       = Column(Float, default=0.21)       # kg CO2, for sustainability report
    created_at       = Column(DateTime, default=func.now())

    # Relationships
    vehicles = relationship("Vehicle", back_populates="vehicle_type")

    def __repr__(self):
        return f"<VehicleType {self.name} ({self.capacity_kg}kg)>"

class Vehicle(Base):
    """
    A physical vehicle. Belongs to one depot, has one type.
    Live position updated via GPS pings.
    """
    __tablename__ = "vehicles"
    __table_args__ = (
        Index("ix_vehicles_depot", "depot_id"),
        Index("ix_vehicles_status", "status"),
    )

    id              = uuid_pk()
    depot_id        = Column(String(36), ForeignKey("depots.id"), nullable=False)
    vehicle_type_id = Column(String(36), ForeignKey("vehicle_types.id"), nullable=False)
    plate_number    = Column(String(20), unique=True, nullable=False)
    status          = Column(SAEnum(VehicleStatus), default=VehicleStatus.AVAILABLE)

    # Live GPS state (updated from GPS ping stream)
    current_lat     = Column(Float)
    current_lon     = Column(Float)
    current_speed   = Column(Float, default=0.0)
    last_seen_at    = Column(DateTime)

    # Load state
    load_current_kg = Column(Float, default=0.0)

    # Metadata
    year_of_manufacture = Column(Integer)
    created_at      = Column(DateTime, default=func.now())
    updated_at      = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    depot        = relationship("Depot",       back_populates="vehicles")
    vehicle_type = relationship("VehicleType", back_populates="vehicles")
    driver       = relationship("Driver",      back_populates="vehicle", uselist=False)
    gps_pings    = relationship("GPSPing",     back_populates="vehicle")
    route_legs   = relationship("RouteLeg",    back_populates="vehicle")

    def __repr__(self):
        return f"<Vehicle {self.plate_number} @ {self.depot_id}>"