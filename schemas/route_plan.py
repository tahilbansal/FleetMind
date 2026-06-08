from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import date, datetime
from models.enums import RoutePlanStatus

class RouteLegResponse(BaseModel):
    stop_id: str
    sequence_order: int
    planned_eta_minutes: int
    status: str
    actual_arrived_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class RoutePlanBase(BaseModel):
    depot_id: str
    plan_date: date
    num_vehicles: int
    num_stops: int
    is_sandbox: bool = False

class RoutePlanCreate(RoutePlanBase):
    stop_ids: List[str]
    vehicle_ids: List[str]

class RoutePlanResponse(RoutePlanBase):
    id: str
    status: RoutePlanStatus
    total_distance_km: Optional[float] = None
    cost_optimized: Optional[float] = None
    cost_savings: Optional[float] = None
    routes_json: Optional[Dict] = None

    class Config:
        from_attributes = True

class ScenarioComparison(BaseModel):
    baseline_id: str
    sandbox_id: str
    distance_delta_km: float
    cost_delta: float
    savings_pct: float
    is_better: bool