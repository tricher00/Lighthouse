import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import json
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import init_db, SessionLocal, TrafficRoute, TrafficAlert
from fetchers.traffic import fetch_route_estimates, fetch_traffic_alerts

async def test_traffic_estimates():
    print("Starting Traffic Estimates Test...")
    
    # Initialize DB (in-memory or local test db)
    init_db()
    db = SessionLocal()
    
    # Mock data for TomTom API (Geocoding and Routing)
    mock_geocode_response = {
        "results": [
            {
                "position": {"lat": 42.3601, "lon": -71.0589}
            }
        ]
    }
    
    mock_routing_response = {
        "routes": [
            {
                "summary": {
                    "travelTimeInSeconds": 1500,  # 25 min
                    "trafficDelayInSeconds": 300   # 5 min
                }
            }
        ]
    }
    
    # Configure test routes (one with coordinates, one with address)
    test_routes = [
        {"name": "Coords Route", "origin": "1,1", "destination": "2,2"},
        {"name": "Address Route", "origin": "100 Main St, Boston", "destination": "MIT, Cambridge"}
    ]
    
    with patch("fetchers.traffic.TRAFFIC_API_KEY", "fake_key"), \
         patch("fetchers.traffic.TRAFFIC_ROUTES_CONFIG", test_routes), \
         patch("aiohttp.ClientSession.get") as mock_get:
        
        # Setup mock response logic
        async def mock_get_logic(url, params=None, **kwargs):
            mock_resp = MagicMock()
            mock_resp.status = 200
            
            if "search/2/geocode" in url:
                async def mock_json(): return mock_geocode_response
            else:
                async def mock_json(): return mock_routing_response
                
            mock_resp.json = mock_json
            return mock_resp

        # aiohttp context manager mock
        mock_get.return_value.__aenter__.side_effect = mock_get_logic
        
        print("Fetching route estimates...")
        updated = await fetch_route_estimates(db)
        print(f"Updated {updated} routes.")
        
        # Verify Coords Route
        route1 = db.query(TrafficRoute).filter(TrafficRoute.name == "Coords Route").first()
        assert route1 is not None
        assert route1.current_duration_minutes == 25
        
        # Verify Address Route
        route2 = db.query(TrafficRoute).filter(TrafficRoute.name == "Address Route").first()
        assert route2 is not None
        assert route2.current_duration_minutes == 25
        # The origin/destination in DB should be the RAW strings from config
        assert route2.origin == "100 Main St, Boston"
        
        print("DB Verification Successful!")

    db.close()
    print("Traffic Estimates Test Passed!")

if __name__ == "__main__":
    asyncio.run(test_traffic_estimates())
