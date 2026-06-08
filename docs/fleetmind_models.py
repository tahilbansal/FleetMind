"""
FleetMind — Complete Domain Models & Database Schema
=====================================================
SQLAlchemy models for all tables.
Swap DATABASE_URL env var to switch SQLite ↔ PostgreSQL with zero code changes.

  SQLite  (dev):  DATABASE_URL=sqlite:///./fleetmind.db
  Postgres (prod): DATABASE_URL=postgresql://user:pass@host/fleetmind
"""

import uuid
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    create_engine, Column, String, Float, Integer, Boolean,
    DateTime, Date, Text, JSON, ForeignKey, Enum as SAEnum,
    UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.sql import func
import os

# ---------------------------------------------------------------------------
# Engine — swap via env var, zero code change
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./fleetmind.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ---------------------------------------------------------------------------
# Helper — UUID primary key that works on both SQLite and PostgreSQL
# ---------------------------------------------------------------------------
def uuid_pk():
    return Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class DepotStatus(str, enum.Enum):
    ACTIVE   = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"

class VehicleStatus(str, enum.Enum):
    AVAILABLE  = "available"
    EN_ROUTE   = "en_route"
    LOADING    = "loading"
    MAINTENANCE = "maintenance"
    OFFLINE    = "offline"

class DriverStatus(str, enum.Enum):
    AVAILABLE = "available"
    ON_DUTY   = "on_duty"
    OFF_DUTY  = "off_duty"
    SICK      = "sick"

class RoutePlanStatus(str, enum.Enum):
    DRAFT      = "draft"
    OPTIMIZING = "optimizing"
    ACTIVE     = "active"
    COMPLETED  = "completed"
    CANCELLED  = "cancelled"

class StopPriority(str, enum.Enum):
    HIGH   = "high"    # must be served today
    MEDIUM = "medium"  # default
    LOW    = "low"     # can slip to next day

class DisruptionType(str, enum.Enum):
    DRIVER_UNAVAILABLE = "driver_unavailable"
    ROAD_BLOCKED       = "road_blocked"
    WEATHER_ALERT      = "weather_alert"
    VEHICLE_BREAKDOWN  = "vehicle_breakdown"
    STOP_CANCELLED     = "stop_cancelled"
    TRAFFIC_DELAY      = "traffic_delay"

class DisruptionSource(str, enum.Enum):
    DISPATCHER_NL  = "dispatcher_nl"   # typed by human
    AI_MONITOR     = "ai_monitor"      # detected by disruption monitor agent
    WEBHOOK        = "webhook"         # pushed by external system

class VehicleCategory(str, enum.Enum):
    SMALL_VAN    = "small_van"
    LARGE_VAN    = "large_van"
    TRUCK_7T     = "truck_7t"
    TRUCK_15T    = "truck_15t"
    REFRIGERATED = "refrigerated"
    MOTORCYCLE   = "motorcycle"   # last-mile small packages


