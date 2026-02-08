import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / "backend"))
from database import SessionLocal, UserSettings
from config import TRAFFIC_API_KEY, TRAFFIC_ROUTES_CONFIG

db = SessionLocal()
try:
    settings = db.query(UserSettings).first()
    print(f"TRAFFIC_API_KEY: {'[SET]' if TRAFFIC_API_KEY else '[MISSING]'}")
    print(f"TRAFFIC_ROUTES_CONFIG (env): {TRAFFIC_ROUTES_CONFIG}")
    if settings:
        print(f"UserSettings.location_name: {settings.location_name}")
        print(f"UserSettings.traffic_routes: {settings.traffic_routes}")
    else:
        print("No UserSettings found in DB.")
finally:
    db.close()
