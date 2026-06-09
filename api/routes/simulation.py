from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from config.database import get_db
from services.simulation_service import SimulationService
import models

router = APIRouter(prefix="/simulation", tags=["Simulation"])

@router.post("/step")
def run_sim_step(minutes: float = 5.0, db: Session = Depends(get_db)):
    """
    Advances the simulation clock, moves vehicles, and triggers stochastic incidents.
    Returns a list of actionable disruptions.
    """
    disruptions = SimulationService.move_vehicles(db, step_minutes=minutes)
    
    results = []
    for d in disruptions:
        # Heuristic AI Suggestion (in production, this would be a prompt to Gemini)
        suggestion = "Mark driver as unavailable and reassign pending stops to the nearest vehicle."
        
        results.append({
            "id": str(d.id),
            "type": d.disruption_type,
            "description": d.description,
            "suggestion": suggestion,
            "severity": "CRITICAL",
            "timestamp": d.timestamp.isoformat(),
            # Pre-formatted command for the Dispatcher Agent
            "action_command": f"Driver {d.description.split(' ')[2]} is offline. Reassign their stops."
        })
        
    return {"status": "SUCCESS", "events": results}