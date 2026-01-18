"""
Weather Fetcher (NWS)
Fetches weather data from the National Weather Service API (keyless).
"""
import aiohttp
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from database import WeatherData, SessionLocal
from config import LOCATION_LAT, LOCATION_LON, LOCATION_NAME

logger = logging.getLogger("lighthouse")

# NWS API requires a User-Agent
HEADERS = {
    'User-Agent': 'Lighthouse/1.0 (trich@example.com)'
}

def get_dress_suggestion(temp: float, conditions: str) -> str:
    """Generate a dress suggestion based on temperature and conditions."""
    conditions_lower = conditions.lower()
    
    if temp < 20:
        base = "Heavy winter coat, layers, hat, and gloves"
    elif temp < 32:
        base = "Winter coat, hat, and gloves"
    elif temp < 45:
        base = "Warm jacket or coat"
    elif temp < 55:
        base = "Light jacket or sweater"
    elif temp < 65:
        base = "Long sleeves or light layer"
    elif temp < 75:
        base = "T-shirt weather"
    elif temp < 85:
        base = "Light, breathable clothing"
    else:
        base = "Stay cool - minimal layers"
    
    if "rain" in conditions_lower or "drizzle" in conditions_lower:
        base += " - Bring an umbrella!"
    elif "snow" in conditions_lower:
        base += " - Watch for slippery conditions"
    elif "thunder" in conditions_lower:
        base += " - Stormy - stay indoors if possible"
    elif "wind" in conditions_lower:
        base += " - Windy - secure loose items"
    
    return base

async def fetch_nws_data(url: str) -> Optional[Dict[str, Any]]:
    """Helper to fetch JSON from NWS with retries."""
    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status == 200:
                    return await response.json()
                logger.warning(f"[WARN] NWS API error for {url}: HTTP {response.status}")
                return None
    except Exception as e:
        logger.warning(f"[WARN] NWS fetch error: {e}")
        return None

async def fetch_weather() -> Optional[Dict[str, Any]]:
    """Fetch current weather from National Weather Service."""
    logger.info(f"[WEATHER] Fetching NWS weather for {LOCATION_NAME}...")
    
    # 1. Get the points meta-data to find the forecast office and station
    points_url = f"https://api.weather.gov/points/{LOCATION_LAT},{LOCATION_LON}"
    points_data = await fetch_nws_data(points_url)
    if not points_data:
        return None
    
    properties = points_data.get('properties', {})
    forecast_url = properties.get('forecast')
    observation_stations_url = properties.get('observationStations')
    
    if not observation_stations_url or not forecast_url:
        return None

    # 2. Get the nearest observation station
    stations_data = await fetch_nws_data(observation_stations_url)
    if not stations_data or not stations_data.get('features'):
        return None
    
    station_id = stations_data['features'][0]['properties']['stationIdentifier']
    
    # 3. Get the latest observation from that station
    obs_url = f"https://api.weather.gov/stations/{station_id}/observations/latest"
    obs_data = await fetch_nws_data(obs_url)
    if not obs_data:
        return None
    
    obs_props = obs_data.get('properties', {})
    
    # NWS provides Celsius, we want Fahrenheit
    def c_to_f(c):
        return (c * 9/5) + 32 if c is not None else None

    temp_c = obs_props.get('temperature', {}).get('value')
    temp_f = c_to_f(temp_c)
    
    feels_like_c = obs_props.get('windChill', {}).get('value') or obs_props.get('heatIndex', {}).get('value') or temp_c
    feels_like_f = c_to_f(feels_like_c)
    
    conditions = obs_props.get('textDescription', 'Unknown')
    
    # 4. Get the highs and lows from the forecast URL
    forecast_data = await fetch_nws_data(forecast_url)
    high = None
    low = None
    if forecast_data:
        periods = forecast_data.get('properties', {}).get('periods', [])
        if periods:
            # First period is usually current/today
            high = periods[0].get('temperature') if periods[0].get('isDaytime') else None
            # Look for the upcoming low/high
            for p in periods[:2]:
                if p.get('isDaytime'):
                    high = high or p.get('temperature')
                else:
                    low = low or p.get('temperature')

    weather = {
        'temperature': temp_f,
        'feels_like': feels_like_f,
        'conditions': conditions,
        'icon': obs_props.get('icon'), # This is a URL, we'll handle it in JS if needed
        'humidity': obs_props.get('relativeHumidity', {}).get('value'),
        'wind_speed': (obs_props.get('windSpeed', {}).get('value') or 0) * 0.621371, # km/h to mph
        'high': high,
        'low': low,
        'dress_suggestion': get_dress_suggestion(temp_f, conditions) if temp_f is not None else "Unknown"
    }
    
    if temp_f is not None:
        logger.info(f"   [OK] {round(temp_f)}degF - {conditions}")
    return weather

async def fetch_and_save_weather() -> Optional[WeatherData]:
    """Fetch weather and save to database."""
    weather = await fetch_weather()
    if not weather or weather['temperature'] is None:
        return None
    
    db = SessionLocal()
    try:
        weather_record = WeatherData(
            temperature=weather['temperature'],
            feels_like=weather['feels_like'],
            conditions=weather['conditions'],
            icon=weather['icon'],
            humidity=weather['humidity'],
            wind_speed=weather['wind_speed'],
            high=weather['high'],
            low=weather['low'],
            dress_suggestion=weather['dress_suggestion'],
            fetched_at=datetime.utcnow()
        )
        db.add(weather_record)
        db.commit()
        db.refresh(weather_record)
        return weather_record
    finally:
        db.close()

def get_latest_weather() -> Optional[Dict[str, Any]]:
    """Get the most recent weather data from the database."""
    db = SessionLocal()
    try:
        weather = db.query(WeatherData).order_by(WeatherData.fetched_at.desc()).first()
        if not weather:
            return None
        
        return {
            'temperature': weather.temperature,
            'feels_like': weather.feels_like,
            'conditions': weather.conditions,
            'icon': weather.icon,
            'humidity': weather.humidity,
            'wind_speed': weather.wind_speed,
            'high': weather.high,
            'low': weather.low,
            'dress_suggestion': weather.dress_suggestion,
            'fetched_at': weather.fetched_at.isoformat() if weather.fetched_at else None
        }
    finally:
        db.close()
