from pydantic import BaseModel, EmailStr
from typing import Optional
from models.enums import DriverStatus

class DriverBase(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    status: DriverStatus = DriverStatus.AVAILABLE
    vehicle_id: Optional[str] = None

class DriverCreate(DriverBase):
    pass

class DriverResponse(DriverBase):
    id: str
    behavior_score: float

    class Config:
        from_attributes = True

class BehaviorReport(BaseModel):
    behavior_score: float
    llm_report: str