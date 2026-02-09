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
        async with session.get(url, params=params, ssl=False) as response:
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

# Icon category to human-readable type mapping
INCIDENT_TYPES = {
    0: "Unknown",
    1: "Accident",
    2: "Fog",
    3: "Dangerous Conditions",
    4: "Rain",
    5: "Ice",
    6: "Jam",
    7: "Lane Closed",
    8: "Road Closed",
    9: "Road Works",
    10: "Wind",
    11: "Flooding",
    14: "Broken Down Vehicle"
}

async def fetch_route_incidents(session: aiohttp.ClientSession, 
                                 origin_lat: float, origin_lon: float,
                                 dest_lat: float, dest_lon: float) -> str:
    """Fetch traffic incidents along a route using bounding box. Returns summary string."""
    if not TRAFFIC_API_KEY:
        return ""
    
    # Create bounding box with some padding (0.05 degrees ~= 3-5 miles)
    padding = 0.05
    min_lat = min(origin_lat, dest_lat) - padding
    max_lat = max(origin_lat, dest_lat) + padding
    min_lon = min(origin_lon, dest_lon) - padding
    max_lon = max(origin_lon, dest_lon) + padding
    
    bbox = f"{min_lon},{min_lat},{max_lon},{max_lat}"
    
    # Request incident details with key fields
    url = f"https://api.tomtom.com/traffic/services/5/incidentDetails"
    params = {
        "key": TRAFFIC_API_KEY,
        "bbox": bbox,
        "fields": "{incidents{properties{iconCategory,magnitudeOfDelay,from,to,delay,roadNumbers,events{description}}}}",
        "language": "en-US"
    }
    
    try:
        async with session.get(url, params=params, ssl=False) as response:
            if response.status != 200:
                return ""
            
            data = await response.json()
            incidents = data.get("incidents", [])
            
            if not incidents:
                return "Clear conditions"
            
            # Summarize incidents - focus on most significant
            summaries = []
            for inc in incidents[:3]:  # Top 3 incidents
                props = inc.get("properties", {})
                icon_cat = props.get("iconCategory", 0)
                incident_type = INCIDENT_TYPES.get(icon_cat, "Issue")
                
                road_from = props.get("from", "")
                road_to = props.get("to", "")
                road_nums = props.get("roadNumbers", [])
                delay_sec = props.get("delay", 0)
                
                # Build location string
                location = ""
                if road_nums:
                    location = ", ".join(road_nums)
                elif road_from:
                    location = road_from
                
                # Build summary
                if delay_sec and delay_sec > 60:
                    delay_min = round(delay_sec / 60)
                    summaries.append(f"{incident_type} on {location} (+{delay_min}min)" if location else f"{incident_type} (+{delay_min}min)")
                elif location:
                    summaries.append(f"{incident_type} on {location}")
                else:
                    summaries.append(incident_type)
            
            return "; ".join(summaries) if summaries else "Minor congestion"
            
    except Exception as e:
        logger.warning(f"[TRAFFIC] Incidents fetch error: {e}")
        return ""

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
            
        # Determine NWS Zone Codes - only use config default if user has no location set
        # If user has a location but no explicit zones, we'll rely on route zones instead
        zone_codes = None
        if settings and settings.nws_zone_codes:
            zone_codes = settings.nws_zone_codes
        elif not settings or not settings.location_name:
            # No user settings at all - use env default
            zone_codes = NWS_ZONE_CODES
            
        # Traffic options for alternative routes and time margin (defaults if missing)
        traffic_options = (settings.traffic_options or {}) if settings else {}
        if not isinstance(traffic_options, dict):
            traffic_options = {}
        traffic_options.setdefault("max_alternatives", 3)
        traffic_options.setdefault("time_margin_percent", 15)
        traffic_options["max_alternatives"] = min(5, max(1, int(traffic_options["max_alternatives"])))
        traffic_options["time_margin_percent"] = min(50, max(5, int(traffic_options["time_margin_percent"])))

        return {
            "routes": routes,
            "zone_codes": zone_codes,
            "location_name": settings.location_name if settings else LOCATION_NAME,
            "traffic_options": traffic_options
        }
    finally:
        if local_db:
            db.close()


