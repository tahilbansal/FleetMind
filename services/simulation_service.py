import math
import random
from datetime import datetime
from sqlalchemy.orm import Session
from models import Vehicle, RoutePlan, GPSPing, DisruptionEvent
from models.enums import VehicleStatus, RoutePlanStatus, DisruptionType, DisruptionSource

class SimulationService:
    @staticmethod
    def move_vehicles(db: Session, step_minutes: float = 1.0):
        """
        Advances all vehicles in the active plan by the given time step.
        Calculates intermediate GPS positions between stops.
        """
        plan = db.query(RoutePlan).filter(RoutePlan.status == RoutePlanStatus.ACTIVE).first()
        if not plan or not plan.routes_json:
            return []

        disruptions = []

        for v_id_str, route_data in plan.routes_json.get("routes", {}).items():
            # Map solver vehicle index to database record (demo mapping)
            vehicle = db.query(Vehicle).offset(int(v_id_str)).first()
            if not vehicle:
                continue

            # Use vehicle-specific speed defined in its type (defaults to 40 km/h)
            speed_kmh = vehicle.vehicle_type.avg_speed_kmh if vehicle.vehicle_type else 40
            distance_to_move = (speed_kmh / 3.6) * (step_minutes * 60)

            if vehicle.status not in [VehicleStatus.EN_ROUTE, VehicleStatus.AVAILABLE]:
                continue

            stops_indices = route_data["stops"]
            if not stops_indices:
                continue

            # Initialize start position at first depot if vehicle has never moved
            if vehicle.current_lat is None:
                start_node = plan.state["stops"][stops_indices[0]]
                vehicle.current_lat = start_node["lat"]
                vehicle.current_lon = start_node["lon"]
                vehicle.status = VehicleStatus.EN_ROUTE

            geometry = route_data.get("geometry", [])
            if geometry:
                # Find the current point on the path
                min_dist = float('inf')
                current_idx = 0
                for i, pt in enumerate(geometry):
                    d = SimulationService._haversine(vehicle.current_lat, vehicle.current_lon, pt[0], pt[1])
                    if d < min_dist:
                        min_dist = d
                        current_idx = i
                
                # Move along the geometry segments until distance is consumed
                remaining_dist = distance_to_move
                curr_lat, curr_lon = vehicle.current_lat, vehicle.current_lon
                
                while remaining_dist > 0 and current_idx + 1 < len(geometry):
                    next_pt = geometry[current_idx + 1]
                    dist_to_next = SimulationService._haversine(curr_lat, curr_lon, next_pt[0], next_pt[1])
                    
                    if dist_to_next <= remaining_dist:
                        # Jump to the next point and keep moving
                        remaining_dist -= dist_to_next
                        curr_lat, curr_lon = next_pt[0], next_pt[1]
                        current_idx += 1
                    else:
                        # Move partially along this segment and stop
                        curr_lat, curr_lon = SimulationService._move_towards(
                            curr_lat, curr_lon, next_pt[0], next_pt[1], remaining_dist
                        )
                        remaining_dist = 0
                
                new_lat, new_lon = curr_lat, curr_lon
                if current_idx + 1 >= len(geometry) and remaining_dist >= 0:
                    vehicle.status = VehicleStatus.AVAILABLE
            else:
                # Fallback to stop-to-stop movement if no geometry available
                target_stop = None
                for idx in stops_indices:
                    stop_data = plan.state["stops"][idx]
                    dist = SimulationService._haversine(vehicle.current_lat, vehicle.current_lon, 
                                                     stop_data["lat"], stop_data["lon"])
                    if dist > 100:
                        target_stop = stop_data
                        break
                
                if not target_stop:
                    vehicle.status = VehicleStatus.AVAILABLE
                    continue
                target_lat, target_lon = target_stop["lat"], target_stop["lon"]
                new_lat, new_lon = SimulationService._move_towards(
                    vehicle.current_lat, vehicle.current_lon,
                    target_lat, target_lon,
                    distance_to_move
                )
            
            vehicle.current_lat = new_lat
            vehicle.current_lon = new_lon
            vehicle.last_seen_at = datetime.utcnow()

            # Persist location to history for telemetry charts
            db.add(GPSPing(
                vehicle_id=vehicle.id,
                route_plan_id=plan.id,
                lat=new_lat,
                lon=new_lon,
                recorded_at=datetime.utcnow()
            ))

            # Stochastic Disruption Logic
            # 0.5% chance per simulation minute of a breakdown
            if random.random() < (0.005 * step_minutes):
                event = SimulationService._trigger_incident(db, plan, vehicle)
                disruptions.append(event)

        db.commit()
        return disruptions

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        R = 6371000 # Earth radius in meters
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlon/2)**2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

    @staticmethod
    def _move_towards(lat1, lon1, lat2, lon2, distance):
        total_dist = SimulationService._haversine(lat1, lon1, lat2, lon2)
        if total_dist <= distance:
            return lat2, lon2
        
        fraction = distance / total_dist
        return lat1 + (lat2 - lat1) * fraction, lon1 + (lon2 - lon1) * fraction

    @staticmethod
    def _trigger_incident(db, plan, vehicle):
        event = DisruptionEvent(
            route_plan_id=plan.id,
            source=DisruptionSource.AI_MONITOR,
            disruption_type=DisruptionType.VEHICLE_BREAKDOWN,
            description=f"CRITICAL: Vehicle {vehicle.plate_number} has stopped. Engine telemetry indicates failure.",
            timestamp=datetime.utcnow()
        )
        vehicle.status = VehicleStatus.OFFLINE
        db.add(event)
        return event