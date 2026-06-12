# api/routes/routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import datetime, time
from config.database import get_db
from schemas.vrp import RouteState
from solver.data_model import build_distance_matrix
from solver.vrp_solver import solve_vrp
from services.cost_service import calculate_operational_costs as calculate_costs
import models
from models.enums import RoutePlanStatus
import os
from viz.map_renderer import get_route_geometry

router = APIRouter(prefix="/routes", tags=["Routes"])

def get_latest_plan(db: Session):
    return db.query(models.RoutePlan).order_by(models.RoutePlan.created_at.desc()).first()

@router.post("/initialize")
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

    # Fetch and store road geometry for simulation
    api_key = os.getenv("ORS_API_KEY")
    if api_key and result.get("status") == "SUCCESS":
        for v_id, route_data in result["routes"].items():
            stops_indices = route_data["stops"]
            ors_coords = [[state.stops[idx].lon, state.stops[idx].lat] for idx in stops_indices]
            geometry = get_route_geometry(ors_coords, api_key)
            if geometry:
                # Store as [lat, lon] for internal consistency
                route_data["geometry"] = [[c[1], c[0]] for c in geometry]

    solve_time_ms = (time.time() - start_time) * 1000
    cost = calculate_costs(result.get("total_distance", 0), state.num_vehicles)

    new_plan = models.RoutePlan(
        depot_id=state.depot_ids[0] if state.depot_ids else "0",
        plan_date=datetime.datetime.now().date(),
        status=RoutePlanStatus.ACTIVE,
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

@router.post("/replan")
def replan_routes(disruption: dict, db: Session = Depends(get_db)):
    """
    Accepts a structured disruption event and replans.
    """
    prev_plan = get_latest_plan(db)
    if not prev_plan:
        raise HTTPException(400, "No active route state. Call /routes/initialize first.")
    
    current_state = RouteState(**prev_plan.state)
    
    # Apply disruption to state
    if disruption.get("type") == "driver_unavailable":
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
    
    for (from_id, to_id) in current_state.blocked_edges:
        matrix[from_id][to_id] = 9999999
        matrix[to_id][from_id] = 9999999
    
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

    # Fetch and store road geometry for simulation
    api_key = os.getenv("ORS_API_KEY")
    if api_key and result.get("status") == "SUCCESS":
        for v_id, route_data in result["routes"].items():
            stops_indices = route_data["stops"]
            ors_coords = [[current_state.stops[idx].lon, current_state.stops[idx].lat] for idx in stops_indices]
            geometry = get_route_geometry(ors_coords, api_key)
            if geometry:
                route_data["geometry"] = [[c[1], c[0]] for c in geometry]

    solve_time_ms = (time.time() - start_time) * 1000
    cost = calculate_costs(result.get("total_distance", 0), current_state.num_vehicles)

    event = models.DisruptionEvent(
        route_plan_id=prev_plan.id,
        source=models.DisruptionSource.DISPATCHER_NL,
        disruption_type=disruption.get("type"),
        description=disruption.get("description", "Manual override"),
        distance_before_km=prev_plan.total_distance_km,
        distance_after_km=result.get("total_distance", 0) / 1000.0,
        cost_before=prev_plan.cost_optimized,
        cost_after=cost,
        replan_time_ms=solve_time_ms
    )
    db.add(event)

    prev_plan.status = RoutePlanStatus.COMPLETED
    new_plan = models.RoutePlan(
        depot_id=prev_plan.depot_id,
        plan_date=prev_plan.plan_date,
        status=RoutePlanStatus.ACTIVE,
        num_vehicles=current_state.num_vehicles,
        num_stops=len(current_state.stops),
        total_distance_km=result.get("total_distance", 0) / 1000.0,
        solve_time_ms=solve_time_ms,
        routes_json={**result, "cost": cost},
        cost_optimized=cost,
        state=current_state.model_dump() if hasattr(current_state, "model_dump") else current_state.dict(),
        parent_plan_id=prev_plan.id
    )
    db.add(new_plan)
    db.commit()
    
    return {**result, "cost": cost, "status": "SUCCESS"}

@router.get("/current")
def get_current_routes(db: Session = Depends(get_db)):
    plan = get_latest_plan(db)
    return {"state": plan.state if plan else None, "solution": plan.routes_json if plan else None}

@router.get("/map")
def get_map(db: Session = Depends(get_db)):
    from viz.map_renderer import render_route_map
    plan = get_latest_plan(db)
    
    if not plan:
        raise HTTPException(400, "No solution available.")
    
    # Fetch current vehicle positions
    vehicles = db.query(models.Vehicle).all()
    current_vehicle_positions = [
        {'id': v.id, 'lat': v.current_lat, 'lon': v.current_lon, 'status': v.status.value, 'plate_number': v.plate_number}
        for v in vehicles if v.current_lat is not None and v.current_lon is not None
    ]
    
    html = render_route_map(RouteState(**plan.state), plan.routes_json, current_vehicle_positions)
    return {"html": html}