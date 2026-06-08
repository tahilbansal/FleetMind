# api/main.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import datetime, time
from sqlalchemy import inspect
from services.cost_service import calculate_operational_costs as calculate_costs

load_dotenv()

from sqlalchemy.orm.attributes import flag_modified
from config.seed_data import DEPOTS_TO_SEED, DEFAULT_SAMPLE_STATE
from config.database import engine, SessionLocal, get_db
from schemas.vrp import RouteState
from solver.data_model import build_distance_matrix
from solver.vrp_solver import solve_vrp
from models.base import Base
from models import FleetConfig
import models
from api.routes import history, routes, config

# Initialize database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="VRP Dispatch API")

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def seed_fleet_config():
    """Ensures the database has a default fleet configuration on startup."""
    inspector = inspect(engine)
    if not inspector.has_table("fleet_configs") or not inspector.has_table("depots"):
        return

    db = SessionLocal()
    try:
        # 1. Seed Depots so Foreign Keys in RoutePlans work
        for d_id, d_name, lat, lon in DEPOTS_TO_SEED:
            if not db.query(models.Depot).filter(models.Depot.id == d_id).first():
                db.add(models.Depot(id=d_id, name=d_name, lat=lat, lon=lon))
        db.commit()

        # 2. Seed Default Config
        config_entry = db.query(FleetConfig).filter(FleetConfig.name == "default").first()
        if not config_entry:
            db.add(FleetConfig(name="default", config=DEFAULT_SAMPLE_STATE))
            db.commit()
        else:
            # Force update if the schema is old (e.g. missing demand_kg or depot_ids)
            config_data = config_entry.config
            is_stale = (
                "depot_ids" not in config_data or 
                (len(config_data.get("stops", [])) > 0 and "demand_kg" not in config_data["stops"][0]) or
                config_data.get("num_vehicles") != DEFAULT_SAMPLE_STATE["num_vehicles"]
            )
            
            if is_stale:
                # We must flag the JSON column as modified so SQLAlchemy detects the change
                config_entry.config = DEFAULT_SAMPLE_STATE
                flag_modified(config_entry, "config")
                db.commit()
                print("✓ Fleet configuration schema updated in database.")

    finally:
        db.close()

def get_latest_plan(db: Session):
    return db.query(models.RoutePlan).order_by(models.RoutePlan.created_at.desc()).first()

@app.post("/routes/initialize")
def initialize_routes(state: RouteState, db: Session = Depends(get_db)):
    """Set up the initial route state and solve."""
    matrix = build_distance_matrix(state.stops)
    
    start_time = time.time()
    depots_indices = [int(d) for d in state.depot_ids] if state.depot_ids else [0] * state.num_vehicles
    result = solve_vrp(
        distance_matrix=matrix,
        num_vehicles=state.num_vehicles,
        depots=depots_indices,
        demands=[int(s.demand_kg) for s in state.stops],
        vehicle_capacities=state.vehicle_capacities,
    )
    solve_time_ms = (time.time() - start_time) * 1000
    cost = calculate_costs(result.get("total_distance", 0), state.num_vehicles)

    new_plan = models.RoutePlan(
        depot_id=state.depot_ids[0] if state.depot_ids else "0",
        plan_date=datetime.datetime.now().date(),
        num_vehicles=state.num_vehicles,
        num_stops=len(state.stops),
        total_distance_km=result.get("total_distance", 0) / 1000.0,
        solve_time_ms=solve_time_ms,
        routes_json={**result, "cost": cost},
        cost_optimized=cost,
        state=state.model_dump() if hasattr(state, "model_dump") else state.dict()
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
            d_id_str = str(d_id)
            if d_id_str not in current_state.unavailable_drivers:
                current_state.unavailable_drivers.append(d_id_str)
    
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
        capacities[int(d)] = 0
    
    depots = [int(d) for d in current_state.depot_ids] if current_state.depot_ids else [0] * current_state.num_vehicles
    start_time = time.time()
    result = solve_vrp(
        distance_matrix=matrix,
        num_vehicles=current_state.num_vehicles,
        depots=depots,
        demands=[int(s.demand_kg) for s in current_state.stops],
        vehicle_capacities=capacities,
    )
    solve_time_ms = (time.time() - start_time) * 1000
    cost = calculate_costs(result.get("total_distance", 0), current_state.num_vehicles)

    # Log Disruption
    dist_before = prev_plan.total_distance_km
    dist_after = result.get("total_distance", 0) / 1000.0
    
    event = models.DisruptionEvent(
        route_plan_id=prev_plan.id,
        source=models.DisruptionSource.DISPATCHER_NL,
        disruption_type=disruption.get("type"),
        description=disruption.get("description", "Manual override"),
        distance_before_km=dist_before,
        distance_after_km=dist_after,
        cost_before=prev_plan.cost_optimized,
        cost_after=cost,
        replan_time_ms=solve_time_ms
    )
    db.add(event)

    # Create new plan
    new_plan = models.RoutePlan(
        depot_id=prev_plan.depot_id,
        plan_date=prev_plan.plan_date,
        num_vehicles=current_state.num_vehicles,
        num_stops=len(current_state.stops),
        total_distance_km=dist_after,
        solve_time_ms=solve_time_ms,
        routes_json={**result, "cost": cost},
        cost_optimized=cost,
        state=current_state.model_dump() if hasattr(current_state, "model_dump") else current_state.dict(),
        parent_plan_id=prev_plan.id
    )
    db.add(new_plan)
    db.commit()
    
    return {**result, "cost": cost, "status": "SUCCESS"}

@app.get("/routes/current")
def get_current_routes(db: Session = Depends(get_db)):
    plan = get_latest_plan(db)
    return {"state": plan.state if plan else None, "solution": plan.routes_json if plan else None}

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
    html = render_route_map(RouteState(**plan.state), plan.routes_json)
    return {"html": html}