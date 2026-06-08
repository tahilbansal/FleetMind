# viz/map_renderer.py
import folium
import requests
import os
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

def render_route_map(state: RouteState, solution: dict) -> str:
    """
    Renders all vehicle routes on an interactive Folium map.
    Returns HTML string for embedding or saving.
    """
    api_key = os.getenv("ORS_API_KEY")

    # Ensure we get depot indices correctly from the state
    if hasattr(state, 'depot_ids') and state.depot_ids:
        depot_indices = [int(d) for d in state.depot_ids]
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
                    radius=8,
                    color=color,
                    fill=True,
                    fill_opacity=0.8,
                    popup=folium.Popup(
                        f"<b>Stop {stop_idx}: {stop.name}</b><br>"
                        f"Driver: {vehicle_id}<br>"
                        f"Demand: {stop.demand_kg} kg",
                        max_width=200
                    ),
                    tooltip=f"Driver {vehicle_id} — {stop.name}"
                ).add_to(m)
        
        # Draw route line
        if len(stops_in_route) > 1:
            if api_key:
                # Real road routing using OpenRouteService (one call per vehicle)
                ors_coords = [[state.stops[idx].lon, state.stops[idx].lat] for idx in stops_in_route]
                geometry = get_route_geometry(ors_coords, api_key)
                
                if geometry:
                    # ORS returns [lon, lat] — Folium needs [lat, lon]
                    folium_coords = [[c[1], c[0]] for c in geometry]
                    folium.PolyLine(
                        locations=folium_coords,
                        color=color, weight=4,
                        opacity=0.85, smooth_factor=1,
                        tooltip=f"Driver {vehicle_id}"
                    ).add_to(m)
                else:
                    # Fallback to straight lines if API call fails
                    folium.PolyLine(
                        locations=route_coords,
                        color=color, weight=3,
                        opacity=0.8,
                        tooltip=f"Driver {vehicle_id} (fallback)"
                    ).add_to(m)
            else:
                # Fallback to straight lines if API key is missing
                folium.PolyLine(
                    locations=route_coords,
                    color=color, weight=3,
                    opacity=0.8,
                    tooltip=f"Driver {vehicle_id} — {route_data['distance']:.0f}m"
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