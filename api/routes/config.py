from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from config.database import get_db
from models import FleetConfig

router = APIRouter(prefix="/routes", tags=["Config"])

@router.get("/config")
def get_fleet_config(name: str = "default", db: Session = Depends(get_db)):
    """Retrieves a stored fleet configuration template."""
    cfg = db.query(FleetConfig).filter(FleetConfig.name == name).first()
    if not cfg:
        raise HTTPException(404, f"Configuration '{name}' not found")
    return cfg.config