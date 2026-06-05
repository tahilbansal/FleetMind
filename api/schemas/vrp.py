from pydantic import BaseModel
from typing import List, Dict, Optional

class Stop(BaseModel):
    id: int
    name: str
    lat: float
    lon: float
    demand: int           # weight/volume of delivery
    time_window: Optional[tuple] = None  # (earliest, latest) in minutes from depot

class RouteState(BaseModel):
    stops: List[Stop]
    num_vehicles: int
    vehicle_capacities: List[int]
    depot_id: int = 0
    # Tracks which stops are assigned to which drivers
    assignments: Dict[int, List[int]] = {}  # {driver_id: [stop_ids]}
    # Drivers marked as unavailable
    unavailable_drivers: List[int] = []
    # Blocked roads as (from_stop_id, to_stop_id) pairs
    blocked_edges: List[tuple] = []