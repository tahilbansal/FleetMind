# solver/data_model.py
from typing import List
from api.schemas.vrp import Stop, RouteState

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