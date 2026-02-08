import sys
import asyncio
from pathlib import Path
sys.path.append(str(Path(__file__).parent / "backend"))
from database import SessionLocal, TrafficRoute
from fetchers.traffic import fetch_route_estimates

async def check_and_run():
    db = SessionLocal()
    try:
        routes = db.query(TrafficRoute).all()
        print(f"Initially found {len(routes)} routes in TrafficRoute table.")
        
        print("Running fetch_route_estimates()...")
        updated = await fetch_route_estimates(db)
        print(f"Fetcher reported {updated} updates.")
        
        routes_after = db.query(TrafficRoute).all()
        print(f"Now found {len(routes_after)} routes in TrafficRoute table.")
        for r in routes_after:
            print(f" - {r.name}: {r.current_duration_minutes}min (Delay: {r.delay_minutes}min)")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(check_and_run())
