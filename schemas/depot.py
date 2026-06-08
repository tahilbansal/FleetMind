from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from models.enums import DepotStatus

class DepotBase(BaseModel):
    name: str
    lat: float
    lon: float
    address: Optional[str] = None
    city: Optional[str] = None
    capacity_vehicles: int = 20
    status: DepotStatus = DepotStatus.ACTIVE
    operating_hours_start: int = 360
    operating_hours_end: int = 1200

class DepotCreate(DepotBase):
    pass

class DepotUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[DepotStatus] = None
    operating_hours_end: Optional[int] = None

class DepotResponse(DepotBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True