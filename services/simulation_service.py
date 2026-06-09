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
        avg_speed_mps = 40 / 3.6  # 40 km/h converted to meters per second
        distance_to_move = avg_speed_mps * (step_minutes * 60)

        for v_id_str, route_data in plan.routes_json.get("routes", {}).items():
            # Map solver vehicle index to database record (demo mapping)
            vehicle = db.query(Vehicle).offset(int(v_id_str)).first()
            if not vehicle:
                continue

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

            # Find the next target stop in the sequence that hasn't been reached
            target_stop = None
            for idx in stops_indices:
                stop_data = plan.state["stops"][idx]
                dist = SimulationService._haversine(vehicle.current_lat, vehicle.current_lon, 
                                                 stop_data["lat"], stop_data["lon"])
                if dist > 100: # Threshold for 'arrived' (100 meters)
                    target_stop = stop_data
                    break
            
            if not target_stop:
                vehicle.status = VehicleStatus.AVAILABLE # Completed its route
                continue

            # Interpolate new position moving towards the target stop
            new_lat, new_lon = SimulationService._move_towards(
                vehicle.current_lat, vehicle.current_lon,
                target_stop["lat"], target_stop["lon"],
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