# ---------------------------------------------------------------------------
# 1. DEPOTS
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# 2. VEHICLE TYPES  — defines capabilities, not individual vehicles
# ---------------------------------------------------------------------------
class VehicleType(Base):
    """
    Template for vehicle capabilities. Decouples specs from individual vehicles.
    New vehicle types (e.g. EV truck) added here without schema change.
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


# ---------------------------------------------------------------------------
# 3. VEHICLES — individual trucks/vans assigned to depots
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# 4. DRIVERS
# ---------------------------------------------------------------------------
class Driver(Base):
    """
    A driver assigned to one vehicle at a time.
    Behavior score is updated daily by the AI scorer.
    """
    __tablename__ = "drivers"

    id             = uuid_pk()
    vehicle_id     = Column(String(36), ForeignKey("vehicles.id"), nullable=True)
    name           = Column(String(128), nullable=False)
    phone          = Column(String(20))
    email          = Column(String(128))
    status         = Column(SAEnum(DriverStatus), default=DriverStatus.AVAILABLE)

    # Shift constraints (minutes from midnight)
    shift_start_min = Column(Integer, default=480)   # 8:00 AM
    shift_end_min   = Column(Integer, default=1080)  # 6:00 PM
    break_duration_min = Column(Integer, default=30)

    # AI-computed rolling score (0–100)
    behavior_score  = Column(Float, default=80.0)

    # Metadata
    joined_at      = Column(DateTime, default=func.now())
    created_at     = Column(DateTime, default=func.now())
    updated_at     = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    vehicle         = relationship("Vehicle",            back_populates="driver")
    behavior_logs   = relationship("DriverBehaviorLog",  back_populates="driver")

    def __repr__(self):
        return f"<Driver {self.name} score={self.behavior_score}>"


# ---------------------------------------------------------------------------
# 5. STOPS — delivery/pickup locations
# ---------------------------------------------------------------------------
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

    def __repr__(self):
        return f"<Stop {self.name} demand={self.demand_kg}kg>"


# ---------------------------------------------------------------------------
# 6. ROUTE PLANS — one optimization run
# ---------------------------------------------------------------------------
class RoutePlan(Base):
    """
    A solved VRP instance. is_sandbox=True means what-if scenario,
    never affects live routes.
    """
    __tablename__ = "route_plans"
    __table_args__ = (
        Index("ix_route_plans_depot_date", "depot_id", "plan_date"),
        Index("ix_route_plans_status", "status"),
    )

    id           = uuid_pk()
    depot_id     = Column(String(36), ForeignKey("depots.id"), nullable=False)
    status       = Column(SAEnum(RoutePlanStatus), default=RoutePlanStatus.DRAFT)
    plan_date    = Column(Date, nullable=False)

    # Solver inputs
    num_vehicles = Column(Integer, nullable=False)
    num_stops    = Column(Integer, nullable=False)

    # Solver outputs
    total_distance_km   = Column(Float)
    total_duration_min  = Column(Float)
    solve_time_ms       = Column(Float)

    # Cost engine outputs
    cost_optimized   = Column(Float)    # ₹ cost of this plan
    cost_baseline    = Column(Float)    # ₹ if routes were unoptimized
    cost_savings     = Column(Float)    # baseline - optimized

    # Full routes stored as JSON for fast retrieval without joining
    routes_json = Column(JSON)

    # What-if flag — sandbox plans never become active
    is_sandbox  = Column(Boolean, default=False)

    # If this plan was created from a disruption replan, ref to parent
    parent_plan_id = Column(String(36), ForeignKey("route_plans.id"), nullable=True)

    created_at = Column(DateTime, default=func.now())
    activated_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Relationships
    depot              = relationship("Depot",             back_populates="route_plans")
    route_legs         = relationship("RouteLeg",          back_populates="route_plan")
    disruption_events  = relationship("DisruptionEvent",   back_populates="route_plan")
    gps_pings          = relationship("GPSPing",           back_populates="route_plan")
    behavior_logs      = relationship("DriverBehaviorLog", back_populates="route_plan")
    child_plans        = relationship("RoutePlan",         backref="parent", remote_side="RoutePlan.id", foreign_keys=[parent_plan_id])

    def __repr__(self):
        return f"<RoutePlan {self.plan_date} depot={self.depot_id} status={self.status}>"


# ---------------------------------------------------------------------------
# 7. ROUTE LEGS — individual stop assignments within a plan
# ---------------------------------------------------------------------------
class RouteLeg(Base):
    """
    One stop visit within a route plan. sequence_order defines drive order.
    """
    __tablename__ = "route_legs"
    __table_args__ = (
        Index("ix_route_legs_plan_vehicle", "route_plan_id", "vehicle_id"),
    )

    id             = uuid_pk()
    route_plan_id  = Column(String(36), ForeignKey("route_plans.id"), nullable=False)
    vehicle_id     = Column(String(36), ForeignKey("vehicles.id"),    nullable=False)
    stop_id        = Column(String(36), ForeignKey("stops.id"),       nullable=False)
    sequence_order = Column(Integer, nullable=False)  # 0 = depot start, N+1 = depot return

    # Planned values (from solver)
    planned_distance_km  = Column(Float)
    planned_eta_minutes  = Column(Integer)  # minutes from plan start

    # Actual values (filled in real-time)
    actual_arrived_at   = Column(DateTime)
    actual_departed_at  = Column(DateTime)
    actual_dwell_min    = Column(Float)     # actual time spent at stop

    # Status
    status = Column(String(32), default="pending")  # pending/arrived/completed/skipped

    # Relationships
    route_plan = relationship("RoutePlan", back_populates="route_legs")
    vehicle    = relationship("Vehicle",   back_populates="route_legs")
    stop       = relationship("Stop",      back_populates="route_legs")

    def __repr__(self):
        return f"<RouteLeg plan={self.route_plan_id} seq={self.sequence_order}>"


# ---------------------------------------------------------------------------
# 8. DISRUPTION EVENTS
# ---------------------------------------------------------------------------
class DisruptionEvent(Base):
    """
    Every disruption — typed by dispatcher or detected by AI monitor.
    Stores raw input, structured event, and replan outcome.
    """
    __tablename__ = "disruption_events"

    id             = uuid_pk()
    route_plan_id  = Column(String(36), ForeignKey("route_plans.id"), nullable=False)

    source         = Column(SAEnum(DisruptionSource), nullable=False)
    disruption_type = Column(SAEnum(DisruptionType), nullable=False)

    # Raw input (NL text from dispatcher, or weather alert JSON)
    raw_input      = Column(Text)

    # LLM-structured event payload
    structured_event = Column(JSON)  # {driver_id, stop_ids, edge, etc.}

    # Impact metrics
    dist_before_km = Column(Float)
    dist_after_km  = Column(Float)
    cost_before    = Column(Float)
    cost_after     = Column(Float)
    replan_ms      = Column(Float)

    # How it was resolved
    resolution     = Column(String(64))  # replanned / dismissed / manual
    new_plan_id    = Column(String(36), ForeignKey("route_plans.id"), nullable=True)

    occurred_at    = Column(DateTime, default=func.now())

    # Relationships
    route_plan = relationship("RoutePlan", back_populates="disruption_events",
                              foreign_keys=[route_plan_id])

    def __repr__(self):
        return f"<Disruption {self.disruption_type} @ {self.occurred_at}>"


# ---------------------------------------------------------------------------
# 9. GPS PINGS — raw position stream
# ---------------------------------------------------------------------------
class GPSPing(Base):
    """
    Every GPS update from every vehicle. High-volume table.
    In production: partition by recorded_at date.
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
    heading_deg    = Column(Float)              # 0–360 compass bearing

    # Geofence result at this ping
    geofence_status = Column(String(32))        # none / approaching / inside / departed
    nearest_stop_id = Column(String(36), ForeignKey("stops.id"), nullable=True)

    recorded_at    = Column(DateTime, nullable=False, default=func.now())

    # Relationships
    vehicle    = relationship("Vehicle",    back_populates="gps_pings")
    route_plan = relationship("RoutePlan",  back_populates="gps_pings")

    def __repr__(self):
        return f"<GPSPing vehicle={self.vehicle_id} {self.lat},{self.lon}>"