def routes_within_time_margin(
    routes_data: List[Dict[str, Any]], time_margin_percent: int
) -> List[int]:
    """
    Return indices of routes whose travelTimeInSeconds is within time_margin_percent of the fastest.
    routes_data: list of route dicts with summary.travelTimeInSeconds.
    time_margin_percent: e.g. 15 means within 15% of fastest (inclusive).
    Always includes index 0 (fastest).
    """
    if not routes_data:
        return []
    times = []
    for i, r in enumerate(routes_data):
        summary = r.get("summary") or {}
        t = summary.get("travelTimeInSeconds")
        if t is not None:
            times.append((i, t))
    if not times:
        return [0] if routes_data else []
    times.sort(key=lambda x: x[1])
    fastest_sec = times[0][1]
    if fastest_sec <= 0:
        return list(range(len(routes_data)))
    max_sec = fastest_sec * (1 + time_margin_percent / 100.0)
    included_indices = {idx for idx, t in times if t <= max_sec}
    return sorted(i for i in range(len(routes_data)) if i in included_indices)


def extract_road_names_from_route(route_obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract important road stretches from a single route.
    Returns list of dicts with {name, length_estimate} for major roads only (from importantRoadStretch sections).
    Turn-by-turn guidance is ignored since it includes every minor street.
    """
    roads = []
    seen_keys = set()
    
    # Only extract from IMPORTANT_ROAD_STRETCH sections - these are the major roads
    for section in route_obj.get("sections") or []:
        if section.get("sectionType") != "IMPORTANT_ROAD_STRETCH":
            continue
        
        start_idx = section.get("startPointIndex", 0)
        end_idx = section.get("endPointIndex", start_idx)
        
        # Estimate length from point indices
        length_estimate = max(1, end_idx - start_idx)
        
        # Get road name from streetName or roadNumbers
        # Both can be dicts with 'text' field or strings
        street_name_raw = section.get("streetName", "")
        road_numbers = section.get("roadNumbers") or []
        
        # streetName can be dict like {"text": "Main St"} or a string
        if isinstance(street_name_raw, dict):
            street_name = street_name_raw.get("text", "")
        else:
            street_name = str(street_name_raw).strip() if street_name_raw else ""
        
        # Extract text from roadNumbers (may be dict or string)
        road_num_texts = []
        for rn in road_numbers:
            if isinstance(rn, dict):
                road_num_texts.append(rn.get("text", str(rn)))
            else:
                road_num_texts.append(str(rn))
        
        # Prefer highway/route numbers over street names for display
        display_name = ""
        if road_num_texts:
            display_name = ", ".join(road_num_texts[:2])  # Limit to 2 route numbers
        elif street_name:
            display_name = street_name.strip()
        
        # Skip very short stretches (less than 20 points ~ less than ~1 mile)
        if length_estimate < 20:
            continue
        
        if display_name and display_name.lower() not in seen_keys:
            seen_keys.add(display_name.lower())
            roads.append({
                "name": display_name,
                "length_estimate": length_estimate
            })
    
    # Sort by length (longest stretches first = main roads)
    roads.sort(key=lambda x: -x["length_estimate"])
    
    return roads


def aggregate_main_roads(
    routes_data: List[Dict[str, Any]],
    within_margin_indices: List[int],
    primary_delay_minutes: Optional[int] = None,
    primary_notes: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Build route alternatives list showing each route option with its travel time and key roads.
    Returns: [{travel_time_min, delay_min, is_fastest, key_roads: [road names]}]
    """
    total_routes = len(within_margin_indices)
    if total_routes == 0:
        return []
    
    # First, collect all roads per route and their times
    routes_info = []
    for idx in within_margin_indices:
        if idx >= len(routes_data):
            continue
        route = routes_data[idx]
        summary = route.get("summary", {})
        travel_time = round(summary.get("travelTimeInSeconds", 0) / 60)
        delay = round(summary.get("trafficDelayInSeconds", 0) / 60)
        
        road_list = extract_road_names_from_route(route)
        # Just get road names, sorted by length (key roads first)
        road_names = [r["name"] for r in road_list[:3]]  # Top 3 key roads
        
        routes_info.append({
            "travel_time_min": travel_time,
            "delay_min": delay,
            "roads": road_names,
            "road_set": set(r.lower() for r in road_names)
        })
    
    if not routes_info:
        return []
    
    # Find fastest time
    min_time = min(r["travel_time_min"] for r in routes_info)
    
    # Find roads common to ALL routes (to exclude)
    if len(routes_info) > 1:
        common_roads = routes_info[0]["road_set"]
        for r in routes_info[1:]:
            common_roads = common_roads & r["road_set"]
    else:
        common_roads = set()
    
    # Build result with unique identifying roads for each route
    result = []
    for i, r in enumerate(routes_info):
        # Get roads that distinguish this route (not in all routes)
        unique_roads = [name for name in r["roads"] if name.lower() not in common_roads]
        # Fall back to all roads if none are unique (single route case)
        display_roads = unique_roads[:2] if unique_roads else r["roads"][:2]
        
        is_fastest = r["travel_time_min"] == min_time
        delta = r["travel_time_min"] - min_time
        
        entry = {
            "route_num": i + 1,
            "travel_time_min": r["travel_time_min"],
            "delay_min": r["delay_min"],
            "is_fastest": is_fastest,
            "time_vs_fastest": delta,
            "key_roads": display_roads,
            "status": None
        }
        
        # Check for incidents mentioning these roads
        if primary_notes:
            for road in display_roads:
                if road.lower() in primary_notes.lower():
                    entry["status"] = primary_notes[:100] if len(primary_notes) > 100 else primary_notes
                    break
        
        result.append(entry)
    
    # Sort by travel time so fastest is first
    result.sort(key=lambda x: x["travel_time_min"])
    return result

async def fetch_route_estimates(db: Session = None) -> tuple[int, List[str]]:
    """Fetch real-time commute estimates from TomTom Routing API. Returns (count, errors)."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True
 
    # Get active settings (DB-driven)
    settings = get_active_traffic_settings(db)
    routes_config = settings["routes"]
    traffic_options = settings.get("traffic_options") or {}
    # User's max_alternatives is the TOTAL routes they want to see
    # TomTom's maxAlternatives param is NUMBER OF ALTERNATIVES (excludes primary)
    # So if user wants 3 total, we pass 2 to TomTom (1 primary + 2 alternatives = 3)
    total_routes_wanted = min(5, max(1, traffic_options.get("max_alternatives", 3)))
    max_alternatives_param = max(0, total_routes_wanted - 1)
    time_margin_percent = min(50, max(5, traffic_options.get("time_margin_percent", 15)))

    if not TRAFFIC_API_KEY or not routes_config:
        logger.info("[TRAFFIC] Skipping route estimates (no API key or routes configured)")
        return 0, []
 
    # Get list of configured route names and clean up stale routes
    configured_names = {r.get("name") for r in routes_config if r.get("name")}
    stale_routes = db.query(TrafficRoute).filter(~TrafficRoute.name.in_(configured_names)).all()
    if stale_routes:
        for stale in stale_routes:
            db.delete(stale)
        db.commit()
        logger.info(f"[TRAFFIC] Removed {len(stale_routes)} stale route(s)")

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
                    "departAt": "now",
                    "maxAlternatives": max_alternatives_param,
                    "sectionType": ["importantRoadStretch", "traffic"],
                    "instructionsType": "text"
                }
 
                try:
                    async with session.get(url, params=params, ssl=False) as response:
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

                        # Fetch incident details for this route FIRST
                        traffic_notes = ""
                        if origin_lat and dest_lat:
                            traffic_notes = await fetch_route_incidents(
                                session, origin_lat, origin_lon, dest_lat, dest_lon
                            )

                        # Filter routes within time margin and build main roads
                        within_indices = routes_within_time_margin(routes_data, time_margin_percent)
                        alternatives_within_margin = len(within_indices)
                        main_roads_list: List[Dict[str, Any]] = []
                        if within_indices:
                            # Pass traffic notes so roads with incidents get status attached
                            main_roads_list = aggregate_main_roads(
                                routes_data, within_indices,
                                primary_delay_minutes=delay_min if delay_min else None,
                                primary_notes=traffic_notes if traffic_notes else None
                            )
 
                        # Update or create database record
                        route = db.query(TrafficRoute).filter(TrafficRoute.name == name).first()
                        if not route:
                            route = TrafficRoute(name=name, origin=origin_raw, destination=dest_raw)
                            db.add(route)
 
                        route.current_duration_minutes = cur_duration
                        route.typical_duration_minutes = typical_duration
                        route.delay_minutes = delay_min
                        route.main_roads = main_roads_list
                        route.alternatives_within_margin = alternatives_within_margin
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
                        
                        # Store traffic notes in DB
                        route.traffic_notes = traffic_notes
                            
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
                        url=f"https://forecast.weather.gov/MapClick.php?zoneid={combined_zones.split(',')[0]}",
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
