import sys
import asyncio
from pathlib import Path
sys.path.append(str(Path(__file__).parent / "backend"))
from database import SessionLocal, TrafficRoute
from fetchers.traffic import fetch_traffic_alerts

async def test_full_fetch():
    db = SessionLocal()
    try:
        print("Starting full traffic/weather alert fetch...")
        count, errors = await fetch_traffic_alerts()
        print(f"Fetch completed: {count} alerts found, {len(errors)} errors reported.")
        for err in errors:
            print(f" ERROR: {err}")
        
        routes = db.query(TrafficRoute).all()
        print(f"\nVerifying {len(routes)} routes in DB:")
        for r in routes:
            print(f" - {r.name}:")
            print(f"   Coords: {r.origin_lat},{r.origin_lon} -> {r.dest_lat},{r.dest_lon}")
            print(f"   Zones: {r.origin_zone} -> {r.dest_zone}")
            print(f"   Status: {r.current_duration_minutes}min (Delay: {r.delay_minutes}min)")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_full_fetch())
