from pydantic import BaseModel
from typing import List, Dict, Optional

class Stop(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    demand_kg: float
    time_window: Optional[tuple[int, int]] = None  # (earliest, latest) in minutes from depot

class RouteState(BaseModel):
    stops: List[Stop]
    num_vehicles: int
    vehicle_capacities: List[int]
    depot_ids: List[str] = []  # Length must match num_vehicles
    # Tracks which stops are assigned to which drivers
    assignments: Dict[str, List[str]] = {}  # {driver_id: [stop_ids]}
    # Drivers marked as unavailable
    unavailable_drivers: List[str] = []
    # Blocked roads as (from_stop_id, to_stop_id) pairs
    blocked_edges: List[tuple[int, int]] = []