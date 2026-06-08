from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey, Enum as SAEnum, Date, Index, Boolean
from datetime import datetime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, backref
from .base import Base, uuid_pk
from .enums import RoutePlanStatus

class RoutePlan(Base):
    """
    A solved VRP instance.
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

    # Full routes stored as JSON
    routes_json = Column(JSON)
    state = Column(JSON)   # The RouteState used

    # What-if flag
    is_sandbox  = Column(Boolean, default=False)
    parent_plan_id = Column(String(36), ForeignKey("route_plans.id"), nullable=True)

    created_at = Column(DateTime, default=func.now())
    activated_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Relationships
    depot              = relationship("Depot",             back_populates="route_plans")
    route_legs         = relationship("RouteLeg",          back_populates="route_plan")
    disruption_events  = relationship(
        "DisruptionEvent", 
        back_populates="route_plan", 
        foreign_keys="[DisruptionEvent.route_plan_id]"
    )
    gps_pings          = relationship("GPSPing",           back_populates="route_plan")
    behavior_logs      = relationship("DriverBehaviorLog", back_populates="route_plan")
    child_plans        = relationship(
        "RoutePlan",
        backref=backref("parent", remote_side="RoutePlan.id"),
        foreign_keys=[parent_plan_id]
    )

class RouteLeg(Base):
    """
    One stop visit within a route plan.
    """
    __tablename__ = "route_legs"
    __table_args__ = (
        Index("ix_route_legs_plan_vehicle", "route_plan_id", "vehicle_id"),
    )

    id             = uuid_pk()
    route_plan_id  = Column(String(36), ForeignKey("route_plans.id"), nullable=False)
    vehicle_id     = Column(String(36), ForeignKey("vehicles.id"),    nullable=False)
    stop_id        = Column(String(36), ForeignKey("stops.id"),       nullable=False)
    sequence_order = Column(Integer, nullable=False)

    # Planned values
    planned_distance_km  = Column(Float)
    planned_eta_minutes  = Column(Integer)

    # Actual values
    actual_arrived_at   = Column(DateTime)
    actual_departed_at  = Column(DateTime)
    actual_dwell_min    = Column(Float)

    status = Column(String(32), default="pending")

    # Relationships
    route_plan = relationship("RoutePlan", back_populates="route_legs")
    vehicle    = relationship("Vehicle",   back_populates="route_legs")
    stop       = relationship("Stop",      back_populates="route_legs")