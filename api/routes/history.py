# api/routes/history.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from config.database import get_db
import models

router = APIRouter(prefix="/history", tags=["History"])

@router.get("")
def get_history(db: Session = Depends(get_db)):
    plans = db.query(models.RoutePlan).order_by(models.RoutePlan.created_at.desc()).limit(10).all()
    disruptions = db.query(models.DisruptionEvent).order_by(models.DisruptionEvent.timestamp.desc()).limit(10).all()
    return {"plans": plans, "disruptions": disruptions}