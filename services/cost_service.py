from config.constants import COST_CONFIG

def calculate_operational_costs(total_distance_m: float, num_vehicles: int) -> float:
    dist_km = total_distance_m / 1000.0
    fuel_cost = dist_km * COST_CONFIG["fuel_cost_per_km"]
    
    # Est. time: distance / speed
    hours = dist_km / COST_CONFIG["avg_speed_kmh"]
    driver_cost = hours * COST_CONFIG["driver_cost_per_hour"]
    
    fixed_cost = num_vehicles * COST_CONFIG["vehicle_fixed_cost_per_day"]
    
    total = fuel_cost + driver_cost + fixed_cost
    return round(total, 2)