"""
Settings API Router
Handles user settings for location, weather zones, and sports teams.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, UserSettings

router = APIRouter(prefix="/api/settings", tags=["settings"])


class LocationSettings(BaseModel):
    location_name: str
    location_lat: float
    location_lon: float
    nws_zone_codes: str


class SportsTeam(BaseModel):
    name: str
    league: str
    sport: str
    espn_id: str


class TrafficRouteUpdate(BaseModel):
    name: str
    origin: str  # Address or lat,lon
    destination: str  # Address or lat,lon


class SettingsUpdate(BaseModel):
    location: Optional[LocationSettings] = None
    sports_teams: Optional[List[SportsTeam]] = None
    traffic_routes: Optional[List[TrafficRouteUpdate]] = None


@router.get("")
async def get_settings(db: Session = Depends(get_db)):
    """Get current user settings."""
    settings = db.query(UserSettings).first()
    
    if not settings:
        # Return defaults from config
        from config import LOCATION_NAME, LOCATION_LAT, LOCATION_LON, NWS_ZONE_CODES, SPORTS_TEAMS
        return {
            "location": {
                "name": LOCATION_NAME,
                "lat": LOCATION_LAT,
                "lon": LOCATION_LON,
                "nws_zone_codes": NWS_ZONE_CODES
            },
            "sports_teams": SPORTS_TEAMS
        }
    
    return {
        "location": {
            "name": settings.location_name,
            "lat": settings.location_lat,
            "lon": settings.location_lon,
            "nws_zone_codes": settings.nws_zone_codes
        },
        "sports_teams": settings.sports_teams or [],
        "traffic_routes": settings.traffic_routes or []
    }


@router.put("")
async def update_settings(update: SettingsUpdate, db: Session = Depends(get_db)):
    """Update user settings."""
    settings = db.query(UserSettings).first()
    
    if not settings:
        # Create new settings record
        from config import LOCATION_NAME, LOCATION_LAT, LOCATION_LON, NWS_ZONE_CODES, SPORTS_TEAMS
        settings = UserSettings(
            location_name=LOCATION_NAME,
            location_lat=LOCATION_LAT,
            location_lon=LOCATION_LON,
            nws_zone_codes=NWS_ZONE_CODES,
            sports_teams=SPORTS_TEAMS
        )
        db.add(settings)
    
    if update.location:
        settings.location_name = update.location.location_name
        settings.location_lat = update.location.location_lat
        settings.location_lon = update.location.location_lon
        settings.nws_zone_codes = update.location.nws_zone_codes
    
    if update.sports_teams is not None:
        settings.sports_teams = [t.model_dump() for t in update.sports_teams]
    
    if update.traffic_routes is not None:
        settings.traffic_routes = [r.model_dump() for r in update.traffic_routes]
    
    db.commit()
    db.refresh(settings)
    
    return {"success": True, "message": "Settings updated"}


@router.post("/refresh")
async def refresh_data():
    """Trigger immediate refresh of weather and sports data."""
    import asyncio
    from fetchers.weather import fetch_and_save_weather
    from fetchers.sports import fetch_all_sports
    from fetchers.traffic import fetch_traffic_alerts
    
    results = {"weather": False, "sports": False, "traffic": False}
    
    try:
        # Fetch weather with new location
        weather = await fetch_and_save_weather()
        results["weather"] = weather is not None
    except Exception as e:
        print(f"Weather refresh error: {e}")
    
    try:
        # Fetch sports with new teams
        sports_count = await fetch_all_sports()
        results["sports"] = sports_count > 0
    except Exception as e:
        print(f"Sports refresh error: {e}")

    traffic_errors = []
    try:
        # Fetch traffic with new routes or location
        traffic_count, traffic_errors = await fetch_traffic_alerts()
        results["traffic"] = traffic_count >= 0
    except Exception as e:
        print(f"Traffic refresh error: {e}")
        traffic_errors.append(str(e))
    
    return {
        "success": True, 
        "refreshed": results,
        "errors": {
            "traffic": traffic_errors
        }
    }


@router.get("/teams/search")
async def search_teams(q: str):
    """Search for ESPN teams by name."""
    if len(q) < 2:
        return {"teams": []}
    
    # Common teams database (expandable)
    # Format: name, league, sport, espn_id
    all_teams = [
        # NBA
        {"name": "Lakers", "league": "nba", "sport": "basketball", "espn_id": "13"},
        {"name": "Celtics", "league": "nba", "sport": "basketball", "espn_id": "2"},
        {"name": "Warriors", "league": "nba", "sport": "basketball", "espn_id": "9"},
        {"name": "Knicks", "league": "nba", "sport": "basketball", "espn_id": "18"},
        {"name": "Bulls", "league": "nba", "sport": "basketball", "espn_id": "4"},
        {"name": "Heat", "league": "nba", "sport": "basketball", "espn_id": "14"},
        {"name": "Nets", "league": "nba", "sport": "basketball", "espn_id": "17"},
        {"name": "76ers", "league": "nba", "sport": "basketball", "espn_id": "20"},
        {"name": "Bucks", "league": "nba", "sport": "basketball", "espn_id": "15"},
        {"name": "Mavericks", "league": "nba", "sport": "basketball", "espn_id": "6"},
        # NFL
        {"name": "Patriots", "league": "nfl", "sport": "football", "espn_id": "17"},
        {"name": "Cowboys", "league": "nfl", "sport": "football", "espn_id": "6"},
        {"name": "Chiefs", "league": "nfl", "sport": "football", "espn_id": "12"},
        {"name": "Eagles", "league": "nfl", "sport": "football", "espn_id": "21"},
        {"name": "49ers", "league": "nfl", "sport": "football", "espn_id": "25"},
        {"name": "Bills", "league": "nfl", "sport": "football", "espn_id": "2"},
        {"name": "Packers", "league": "nfl", "sport": "football", "espn_id": "9"},
        {"name": "Giants", "league": "nfl", "sport": "football", "espn_id": "19"},
        {"name": "Jets", "league": "nfl", "sport": "football", "espn_id": "20"},
        {"name": "Dolphins", "league": "nfl", "sport": "football", "espn_id": "15"},
        # MLB
        {"name": "Yankees", "league": "mlb", "sport": "baseball", "espn_id": "10"},
        {"name": "Red Sox", "league": "mlb", "sport": "baseball", "espn_id": "2"},
        {"name": "Dodgers", "league": "mlb", "sport": "baseball", "espn_id": "19"},
        {"name": "Cubs", "league": "mlb", "sport": "baseball", "espn_id": "16"},
        {"name": "Mets", "league": "mlb", "sport": "baseball", "espn_id": "21"},
        {"name": "Braves", "league": "mlb", "sport": "baseball", "espn_id": "15"},
        {"name": "Astros", "league": "mlb", "sport": "baseball", "espn_id": "18"},
        {"name": "Phillies", "league": "mlb", "sport": "baseball", "espn_id": "22"},
        # NHL
        {"name": "Bruins", "league": "nhl", "sport": "hockey", "espn_id": "1"},
        {"name": "Rangers", "league": "nhl", "sport": "hockey", "espn_id": "13"},
        {"name": "Maple Leafs", "league": "nhl", "sport": "hockey", "espn_id": "28"},
        {"name": "Canadiens", "league": "nhl", "sport": "hockey", "espn_id": "15"},
        {"name": "Blackhawks", "league": "nhl", "sport": "hockey", "espn_id": "4"},
        {"name": "Penguins", "league": "nhl", "sport": "hockey", "espn_id": "23"},
        {"name": "Capitals", "league": "nhl", "sport": "hockey", "espn_id": "27"},
        {"name": "Devils", "league": "nhl", "sport": "hockey", "espn_id": "17"},
    ]
    
    q_lower = q.lower()
    matches = [t for t in all_teams if q_lower in t["name"].lower()]
    
    return {"teams": matches[:10]}


@router.get("/location/search")
async def search_location(q: str):
    """Search for a city/location and return coordinates using Nominatim."""
    import aiohttp
    
    if len(q) < 3:
        return {"locations": []}
    
    try:
        async with aiohttp.ClientSession() as session:
            # Nominatim is free and doesn't require an API key
            url = f"https://nominatim.openstreetmap.org/search"
            params = {
                "q": q,
                "format": "json",
                "limit": 5,
                "addressdetails": 1
            }
            headers = {"User-Agent": "Lighthouse/1.0"}
            
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    results = []
                    for item in data:
                        display = item.get("display_name", "").split(",")
                        # Create a shorter display name
                        short_name = ", ".join(display[:3]) if len(display) >= 3 else item.get("display_name", "")
                        results.append({
                            "name": short_name,
                            "full_name": item.get("display_name", ""),
                            "lat": float(item.get("lat", 0)),
                            "lon": float(item.get("lon", 0))
                        })
                    return {"locations": results}
    except Exception as e:
        print(f"Location search error: {e}")
    
    return {"locations": []}


# ============================================
# Reader Mode Settings
# ============================================

class ReaderSettingsUpdate(BaseModel):
    cache_hours: Optional[int] = None
    theme: Optional[str] = None  # auto, light, dark


@router.get("/reader")
async def get_reader_settings(db: Session = Depends(get_db)):
    """Get reader mode settings."""
    settings = db.query(UserSettings).first()
    
    if not settings:
        return {
            "blacklisted_sources": [],
            "cache_hours": 24,
            "theme": "auto"
        }
    
    return {
        "blacklisted_sources": settings.reader_blacklisted_sources or [],
        "cache_hours": settings.reader_cache_hours or 24,
        "theme": settings.reader_theme or "auto"
    }


@router.put("/reader")
async def update_reader_settings(update: ReaderSettingsUpdate, db: Session = Depends(get_db)):
    """Update reader mode settings."""
    settings = db.query(UserSettings).first()
    
    if not settings:
        settings = UserSettings()
        db.add(settings)
    
    if update.cache_hours is not None:
        settings.reader_cache_hours = update.cache_hours
    if update.theme is not None:
        if update.theme not in ["auto", "light", "dark"]:
            raise HTTPException(status_code=400, detail="Theme must be 'auto', 'light', or 'dark'")
        settings.reader_theme = update.theme
    
    db.commit()
    return {"success": True, "message": "Reader settings updated"}


@router.post("/reader/blacklist/{source_id}")
async def add_to_reader_blacklist(source_id: int, db: Session = Depends(get_db)):
    """Add a source to the reader mode blacklist."""
    settings = db.query(UserSettings).first()
    
    if not settings:
        settings = UserSettings(reader_blacklisted_sources=[source_id])
        db.add(settings)
    else:
        blacklist = settings.reader_blacklisted_sources or []
        if source_id not in blacklist:
            blacklist.append(source_id)
            settings.reader_blacklisted_sources = blacklist
    
    db.commit()
    return {"success": True, "message": f"Source {source_id} added to blacklist"}


@router.delete("/reader/blacklist/{source_id}")
async def remove_from_reader_blacklist(source_id: int, db: Session = Depends(get_db)):
    """Remove a source from the reader mode blacklist."""
    settings = db.query(UserSettings).first()
    
    if settings and settings.reader_blacklisted_sources:
        blacklist = settings.reader_blacklisted_sources
        if source_id in blacklist:
            blacklist.remove(source_id)
            settings.reader_blacklisted_sources = blacklist
            db.commit()
            return {"success": True, "message": f"Source {source_id} removed from blacklist"}
    
    return {"success": False, "message": f"Source {source_id} not in blacklist"}

