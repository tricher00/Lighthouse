import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
import json
from datetime import datetime
# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Use in-memory SQLite for tests to avoid disk I/O in sandbox
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from database import init_db, SessionLocal, TrafficRoute, TrafficAlert
from fetchers.traffic import (
    fetch_route_estimates,
    fetch_traffic_alerts,
    routes_within_time_margin,
    extract_road_names_from_route,
    aggregate_main_roads,
)


def test_routes_within_time_margin():
    """Unit test: filter route indices by time margin."""
    # Empty
    assert routes_within_time_margin([], 15) == []

    # Single route
    r1 = [{"summary": {"travelTimeInSeconds": 600}}]
    assert routes_within_time_margin(r1, 15) == [0]

    # Three routes: 600, 650 (within 15%), 800 (outside 15%). 15% of 600 = 90, max = 690
    r3 = [
        {"summary": {"travelTimeInSeconds": 600}},
        {"summary": {"travelTimeInSeconds": 650}},
        {"summary": {"travelTimeInSeconds": 800}},
    ]
    assert routes_within_time_margin(r3, 15) == [0, 1]
    assert routes_within_time_margin(r3, 0) == [0]
    assert routes_within_time_margin(r3, 50) == [0, 1, 2]

    # Edge: exactly 15% over = 690 sec
    r_edge = [
        {"summary": {"travelTimeInSeconds": 600}},
        {"summary": {"travelTimeInSeconds": 690}},
    ]
    assert routes_within_time_margin(r_edge, 15) == [0, 1]

    # Route with no summary is excluded from comparison (we only include indices that have times)
    r_partial = [
        {"summary": {"travelTimeInSeconds": 600}},
        {"summary": {}},
    ]
    # Only index 0 has a time, so fastest is 600, included_indices = {0}
    assert routes_within_time_margin(r_partial, 15) == [0]


def test_extract_road_names_from_route():
    """Unit test: extract road names from IMPORTANT_ROAD_STRETCH sections only."""
    # Empty
    assert extract_road_names_from_route({}) == []
    assert extract_road_names_from_route({"guidance": {}, "sections": []}) == []

    # Guidance instructions are now IGNORED (they include minor streets)
    # Only IMPORTANT_ROAD_STRETCH sections are used
    # roadNumbers can be dicts with 'text' field (TomTom format)
    r = {
        "guidance": {
            "instructions": [
                {"street": "Minor St", "roadNumbers": []},  # Should be ignored
            ]
        },
        "sections": [
            # Long stretch (50 points) - should be included
            {"sectionType": "IMPORTANT_ROAD_STRETCH", "streetName": "Main St", "startPointIndex": 0, "endPointIndex": 50},
            # Route numbers as dicts (TomTom format), long stretch (100 points)
            {"sectionType": "IMPORTANT_ROAD_STRETCH", "roadNumbers": [{"text": "I-93"}, {"text": "US-1"}], "startPointIndex": 50, "endPointIndex": 150},
            # Short stretch (10 points) - should be EXCLUDED by min length filter
            {"sectionType": "IMPORTANT_ROAD_STRETCH", "streetName": "Short Rd", "startPointIndex": 150, "endPointIndex": 160},
        ],
    }
    roads = extract_road_names_from_route(r)
    names = [road["name"] for road in roads]
    assert "Main St" in names
    assert "I-93, US-1" in names
    assert "Minor St" not in names  # Guidance is ignored
    assert "Short Rd" not in names  # Too short (< 20 points)
    assert len(roads) == 2


