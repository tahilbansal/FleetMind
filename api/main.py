# api/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv
import os

load_dotenv()

from solver.data_model import RouteState, Stop, build_distance_matrix
from solver.vrp_solver import solve_vrp

app = FastAPI(title="VRP Dispatch API")

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

# In-memory state (replace with Redis/DB in production)
current_state: Optional[RouteState] = None
current_solution: Optional[dict] = None

@app.post("/routes/initialize")
def initialize_routes(state: RouteState):
    """Set up the initial route state and solve."""
    global current_state, current_solution
    current_state = state
    matrix = build_distance_matrix(state.stops)
    
    result = solve_vrp(
        distance_matrix=matrix,
        num_vehicles=state.num_vehicles,
        depot=state.depot_id,
        demands=[s.demand for s in state.stops],
        vehicle_capacities=state.vehicle_capacities,
    )
    current_solution = {**result, "status": "SUCCESS"}
    return current_solution

@app.post("/routes/replan")
def replan_routes(disruption: dict):
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
    global current_state, current_solution
    if not current_state:
        raise HTTPException(400, "No active route state. Call /routes/initialize first.")
    
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
    
    result = solve_vrp(
        distance_matrix=matrix,
        num_vehicles=current_state.num_vehicles,
        depot=current_state.depot_id,
        demands=[s.demand for s in current_state.stops],
        vehicle_capacities=capacities,
    )
    current_solution = {**result, "status": "SUCCESS"}
    return current_solution

@app.get("/routes/current")
def get_current_routes():
    return {"state": current_state, "solution": current_solution}

@app.get("/routes/map")
def get_map():
    """Returns HTML of the Folium map for the current solution."""
    from viz.map_renderer import render_route_map
    if not current_state or not current_solution:
        raise HTTPException(400, "No solution available.")
    html = render_route_map(current_state, current_solution)
    return {"html": html}