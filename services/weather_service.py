import httpx
from typing import List, Dict, Optional

class WeatherService:
    @staticmethod
    async def get_weather_data(lat: float, lon: float) -> Optional[Dict]:
        """
        Fetches current weather and 3-hour forecast from Open-Meteo.
        Open-Meteo is free for non-commercial use and requires no API key.
        """
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "precipitation,wind_speed_10m,weather_code",
            "forecast_days": 1
        }
        
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(url, params=params, timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    # Check conditions for the next 3 hours
                    hourly = data.get("hourly", {})
                    precip = hourly.get("precipitation", [0])[0:3]
                    wind = hourly.get("wind_speed_10m", [0])[0:3]
                    
                    max_precip = max(precip) if precip else 0
                    max_wind = max(wind) if wind else 0
                    
                    # Thresholds for 'Severe' weather
                    is_severe = max_precip >= 0 or max_wind > 10  # Using > 0 for rain testing
                    
                    return {
                        "is_severe": is_severe,
                        "max_precipitation": max_precip,
                        "max_wind_speed": max_wind,
                        "summary": "Heavy Rain" if max_precip >= 0 else "High Winds" if max_wind > 10 else "Clear"
                    }
            except Exception:
                return None
        return None