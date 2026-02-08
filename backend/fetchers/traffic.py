"""
Traffic Alert Fetcher
Fetches weather and traffic-impacting alerts for the configured location.
"""
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from database import TrafficAlert, TrafficRoute, SessionLocal
from config import (
    LOCATION_NAME, NWS_ZONE_CODES, 
    TRAFFIC_API_KEY, TRAFFIC_ROUTES_CONFIG
)

logger = logging.getLogger("lighthouse")


import re

def is_coordinates(text: str) -> bool:
    """Check if text is in 'lat,lon' format."""
    if not text:
        return False
    return bool(re.match(r'^-?\d+(\.\d+)?,-?\d+(\.\d+)?$', text.strip()))

async def geocode_address(session: aiohttp.ClientSession, address: str) -> Optional[str]:
    """Convert an address string to 'lat,lon' using TomTom Search API."""
    if not TRAFFIC_API_KEY or not address:
        return None
    
    # URL encode the address implicitly via params or manual formatting
    url = f"https://api.tomtom.com/search/2/geocode/{address}.json"
    params = {"key": TRAFFIC_API_KEY, "limit": 1}
    
    try:
        async with session.get(url, params=params) as response:
            if response.status != 200:
                err_text = await response.text()
                logger.warning(f"[TRAFFIC] Geocoding error for {address}: {response.status} - {err_text[:100]}")
                return None
            data = await response.json()
            results = data.get("results", [])
            if not results:
                logger.warning(f"[TRAFFIC] No geocoding results for {address}")
                return None
            
            pos = results[0].get("position", {})
            lat = pos.get("lat")
            lon = pos.get("lon")
            if lat is not None and lon is not None:
                return f"{lat},{lon}"
    except Exception as e:
        logger.warning(f"[TRAFFIC] Geocoding exception for {address}: {e}")
    
    return None

async def get_nws_zone_from_coords(session: aiohttp.ClientSession, lat: float, lon: float) -> Optional[str]:
    """Get the NWS public zone code for a given lat,lon."""
    url = f"https://api.weather.gov/points/{lat},{lon}"
    headers = {'User-Agent': 'Lighthouse/0.1 (personal-aggregator)'}
    
    try:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                return None
            data = await response.json()
            zone_url = data.get("properties", {}).get("forecastZone")
            if zone_url:
                # Extract zone code from URL (e.g., https://api.weather.gov/zones/forecast/MAZ005)
                return zone_url.split("/")[-1]
    except Exception as e:
        logger.warning(f"[TRAFFIC] Failed to catch NWS zone for {lat},{lon}: {e}")
    
    return None

def get_active_traffic_settings(db: Session = None) -> Dict[str, Any]:
    """Get traffic settings from UserSettings DB, falling back to config env vars."""
    local_db = False
    if db is None:
        db = SessionLocal()
        local_db = True
    
    try:
        from database import UserSettings
        settings = db.query(UserSettings).first()
        
        # Determine routes: UserSettings.traffic_routes OR TRAFFIC_ROUTES_CONFIG
        routes = TRAFFIC_ROUTES_CONFIG
        if settings and settings.traffic_routes:
            routes = settings.traffic_routes
            
        # Determine NWS Zone Codes
        zone_codes = NWS_ZONE_CODES
        if settings and settings.nws_zone_codes:
            zone_codes = settings.nws_zone_codes
            
        return {
            "routes": routes,
            "zone_codes": zone_codes,
            "location_name": settings.location_name if settings else LOCATION_NAME
        }
    finally:
        if local_db:
            db.close()

