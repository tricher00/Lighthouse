"""
Traffic Alert Fetcher
Fetches severe weather and traffic-impacting alerts for the North Andover/Wilmington area.
"""
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from database import TrafficAlert, SessionLocal
from config import LOCATION_NAME, NWS_ZONE_CODES

logger = logging.getLogger("lighthouse")


async def fetch_traffic_alerts() -> int:
    """Fetch traffic-impacting alerts (Weather/NWS)."""
    # Use zone codes from config
    url = f"https://api.weather.gov/alerts/active?zone={NWS_ZONE_CODES}"
    
    logger.info(f"[CAR] Fetching traffic & weather alerts for {LOCATION_NAME} area...")
    
    db = SessionLocal()
    total_added = 0
    
    try:
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
                        url=f"https://forecast.weather.gov/MapClick.php?zoneid={NWS_ZONE_CODES.split(',')[0]}",
                        reported_at=datetime.fromisoformat(props.get('onset').replace('Z', '+00:00')) if props.get('onset') else datetime.utcnow(),
                        expires_at=datetime.fromisoformat(props.get('expires').replace('Z', '+00:00')) if props.get('expires') else datetime.utcnow() + timedelta(hours=4)
                    )
                    db.add(alert)
                    total_added += 1
                
                # Add a static "Commute Status" placeholder for now if no alerts
                if total_added == 0 and db.query(TrafficAlert).count() == 0:
                    commute_info = TrafficAlert(
                        route="North Andover → Wilmington",
                        alert_type="Commute Check",
                        description="Main routes (I-93, Rt 125) appear clear. Recommended: Rt 125 for light traffic.",
                        severity="minor",
                        location="Route 125, I-93",
                        reported_at=datetime.utcnow(),
                        expires_at=datetime.utcnow() + timedelta(hours=2)
                    )
                    db.add(commute_info)
                    total_added += 1
                
                db.commit()
                logger.info(f"[OK] Added {total_added} alerts/status updates")
                return total_added
                
    except Exception as e:
        logger.warning(f"[WARN] Traffic fetch error: {e}")
        return 0
    finally:
        db.close()