def test_aggregate_main_roads():
    """Unit test: aggregate_main_roads returns route alternatives with travel times and key roads."""
    # Route 1: 600s travel, 60s delay, Main St + Rt 125
    # Route 2: 650s travel, 0 delay, Main St only
    routes_data = [
        {
            "summary": {"travelTimeInSeconds": 600, "trafficDelayInSeconds": 60},
            "sections": [
                {"sectionType": "IMPORTANT_ROAD_STRETCH", "streetName": "Main St", "startPointIndex": 0, "endPointIndex": 50},
                {"sectionType": "IMPORTANT_ROAD_STRETCH", "roadNumbers": [{"text": "Rt 125"}], "startPointIndex": 50, "endPointIndex": 100},
            ]
        },
        {
            "summary": {"travelTimeInSeconds": 650, "trafficDelayInSeconds": 0},
            "sections": [
                {"sectionType": "IMPORTANT_ROAD_STRETCH", "streetName": "Main St", "startPointIndex": 0, "endPointIndex": 60},
            ]
        },
    ]
    within_indices = [0, 1]
    result = aggregate_main_roads(routes_data, within_indices)
    
    # Should return 2 route alternatives
    assert len(result) == 2
    
    # Fastest route should be first (route 1 with 10 min = 600s)
    fastest = result[0]
    assert fastest["travel_time_min"] == 10
    assert fastest["delay_min"] == 1
    assert fastest["is_fastest"] == True
    # Rt 125 should be in key_roads (Main St is common so excluded)
    assert "Rt 125" in fastest["key_roads"]
    
    # Second route should be slower
    second = result[1]
    assert second["travel_time_min"] == 11
    assert second["is_fastest"] == False
    assert second["time_vs_fastest"] == 1


def test_traffic_estimates():
    """Sync wrapper for async fetcher test."""
    asyncio.run(_test_traffic_estimates())


def _make_mock_response(json_data):
    mock_resp = MagicMock()
    mock_resp.status = 200
    async def mock_json():
        return json_data
    mock_resp.json = mock_json
    return mock_resp


async def _test_traffic_estimates():
    print("Starting Traffic Estimates Test...")
    
    init_db()
    db = SessionLocal()
    
    mock_geocode_response = {
        "results": [{"position": {"lat": 42.3601, "lon": -71.0589}}]
    }
    mock_routing_response = {
        "routes": [{
            "summary": {
                "travelTimeInSeconds": 1500,
                "trafficDelayInSeconds": 300
            }
        }]
    }
    
    test_routes = [
        {"name": "Coords Route", "origin": "1,1", "destination": "2,2"},
        {"name": "Address Route", "origin": "100 Main St, Boston", "destination": "MIT, Cambridge"}
    ]
    test_settings = {
        "routes": test_routes,
        "zone_codes": None,
        "location_name": "Test",
        "traffic_options": {"max_alternatives": 3, "time_margin_percent": 15}
    }
    
    # Response order: route (coords), NWS origin, NWS dest, geocode (origin), geocode (dest), route (address), NWS origin, NWS dest
    mock_nws_response = {"properties": {"forecastZone": "https://api.weather.gov/zones/forecast/MAZ005"}}
    responses = [
        _make_mock_response(mock_routing_response),
        _make_mock_response(mock_nws_response),
        _make_mock_response(mock_nws_response),
        _make_mock_response(mock_geocode_response),
        _make_mock_response(mock_geocode_response),
        _make_mock_response(mock_routing_response),
        _make_mock_response(mock_nws_response),
        _make_mock_response(mock_nws_response),
    ]
    
    with patch("fetchers.traffic.TRAFFIC_API_KEY", "fake_key"), \
         patch("fetchers.traffic.get_active_traffic_settings", return_value=test_settings), \
         patch("fetchers.traffic.fetch_route_incidents", new_callable=AsyncMock, return_value="Clear"), \
         patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.side_effect = responses
        
        updated, _ = await fetch_route_estimates(db)
        
        route1 = db.query(TrafficRoute).filter(TrafficRoute.name == "Coords Route").first()
        assert route1 is not None
        assert route1.current_duration_minutes == 25
        
        route2 = db.query(TrafficRoute).filter(TrafficRoute.name == "Address Route").first()
        assert route2 is not None
        assert route2.current_duration_minutes == 25
        assert route2.origin == "100 Main St, Boston"

    db.close()
    print("Traffic Estimates Test Passed!")


