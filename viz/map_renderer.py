# viz/map_renderer.py
import folium
from folium import plugins
from solver.data_model import RouteState

# Color each driver's route differently
ROUTE_COLORS = [
    "blue", "red", "green", "purple", "orange",
    "darkred", "lightred", "darkblue", "darkgreen", "cadetblue"
]

def render_route_map(state: RouteState, solution: dict) -> str:
    """
    Renders all vehicle routes on an interactive Folium map.
    Returns HTML string for embedding or saving.
    """
    # Center map on depot
    depot = state.stops[state.depot_id]
    m = folium.Map(location=[depot.lat, depot.lon], zoom_start=12)

    # Add depot marker
    folium.Marker(
        location=[depot.lat, depot.lon],
        popup="<b>DEPOT</b>",
        icon=folium.Icon(color="black", icon="home")
    ).add_to(m)

    # Track all coordinates for bounds
    all_coords = [[depot.lat, depot.lon]]

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
            if stop_idx != state.depot_id:
                folium.CircleMarker(
                    location=[stop.lat, stop.lon],
                    radius=8,
                    color=color,
                    fill=True,
                    fill_opacity=0.8,
                    popup=folium.Popup(
                        f"<b>Stop {stop_idx}: {stop.name}</b><br>"
                        f"Driver: {vehicle_id}<br>"
                        f"Demand: {stop.demand} units",
                        max_width=200
                    ),
                    tooltip=f"Driver {vehicle_id} — {stop.name}"
                ).add_to(m)
        
        # Draw route line (including depot connections)
        if len(route_coords) > 1:
            folium.PolyLine(
                locations=route_coords,
                color=color,
                weight=3,
                opacity=0.8,
                tooltip=f"Driver {vehicle_id} — {route_data['distance']:.0f}m"
            ).add_to(m)

    # Add distance summary in bottom-right
    total_km = solution["total_distance"] / 1000
    folium.map.Marker(
        [depot.lat - 0.05, depot.lon + 0.05],
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