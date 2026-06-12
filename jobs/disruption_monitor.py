import asyncio
import logging
from config.database import SessionLocal
from services.disruption_service import DisruptionService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DisruptionMonitor")

async def run_monitor():
    """Background job that runs every 5 minutes."""
    logger.info("Starting Proactive Disruption Monitor...")
    while True:
        db = SessionLocal()
        try:
            logger.info("Checking for weather disruptions...")
            await DisruptionService.check_active_plan_disruptions(db)
        except Exception as e:
            logger.error(f"Error in monitor loop: {e}")
        finally:
            db.close()
        await asyncio.sleep(15) # Wait 5 minutes

if __name__ == "__main__":
    asyncio.run(run_monitor())