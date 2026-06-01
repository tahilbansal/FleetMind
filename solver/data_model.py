# solver/data_model.py
from pydantic import BaseModel
from typing import List, Dict, Optional
import numpy as np

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

def build_distance_matrix(stops: List[Stop]) -> List[List[int]]:
    """
    Build a distance matrix from lat/lon coordinates.
    In production, replace with Google Distance Matrix API
    or OSRM (open source) for real road distances.
    For demo: use Haversine formula.
    """
    from math import radians, sin, cos, sqrt, atan2
    n = len(stops)
    matrix = [[0]*n for _ in range(n)]
    
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            lat1, lon1 = radians(stops[i].lat), radians(stops[i].lon)
            lat2, lon2 = radians(stops[j].lat), radians(stops[j].lon)
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            # Earth radius in meters, scale to integers for OR-Tools
            matrix[i][j] = int(6371000 * c)
    
    return matrix