async def fetch_route_estimates(db: Session = None) -> tuple[int, List[str]]:
    """Fetch real-time commute estimates from TomTom Routing API. Returns (count, errors)."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True
 
    # Get active settings (DB-driven)
    settings = get_active_traffic_settings(db)
    routes_config = settings["routes"]
    
    if not TRAFFIC_API_KEY or not routes_config:
        logger.info("[TRAFFIC] Skipping route estimates (no API key or routes configured)")
        return 0, []
 
    total_updated = 0
    errors = []
    try:
        async with aiohttp.ClientSession() as session:
            for route_cfg in routes_config:
                name = route_cfg.get("name")
                origin_raw = route_cfg.get("origin")
                dest_raw = route_cfg.get("destination")
 
                if not origin_raw or not dest_raw:
                    continue
 
                # Resolve addresses to coordinates if needed and store them
                origin_lat, origin_lon = None, None
                if is_coordinates(origin_raw):
                    origin_lat, origin_lon = map(float, origin_raw.split(','))
                    origin = origin_raw
                else:
                    resolved = await geocode_address(session, origin_raw)
                    if resolved:
                        origin = resolved
                        origin_lat, origin_lon = map(float, origin.split(','))
                    else:
                        msg = f"Could not resolve origin: {origin_raw}"
                        logger.warning(f"[TRAFFIC] {msg}")
                        errors.append(msg)
                        continue
 
                dest_lat, dest_lon = None, None
                if is_coordinates(dest_raw):
                    dest_lat, dest_lon = map(float, dest_raw.split(','))
                    destination = dest_raw
                else:
                    resolved = await geocode_address(session, dest_raw)
                    if resolved:
                        destination = resolved
                        dest_lat, dest_lon = map(float, destination.split(','))
                    else:
                        msg = f"Could not resolve destination: {dest_raw}"
                        logger.warning(f"[TRAFFIC] {msg}")
                        errors.append(msg)
                        continue
 
                url = f"https://api.tomtom.com/routing/1/calculateRoute/{origin}:{destination}/json"
                params = {
                    "key": TRAFFIC_API_KEY,
                    "traffic": "true",
                    "travelMode": "car",
                    "departAt": "now"
                }
 
                try:
                    async with session.get(url, params=params) as response:
                        if response.status != 200:
                            err_text = await response.text()
                            msg = f"TomTom API level error for {name}: {response.status}"
                            logger.warning(f"[TRAFFIC] {msg} - {err_text[:100]}")
                            errors.append(msg)
                            continue
 
                        data = await response.json()
                        routes_data = data.get("routes", [])
                        if not routes_data:
                            continue
 
                        summary = routes_data[0].get("summary", {})
                        travel_time = summary.get("travelTimeInSeconds", 0)
                        delay = summary.get("trafficDelayInSeconds", 0)
                        
                        cur_duration = round(travel_time / 60)
                        delay_min = round(delay / 60)
                        typical_duration = cur_duration - delay_min
 
                        # Update or create database record
                        route = db.query(TrafficRoute).filter(TrafficRoute.name == name).first()
                        if not route:
                            route = TrafficRoute(name=name, origin=origin_raw, destination=dest_raw)
                            db.add(route)
 
                        route.current_duration_minutes = cur_duration
                        route.typical_duration_minutes = typical_duration
                        route.delay_minutes = delay_min
                        route.fetched_at = datetime.utcnow()
                        
                        # Save coords
                        route.origin_lat = origin_lat
                        route.origin_lon = origin_lon
                        route.dest_lat = dest_lat
                        route.dest_lon = dest_lon
                        
                        # Refresh zones if missing
                        if not route.origin_zone and origin_lat:
                            route.origin_zone = await get_nws_zone_from_coords(session, origin_lat, origin_lon)
                        if not route.dest_zone and dest_lat:
                            route.dest_zone = await get_nws_zone_from_coords(session, dest_lat, dest_lon)
                            
                        total_updated += 1
                except Exception as route_err:
                    msg = f"Error fetching route '{name}': {route_err}"
                    logger.warning(f"[TRAFFIC] {msg}")
                    errors.append(msg)
 
        db.commit()
        logger.info(f"[TRAFFIC] Updated {total_updated} route estimates")
        return total_updated, errors
 
    except Exception as e:
        msg = f"Fatal route fetch error: {e}"
        logger.warning(f"[TRAFFIC] {msg}")
        return 0, [msg]
    finally:
        if should_close:
            db.close()


async def fetch_traffic_alerts() -> tuple[int, List[str]]:
    """Fetch traffic-impacting alerts (Weather/NWS) and route estimates. Returns (count, errors)."""
    db = SessionLocal()
    errors = []
    try:
        # Get active settings
        settings = get_active_traffic_settings(db)
        zone_codes = settings["zone_codes"]
        location_name = settings["location_name"]
        
        # First, fetch route estimates
        _, route_errors = await fetch_route_estimates(db)
        errors.extend(route_errors)

        # Build list of unique zones to poll
        zones = set()
        if zone_codes:
            for z in zone_codes.split(','):
                zones.add(z.strip())
        
        # Add zones from active routes
        routes = db.query(TrafficRoute).all()
        for r in routes:
            if r.origin_zone: zones.add(r.origin_zone)
            if r.dest_zone: zones.add(r.dest_zone)
        
        if not zones:
            logger.info("[TRAFFIC] No zones to poll for alerts.")
            return 0
            
        combined_zones = ",".join(zones)
        url = f"https://api.weather.gov/alerts/active?zone={combined_zones}"
        
        logger.info(f"[CAR] Fetching traffic & weather alerts for {location_name} + route zones ({len(zones)} zones total)...")
        
        total_added = 0
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'User-Agent': 'Lighthouse/0.1 (personal-aggregator)'}) as response:
                if response.status != 200:
                    logger.warning(f"[WARN] NWS API error: HTTP {response.status}")
                    return 0
                
                data = await response.json()
                features = data.get('features', [])
                
                # Clear expired alerts
                db.query(TrafficAlert).filter(TrafficAlert.expires_at < datetime.utcnow()).delete()
                
                for feature in features:
                    props = feature.get('properties', {})
                    alert_id = props.get('id')
                    
                    if not alert_id:
                        continue
                        
                    # Check if already exists
                    existing = db.query(TrafficAlert).filter(TrafficAlert.description.contains(alert_id)).first()
                    if existing:
                        continue
                    
                    # Estimate which route it affects based on area
                    area = props.get('areaDesc', '')
                    severity = props.get('severity', 'Minor').lower()
                    
                    # Map severity to our internal scale
                    internal_severity = "minor"
                    if severity in ['severe', 'extreme']:
                        internal_severity = "major"
                    
                    alert = TrafficAlert(
                        route="Region-wide",
                        alert_type="Weather Alert",
                        description=f"{props.get('headline')}: {props.get('description')[:500]} (ID: {alert_id})",
                        severity=internal_severity,
                        location=area,
                        url=f"https://forecast.weather.gov/MapClick.php?zoneid={zone_codes.split(',')[0]}",
                        reported_at=datetime.fromisoformat(props.get('onset').replace('Z', '+00:00')) if props.get('onset') else datetime.utcnow(),
                        expires_at=datetime.fromisoformat(props.get('expires').replace('Z', '+00:00')) if props.get('expires') else datetime.utcnow() + timedelta(hours=4)
                    )
                    db.add(alert)
                    total_added += 1
                
                # Add a static "Commute Status" placeholder for now if no alerts AND no routes
                if total_added == 0 and db.query(TrafficAlert).count() == 0 and db.query(TrafficRoute).count() == 0:
                    commute_info = TrafficAlert(
                        route=f"{location_name} Commute",
                        alert_type="Commute Check",
                        description=f"Standard routes for {location_name} area appear clear.",
                        severity="minor",
                        location=location_name,
                        reported_at=datetime.utcnow(),
                        expires_at=datetime.utcnow() + timedelta(hours=2)
                    )
                    db.add(commute_info)
                    total_added += 1
                
                db.commit()
                logger.info(f"[OK] Added {total_added} alerts/status updates")
                return total_added, errors
                
    except Exception as e:
        msg = f"Traffic/Weather alert fetch error: {e}"
        logger.warning(f"[WARN] {msg}")
        return 0, errors + [msg]
    finally:
        db.close()
