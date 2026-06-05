# demo/seed_data.py
import httpx

DALLAS_STOPS = [
    {"id": 0, "name": "Depot — DFW Warehouse", "lat": 32.8998, "lon": -97.0403, "demand": 0},
    {"id": 1, "name": "Walmart Supercenter — Garland", "lat": 32.9127, "lon": -96.6389, "demand": 15},
    {"id": 2, "name": "Target — Plano", "lat": 33.0198, "lon": -96.6989, "demand": 20},
    {"id": 3, "name": "Home Depot — Irving", "lat": 32.8573, "lon": -96.9702, "demand": 25},
    {"id": 4, "name": "CVS — Downtown Dallas", "lat": 32.7767, "lon": -96.7970, "demand": 10},
    {"id": 5, "name": "Sam's Club — Mesquite", "lat": 32.7673, "lon": -96.5992, "demand": 30},
    {"id": 6, "name": "Kroger — Arlington", "lat": 32.7357, "lon": -97.1081, "demand": 18},
    {"id": 7, "name": "Best Buy — Frisco", "lat": 33.1581, "lon": -96.8236, "demand": 22},
    {"id": 8, "name": "Costco — Lewisville", "lat": 33.0462, "lon": -97.0641, "demand": 35},
    {"id": 9, "name": "Office Depot — Richardson", "lat": 32.9483, "lon": -96.7299, "demand": 12},
    {"id": 10, "name": "Walgreens — Grand Prairie", "lat": 32.7460, "lon": -97.0147, "demand": 8},
    {"id": 11, "name": "Tribeca Loft", "lat": 40.718, "lon": -74.008, "demand": 1},
    {"id": 12, "name": "Soho Boutique", "lat": 40.724, "lon": -74.000, "demand": 2},
    {"id": 13, "name": "Williamsburg Distribution", "lat": 40.716, "lon": -73.959, "demand": 4},
    {"id": 14, "name": "Dumbo Art Gallery", "lat": 40.703, "lon": -73.990, "demand": 3},
    {"id": 15, "name": "Brooklyn Heights Library", "lat": 40.696, "lon": -73.993, "demand": 2},
]

state = {
    "stops": DALLAS_STOPS,
    "num_vehicles": 4,
    "vehicle_capacities": [100, 100, 100, 100],
    "depot_id": 0,
}

resp = httpx.post("http://localhost:8000/routes/initialize", json=state)
print(resp.json())