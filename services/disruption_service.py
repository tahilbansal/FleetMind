from sqlalchemy.orm import Session
from models import RoutePlan, DisruptionEvent, Stop
from models.enums import RoutePlanStatus, DisruptionType, DisruptionSource
from services.weather_service import WeatherService
import json

class DisruptionService:
    @staticmethod
    async def check_active_plan_disruptions(db: Session):
        """
        Analyzes the active route plan against external factors (weather).
        Creates disruption events if severe conditions are met.
        """
        plan = db.query(RoutePlan).filter(RoutePlan.status == RoutePlanStatus.ACTIVE).first()
        if not plan or not plan.state:
            return

        stops = plan.state.get("stops", []) 
        if not stops:
            return

        # Calculate center point of the fleet
        avg_lat = sum(s['lat'] for s in stops) / len(stops)
        avg_lon = sum(s['lon'] for s in stops) / len(stops)

        weather = await WeatherService.get_weather_data(avg_lat, avg_lon)
        
        if weather and weather["is_severe"]:
            # Check if we already have a recent active weather alert for this plan to avoid spam
            existing = db.query(DisruptionEvent).filter(
                DisruptionEvent.route_plan_id == plan.id,
                DisruptionEvent.disruption_type == DisruptionType.WEATHER_ALERT,
                DisruptionEvent.resolution == None
            ).first()

            if not existing:
                # Identify potentially affected stops (simplified: all stops in the area)
                affected_stop_ids = [s['id'] for s in stops]
                
                new_event = DisruptionEvent(
                    route_plan_id=plan.id,
                    source=DisruptionSource.AI_MONITOR,
                    disruption_type=DisruptionType.WEATHER_ALERT,
                    description=f"AI Monitor: {weather['summary']} detected in the operational area. "
                                f"Precipitation: {weather['max_precipitation']}mm, Wind: {weather['max_wind_speed']}km/h.",
                    structured_event={
                        "weather_stats": weather,
                        "affected_stop_ids": affected_stop_ids
                    }
                )
                db.add(new_event)
                db.commit()