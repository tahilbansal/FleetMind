# api/main.py
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv
import os, time
from sqlalchemy.orm import Session

load_dotenv()

from .schemas.vrp import RouteState, Stop
from solver.data_model import build_distance_matrix
from solver.vrp_solver import solve_vrp
from .db.session import engine, get_db, SessionLocal
from .db.base import Base
from .db import models  # Importing the models package registers them with Base

# Initialize database tables
Base.metadata.create_all(bind=engine)

COST_CONFIG = {
    "fuel_cost_per_km": 8.5,      # ₹ per km
    "avg_speed_kmh": 30,          # Estimated avg speed in city
    "driver_cost_per_hour": 150,   # ₹ per hour
    "vehicle_fixed_cost_per_day": 500,  # ₹ depreciation etc
}

def calculate_costs(total_distance_m, num_vehicles):
    dist_km = total_distance_m / 1000.0
    fuel_cost = dist_km * COST_CONFIG["fuel_cost_per_km"]
    
    # Est. time: distance / speed
    hours = dist_km / COST_CONFIG["avg_speed_kmh"]
    driver_cost = hours * COST_CONFIG["driver_cost_per_hour"]
    
    fixed_cost = num_vehicles * COST_CONFIG["vehicle_fixed_cost_per_day"]
    
    total = fuel_cost + driver_cost + fixed_cost
    return round(total, 2)

app = FastAPI(title="VRP Dispatch API")

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def seed_fleet_config():
    """Ensures the database has a default fleet configuration on startup."""
    db = SessionLocal()
    try:
        default_exists = db.query(models.FleetConfig).filter(models.FleetConfig.name == "default").first()
        if not default_exists:
            sample_state = {
                "stops": [
                    {"id": 0, "name": "Warehouse North (Main)", "lat": 40.735, "lon": -74.006, "demand": 0},
                    {"id": 10, "name": "Warehouse South (Secondary)", "lat": 40.707, "lon": -74.011, "demand": 0},
                    {"id": 1, "name": "Hell's Kitchen Delivery", "lat": 40.763, "lon": -73.992, "demand": 2},
                    {"id": 2, "name": "UWS Apartments", "lat": 40.783, "lon": -73.980, "demand": 1},
                    {"id": 3, "name": "UES Medical Center", "lat": 40.773, "lon": -73.956, "demand": 3},
                    {"id": 4, "name": "Midtown Office Hub", "lat": 40.754, "lon": -73.972, "demand": 2},
                    {"id": 5, "name": "Chelsea Market Drop-off", "lat": 40.746, "lon": -74.001, "demand": 4},
                    {"id": 6, "name": "Washington Square Park", "lat": 40.733, "lon": -73.997, "demand": 1},
                    {"id": 7, "name": "East Village Cafe", "lat": 40.729, "lon": -73.987, "demand": 2},
                    {"id": 8, "name": "LES Retail Store", "lat": 40.715, "lon": -73.988, "demand": 3},
                    {"id": 9, "name": "FiDi Tech Office", "lat": 40.707, "lon": -74.011, "demand": 2}
                ],
                "num_vehicles": 4,
                "vehicle_capacities": [10, 10, 10, 10],
                "depot_ids": [0, 0, 1, 1] # 2 vehicles per depot (indices 0 and 1)
            }
            db.add(models.FleetConfig(name="default", config=sample_state))
            db.commit()
    finally:
        db.close()

def get_latest_plan(db: Session):
    return db.query(models.RoutePlan).order_by(models.RoutePlan.id.desc()).first()

@app.post("/routes/initialize")
def initialize_routes(state: RouteState, db: Session = Depends(get_db)):
    """Set up the initial route state and solve."""
    matrix = build_distance_matrix(state.stops)
    
    start_time = time.time()
    depots = state.depot_ids if state.depot_ids else [0] * state.num_vehicles
    result = solve_vrp(
        distance_matrix=matrix,
        num_vehicles=state.num_vehicles,
        depots=depots,
        demands=[s.demand for s in state.stops],
        vehicle_capacities=state.vehicle_capacities,
    )
    solve_time_ms = (time.time() - start_time) * 1000
    cost = calculate_costs(result.get("total_distance", 0), state.num_vehicles)

    new_plan = models.RoutePlan(
        num_vehicles=state.num_vehicles,
        num_stops=len(state.stops),
        total_distance_km=result.get("total_distance", 0) / 1000.0,
        solve_time_ms=solve_time_ms,
        routes={**result, "cost": cost},
        state=state.dict()
    )
    db.add(new_plan)
    db.commit()
    return {**result, "status": "SUCCESS"}