# ---------------------------------------------------------------------------
# 10. DRIVER BEHAVIOR LOGS — daily AI-scored report per driver
# ---------------------------------------------------------------------------
class DriverBehaviorLog(Base):
    """
    One record per driver per day. Computed by the behavior scorer agent.
    llm_report is the natural language summary.
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
    avg_dwell_min         = Column(Float)       # average time at each stop
    target_dwell_min      = Column(Float)       # from stop.service_time_min
    route_adherence_pct   = Column(Float)       # % of pings on planned route
    speed_compliance_pct  = Column(Float)       # % of pings within speed limit
    total_distance_km     = Column(Float)
    total_duration_min    = Column(Float)

    # Composite AI score (0–100)
    behavior_score = Column(Float)

    # LLM-generated natural language report
    llm_report     = Column(Text)

    created_at = Column(DateTime, default=func.now())

    # Relationships
    driver     = relationship("Driver",     back_populates="behavior_logs")
    route_plan = relationship("RoutePlan",  back_populates="behavior_logs")

    def __repr__(self):
        return f"<BehaviorLog driver={self.driver_id} date={self.log_date} score={self.behavior_score}>"


# ---------------------------------------------------------------------------
# 11. COST CONFIGS — per-depot configurable cost model
# ---------------------------------------------------------------------------
class CostConfig(Base):
    """
    Cost parameters per depot. Operations manager can update without code change.
    """
    __tablename__ = "cost_configs"
    __table_args__ = (
        UniqueConstraint("depot_id", name="uq_cost_config_depot"),
    )

    id                    = uuid_pk()
    depot_id              = Column(String(36), ForeignKey("depots.id"), nullable=False)
    fuel_cost_per_km      = Column(Float, default=8.5)    # ₹ per km
    driver_cost_per_hr    = Column(Float, default=150.0)  # ₹ per hour
    vehicle_fixed_per_day = Column(Float, default=500.0)  # ₹ depreciation + insurance
    stockout_penalty      = Column(Float, default=2000.0) # ₹ per missed stop
    is_active             = Column(Boolean, default=True)
    updated_at            = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationship
    depot = relationship("Depot", back_populates="cost_config")

    def __repr__(self):
        return f"<CostConfig depot={self.depot_id} fuel=₹{self.fuel_cost_per_km}/km>"


# ---------------------------------------------------------------------------
# Create all tables
# ---------------------------------------------------------------------------
def init_db():
    Base.metadata.create_all(bind=engine)
    print("FleetMind database initialized.")


# ---------------------------------------------------------------------------
# Dependency for FastAPI
# ---------------------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
