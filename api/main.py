# api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from sqlalchemy import inspect
import asyncio
from jobs.disruption_monitor import run_monitor

load_dotenv()

from sqlalchemy.orm.attributes import flag_modified
from config.seed_data import DEPOTS_TO_SEED, DEFAULT_SAMPLE_STATE
from config.database import engine, SessionLocal, get_db
from schemas.vrp import RouteState
from models.base import Base
from models import FleetConfig
import models
from api.routes import history, routes, config, simulation

# Initialize database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="VRP Dispatch API")

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def start_background_jobs():
    asyncio.create_task(run_monitor())

@app.on_event("startup")
def seed_fleet_config():
    """Ensures the database has a default fleet configuration on startup."""
    inspector = inspect(engine)
    if not inspector.has_table("fleet_configs") or not inspector.has_table("depots"):
        return

    db = SessionLocal()
    try:
        # 1. Seed Depots so Foreign Keys in RoutePlans work
        seeded_depot_ids = []
        for d_id, d_name, lat, lon in DEPOTS_TO_SEED:
            if not db.query(models.Depot).filter(models.Depot.id == d_id).first():
                db.add(models.Depot(id=d_id, name=d_name, lat=lat, lon=lon))
            seeded_depot_ids.append(d_id)
        db.commit()

        # 2. Seed Vehicle Types
        standard_van_type = db.query(models.VehicleType).filter(models.VehicleType.name == "Standard Van").first()
        if not standard_van_type:
            standard_van_type = models.VehicleType(
                name="Standard Van",
                category=models.VehicleCategory.SMALL_VAN,
                capacity_kg=1000.0,
                capacity_m3=10.0,
                fuel_cost_per_km=8.5
            )
            db.add(standard_van_type)
            db.commit()
            db.refresh(standard_van_type)

        # 3. Seed Vehicles (if not already present)
        for i in range(DEFAULT_SAMPLE_STATE["num_vehicles"]):
            depot_for_vehicle = seeded_depot_ids[i % len(seeded_depot_ids)] # Distribute vehicles among depots
            if not db.query(models.Vehicle).filter(models.Vehicle.plate_number == f"FM{i:03d}").first():
                db.add(models.Vehicle(id=str(i), depot_id=depot_for_vehicle, vehicle_type_id=standard_van_type.id, plate_number=f"FM{i:03d}"))
        db.commit()

        # 4. Seed Default Config
        config_entry = db.query(FleetConfig).filter(FleetConfig.name == "default").first()
        if not config_entry:
            db.add(FleetConfig(name="default", config=DEFAULT_SAMPLE_STATE))
            db.commit()
        else:
            # Force update if the schema is old (e.g. missing demand_kg or depot_ids)
            config_data = config_entry.config
            is_stale = (
                "depot_ids" not in config_data or 
                (len(config_data.get("stops", [])) > 0 and "demand_kg" not in config_data["stops"][0]) or
                config_data.get("num_vehicles") != DEFAULT_SAMPLE_STATE["num_vehicles"]
            )
            
            if is_stale:
                # We must flag the JSON column as modified so SQLAlchemy detects the change
                config_entry.config = DEFAULT_SAMPLE_STATE
                flag_modified(config_entry, "config")
                db.commit()
                print("✓ Fleet configuration schema updated in database.")

    finally:
        db.close()

app.include_router(routes.router)
app.include_router(history.router)
app.include_router(config.router)
app.include_router(simulation.router)