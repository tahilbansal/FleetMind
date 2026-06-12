# viz/map_renderer.py
import folium
import requests
import math
import os
from folium.plugins import AntPath
from folium import plugins
from solver.data_model import RouteState

# Color each driver's route differently
ROUTE_COLORS = [
    "blue", "red", "green", "purple", "orange",
    "darkred", "lightred", "darkblue", "darkgreen", "cadetblue"
]

def get_route_geometry(coordinates, api_key):
    """Fetches real road path for a sequence of coordinates from OpenRouteService."""
    if not coordinates or len(coordinates) < 2:
        return None
    url = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
    body = {"coordinates": coordinates}
    headers = {"Authorization": api_key, "Content-Type": "application/json"}
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=10.0)
        if resp.status_code == 200:
            return resp.json()["features"][0]["geometry"]["coordinates"]
    except Exception:
        pass
    return None

def split_route_by_position(coords, current_pos):
    """Splits a list of [lat, lon] coordinates into (past, future) based on current position."""
    if not coords or not current_pos:
        return [], coords
    
    min_dist = float('inf')
    idx = 0
    for i, pt in enumerate(coords):
        dist = (pt[0] - current_pos[0])**2 + (pt[1] - current_pos[1])**2
        if dist < min_dist:
            min_dist = dist
            idx = i
    return coords[:idx+1], coords[idx:]

def render_route_map(state: RouteState, solution: dict, current_vehicle_positions: list) -> str:
    """ 
    Renders all vehicle routes on an interactive Folium map.
    Returns HTML string for embedding or saving.
    """
    api_key = os.getenv("ORS_API_KEY")

    # Ensure we get depot indices correctly from the state
    if hasattr(state, 'depot_ids') and state.depot_ids:
        depot_indices = [int(d) for d in state.depot_ids if d.isdigit()] # Ensure conversion to int is safe
    else:
        # Fallback for legacy data/single depot
        depot_indices = [0] * state.num_vehicles
        
    unique_depot_indices = sorted(list(set(depot_indices)))
    
    # Center map on the first identified depot
    main_depot = state.stops[unique_depot_indices[0]]
    m = folium.Map(location=[main_depot.lat, main_depot.lon], zoom_start=13)

    # Add markers for all unique depots with a distinct style
    for d_idx in unique_depot_indices:
        d_stop = state.stops[d_idx]
        folium.Marker(
            location=[d_stop.lat, d_stop.lon],
            popup=f"<b>WAREHOUSE HUB</b><br>ID: {d_stop.id}<br>Name: {d_stop.name}",
            icon=folium.Icon(color="black", icon="home")
        ).add_to(m)

    # Track all coordinates for bounds
    all_coords = []
    for d_idx in unique_depot_indices:
        all_coords.append([state.stops[d_idx].lat, state.stops[d_idx].lon])

    # Draw each vehicle's route
    for vehicle_id, route_data in solution["routes"].items():
        stops_in_route = route_data["stops"]
        color = ROUTE_COLORS[int(vehicle_id) % len(ROUTE_COLORS)]

        route_coords = []
        for stop_idx in stops_in_route:
            stop = state.stops[stop_idx]
            route_coords.append([stop.lat, stop.lon])
            all_coords.append([stop.lat, stop.lon])
            
            # Add stop marker (skip depot marker since already added)
            if stop_idx not in unique_depot_indices:
                folium.CircleMarker(
                    location=[stop.lat, stop.lon],
                    radius=6,
                    color=color,
                    fill=True,
                    fill_opacity=0.6,
                    popup=folium.Popup(
                        f"<b>Stop {stop_idx}: {stop.name}</b><br>"
                        f"Driver: {vehicle_id}<br>"
                        f"Demand: {stop.demand_kg} kg",
                        max_width=200
                    ),
                    tooltip=f"Driver {vehicle_id} — {stop.name}"
                ).add_to(m)
        
        # Find current position for this vehicle to split the line
        current_pos = None
        vehicle_status = "active"
        for v_pos in current_vehicle_positions:
            # Matching logic depends on how IDs are passed from the frontend/simulator
            if v_pos['id'] == str(vehicle_id):
                current_pos = [v_pos['lat'], v_pos['lon']]
                vehicle_status = v_pos.get('status', 'active').lower()
                break

        # Draw route line
        if len(stops_in_route) > 1:
            full_geometry = []
            # Use pre-stored road path if available
            if "geometry" in route_data:
                full_geometry = route_data["geometry"]
            elif api_key:
                ors_coords = [[state.stops[idx].lon, state.stops[idx].lat] for idx in stops_in_route]
                geometry = get_route_geometry(ors_coords, api_key)
                if geometry:
                    full_geometry = [[c[1], c[0]] for c in geometry]
            
            if not full_geometry:
                full_geometry = route_coords

            if current_pos:
                past, future = split_route_by_position(full_geometry, current_pos)
                # Render past path (faded/dotted)
                if past:
                    folium.PolyLine(
                        locations=past, color=color, weight=2, 
                        opacity=0.4, dash_array='5, 10'
                    ).add_to(m)
                # Render future path (animated AntPath)
                if future:
                    AntPath(
                        locations=future, color=color, weight=4,
                        opacity=0.8, delay=1000, pulse_color='#ffffff'
                    ).add_to(m)
            else:
                # Standard PolyLine if no real-time position
                folium.PolyLine(
                    locations=full_geometry, color=color, weight=4, opacity=0.7
                ).add_to(m)

        # Add vehicle marker with fault logic
        if current_pos:
            v_color = color
            v_icon = "truck"
            if vehicle_status in ["fault", "error", "broken", "delayed"]:
                v_color = "red"
                v_icon = "exclamation-triangle"
            
            folium.Marker(
                location=current_pos,
                popup=f"<b>Vehicle {vehicle_id}</b><br>Status: {vehicle_status.upper()}",
                icon=folium.Icon(color=v_color, icon=v_icon, prefix="fa"),
                tooltip=f"Driver {vehicle_id} ({vehicle_status})"
            ).add_to(m)

    # Add distance summary in bottom-right
    total_km = solution["total_distance"] / 1000
    folium.map.Marker(
        [main_depot.lat - 0.05, main_depot.lon + 0.05],
        icon=folium.DivIcon(html=f"""
            <div style="background:white;padding:8px;border-radius:4px;
                        border:1px solid #ccc;font-size:12px;">
                <b>Total fleet distance:</b><br>{total_km:.1f} km
            </div>
        """)
    ).add_to(m)

    # Auto-fit map to show all markers
    if len(all_coords) > 1:
        m.fit_bounds(all_coords)

    return m._repr_html_()