def test_traffic_estimates_multi_route_main_roads():
    """Fetcher integration: multi-route response, filter by margin, main_roads and alternatives_within_margin in DB."""
    asyncio.run(_test_traffic_estimates_multi_route_main_roads())


async def _test_traffic_estimates_multi_route_main_roads():
    init_db()
    db = SessionLocal()

    mock_geocode = {"results": [{"position": {"lat": 42.36, "lon": -71.06}}]}
    mock_routing = {
        "routes": [
            {
                "summary": {"travelTimeInSeconds": 600, "trafficDelayInSeconds": 60},
                "sections": [
                    # 50 points - passes min length filter
                    {"sectionType": "IMPORTANT_ROAD_STRETCH", "streetName": "Main St", "startPointIndex": 0, "endPointIndex": 50},
                    {"sectionType": "IMPORTANT_ROAD_STRETCH", "roadNumbers": [{"text": "Rt 125"}], "startPointIndex": 50, "endPointIndex": 100},
                ],
            },
            {
                "summary": {"travelTimeInSeconds": 650, "trafficDelayInSeconds": 50},
                "sections": [
                    {"sectionType": "IMPORTANT_ROAD_STRETCH", "streetName": "Main St", "startPointIndex": 0, "endPointIndex": 60},
                    {"sectionType": "IMPORTANT_ROAD_STRETCH", "streetName": "Elm St", "startPointIndex": 60, "endPointIndex": 100},
                ],
            },
            {
                "summary": {"travelTimeInSeconds": 800, "trafficDelayInSeconds": 100},
                "sections": [
                    {"sectionType": "IMPORTANT_ROAD_STRETCH", "streetName": "Other Rd", "startPointIndex": 0, "endPointIndex": 100},
                ],
            },
        ]
    }

    test_routes = [{"name": "Multi Route", "origin": "1,1", "destination": "2,2"}]
    test_settings = {
        "routes": test_routes,
        "zone_codes": None,
        "location_name": "Test",
        "traffic_options": {"max_alternatives": 3, "time_margin_percent": 15}
    }

    # One route call only (coords), so one response
    resp = _make_mock_response(mock_routing)

    with patch("fetchers.traffic.TRAFFIC_API_KEY", "key"), \
         patch("fetchers.traffic.get_active_traffic_settings", return_value=test_settings), \
         patch("fetchers.traffic.fetch_route_incidents", new_callable=AsyncMock, return_value="Clear conditions"), \
         patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.side_effect = [resp]

        updated, _ = await fetch_route_estimates(db)

    assert updated == 1
    route = db.query(TrafficRoute).filter(TrafficRoute.name == "Multi Route").first()
    assert route is not None
    assert route.current_duration_minutes == 10  # 600s
    assert route.alternatives_within_margin == 2
    main_roads = route.main_roads or []
    
    # New format: list of route alternatives with travel times and key roads
    assert len(main_roads) == 2  # 2 routes within margin
    
    # First should be fastest (10 min)
    fastest = main_roads[0]
    assert fastest["travel_time_min"] == 10
    assert fastest["is_fastest"] == True
    # Should have key roads (Rt 125 is unique to this route, Main St is common)
    assert "key_roads" in fastest
    
    # Second should be slower (11 min)
    second = main_roads[1]
    assert second["travel_time_min"] == 11  # 650s rounded
    assert second["is_fastest"] == False

    db.close()
    print("Multi-route main roads test passed!")


if __name__ == "__main__":
    test_routes_within_time_margin()
    test_extract_road_names_from_route()
    test_aggregate_main_roads()
    print("Unit tests passed!")
    test_traffic_estimates()
    test_traffic_estimates_multi_route_main_roads()