@app.post("/routes/replan")
def replan_routes(disruption: dict, db: Session = Depends(get_db)):
    """
    Accepts a structured disruption event and replans.
    disruption = {
        "type": "driver_unavailable" | "road_blocked" | "stop_reassignment",
        "driver_id": int (optional),
        "blocked_edge": [from_id, to_id] (optional),
        "reassign_stops": [stop_ids] (optional),
        "target_driver": int (optional)
    }
    """
    prev_plan = get_latest_plan(db)
    if not prev_plan:
        raise HTTPException(400, "No active route state. Call /routes/initialize first.")
    
    current_state = RouteState(**prev_plan.state)
    
    # Apply disruption to state
    if disruption.get("type") == "driver_unavailable":
        # Support both single ID and multiple IDs
        ids = disruption.get("driver_ids", [])
        if "driver_id" in disruption:
            ids.append(disruption["driver_id"])
        for d_id in ids:
            if d_id not in current_state.unavailable_drivers:
                current_state.unavailable_drivers.append(d_id)
    
    if disruption.get("type") == "road_blocked":
        edge = tuple(disruption["blocked_edge"])
        current_state.blocked_edges.append(edge)
    
    matrix = build_distance_matrix(current_state.stops)
    
    # Penalize blocked edges by setting very high cost
    for (from_id, to_id) in current_state.blocked_edges:
        matrix[from_id][to_id] = 9999999
        matrix[to_id][from_id] = 9999999
    
    # Exclude unavailable drivers by setting capacity to 0
    capacities = current_state.vehicle_capacities.copy()
    for d in current_state.unavailable_drivers:
        capacities[d] = 0
    
    depots = current_state.depot_ids if current_state.depot_ids else [0] * current_state.num_vehicles
    start_time = time.time()
    result = solve_vrp(
        distance_matrix=matrix,
        num_vehicles=current_state.num_vehicles,
        depots=depots,
        demands=[s.demand for s in current_state.stops],
        vehicle_capacities=capacities,
    )
    solve_time_ms = (time.time() - start_time) * 1000
    cost = calculate_costs(result.get("total_distance", 0), current_state.num_vehicles)

    # Log Disruption
    dist_before = prev_plan.total_distance_km
    dist_after = result.get("total_distance", 0) / 1000.0
    
    event = models.DisruptionEvent(
        description=disruption.get("description", "Manual override"),
        disruption_type=disruption.get("type"),
        distance_before_km=dist_before,
        distance_after_km=dist_after,
        replan_time_ms=solve_time_ms
    )
    db.add(event)

    # Create new plan
    new_plan = models.RoutePlan(
        num_vehicles=current_state.num_vehicles,
        num_stops=len(current_state.stops),
        total_distance_km=dist_after,
        solve_time_ms=solve_time_ms,
        routes={**result, "cost": cost},
        state=current_state.dict()
    )
    db.add(new_plan)
    db.commit()
    
    return {**result, "cost": cost, "status": "SUCCESS"}

@app.get("/routes/current")
def get_current_routes(db: Session = Depends(get_db)):
    plan = get_latest_plan(db)
    return {"state": plan.state if plan else None, "solution": plan.routes if plan else None}

@app.get("/history")
def get_history(db: Session = Depends(get_db)):
    plans = db.query(models.RoutePlan).order_by(models.RoutePlan.created_at.desc()).limit(10).all()
    disruptions = db.query(models.DisruptionEvent).order_by(models.DisruptionEvent.timestamp.desc()).limit(10).all()
    return {"plans": plans, "disruptions": disruptions}

@app.get("/routes/config")
def get_fleet_config(name: str = "default", db: Session = Depends(get_db)):
    """Retrieves a stored fleet configuration template."""
    cfg = db.query(models.FleetConfig).filter(models.FleetConfig.name == name).first()
    if not cfg:
        raise HTTPException(404, f"Configuration '{name}' not found")
    return cfg.config

@app.get("/routes/map")
def get_map(db: Session = Depends(get_db)):
    from viz.map_renderer import render_route_map
    plan = get_latest_plan(db)
    if not plan:
        raise HTTPException(400, "No solution available.")
    html = render_route_map(RouteState(**plan.state), plan.routes)
    return {"html": html}