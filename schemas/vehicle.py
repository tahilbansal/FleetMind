from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from models.enums import VehicleStatus, VehicleCategory

class VehicleTypeBase(BaseModel):
    name: str
    category: VehicleCategory
    capacity_kg: float
    capacity_m3: float
    fuel_cost_per_km: float
    max_range_km: float = 500.0
    avg_speed_kmh: int = 40

class VehicleTypeResponse(VehicleTypeBase):
    id: str
    class Config:
        from_attributes = True

class VehicleBase(BaseModel):
    depot_id: str
    vehicle_type_id: str
    plate_number: str
    status: VehicleStatus = VehicleStatus.AVAILABLE

class VehicleCreate(VehicleBase):
    pass

class VehicleUpdate(BaseModel):
    status: Optional[VehicleStatus] = None
    current_lat: Optional[float] = None
    current_lon: Optional[float] = None

class VehicleResponse(VehicleBase):
    id: str
    current_lat: Optional[float] = None
    current_lon: Optional[float] = None
    last_seen_at: Optional[datetime] = None
    
    # Nested relationships can be included if needed
    # vehicle_type: Optional[VehicleTypeResponse] = None

    class Config:
        from_attributes = True

class GPSPingRequest(BaseModel):
    lat: float
    lon: float
    speed_kmh: float = 0.0