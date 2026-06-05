# agent/tools.py
from langchain.tools import tool
import httpx
import json
from typing import List, Union

BASE_URL = "http://localhost:8000"

@tool
def get_current_routes() -> str:
    """
    Get the current route assignments and solution for all drivers.
    Use this first to understand the current state before making changes.
    """
    try:
        resp = httpx.get(f"{BASE_URL}/routes/current", timeout=5.0)
        data = resp.json()
        solution = data.get("solution", {})
        if not solution or solution.get("status") == "FAILED":
            return "No active routes. Please initialize first."
        
        summary = []
        for vid, route in solution["routes"].items():
            stops = route["stops"]
            dist_km = route["distance"] / 1000
            summary.append(
                f"Driver {vid}: stops {stops} | distance {dist_km:.1f}km"
            )
        return "\n".join(summary)
    except Exception as e:
        return f"Error getting routes: {str(e)}"

@tool
def mark_drivers_unavailable(driver_ids: Union[int, List[int]]) -> str:
    """
    Mark one or more drivers as unavailable (sick, broken vehicle, etc.).
    This removes them from the fleet and triggers a single replanning cycle.
    Use this to handle multiple driver issues at once for better efficiency.
    
    Args:
        driver_ids: A single integer ID or a list of integer IDs of the drivers.
    """
    if isinstance(driver_ids, int):
        payload = {"type": "driver_unavailable", "driver_id": driver_ids}
        d_label = f"Driver {driver_ids}"
    else:
        payload = {"type": "driver_unavailable", "driver_ids": driver_ids}
        d_label = f"Drivers {driver_ids}"

    try:
        resp = httpx.post(
            f"{BASE_URL}/routes/replan", 
            json=payload, 
            timeout=60.0
        )
        result = resp.json()
        if result.get("status") == "SUCCESS":
            return f"✓ {d_label} removed. Routes replanned. New total distance: {result['total_distance']/1000:.1f}km"
        return "✗ Replanning failed — server encountered an optimization error."
    except Exception as e:
        return f"Error: {str(e)}"

@tool
def block_road_segment(from_stop_id: int, to_stop_id: int) -> str:
    """
    Block a road segment between two stop locations (road closure, accident).
    The solver will route around this segment automatically.
    
    Args:
        from_stop_id: Starting stop ID of the blocked segment
        to_stop_id: Ending stop ID of the blocked segment
    """
    try:
        resp = httpx.post(f"{BASE_URL}/routes/replan", json={
            "type": "road_blocked",
            "blocked_edge": [from_stop_id, to_stop_id]
        }, timeout=30.0)
        result = resp.json()
        if result.get("status") == "SUCCESS":
            return f"✓ Road {from_stop_id}→{to_stop_id} blocked. Routes updated. New distance: {result['total_distance']/1000:.1f}km"
        return "✗ Replanning failed."
    except Exception as e:
        return f"Error: {str(e)}"

@tool
def get_stop_info() -> str:
    """
    Get information about all delivery stops including their IDs, names,
    and current demands. Use this to understand stop IDs before making changes.
    """
    try:
        resp = httpx.get(f"{BASE_URL}/routes/current", timeout=5.0)
        data = resp.json()
        state = data.get("state", {})
        stops = state.get("stops", [])
        
        lines = ["Stop Information:"]
        for stop in stops:
            lines.append(f"  ID {stop['id']}: {stop['name']} (demand: {stop['demand']} units)")
        return "\n".join(lines) if len(lines) > 1 else "No stops loaded."
    except Exception as e:
        return f"Error getting stops: {str(e)}"
