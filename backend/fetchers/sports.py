"""
Sports Schedule Fetcher
Fetches upcoming games for Boston teams and user-defined interests using ESPN API.
"""
import aiohttp
from datetime import datetime, timedelta
import asyncio
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from database import SportsSchedule, SessionLocal
from config import SPORTS_TEAMS

logger = logging.getLogger("lighthouse")


async def fetch_team_schedule(league: str, sport: str, team_id: str, team_name: str) -> List[Dict[str, Any]]:
    """Fetch schedule for a specific team from ESPN API."""
    # Note: ESPN team IDs are numeric strings
    url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/teams/{team_id}/schedule"
    
    logger.info(f"[SPORTS] Fetching {team_name} schedule ({league})...")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    logger.warning(f"[WARN] Sports API error for {team_name}: HTTP {response.status}")
                    return []
                
                data = await response.json()
                events = data.get('events', [])
                
                games = []
                for event in events:
                    # Filter for future games only (or very recent ones)
                    game_time_str = event.get('date')
                    if not game_time_str:
                        continue
                        
                    game_time = datetime.strptime(game_time_str, "%Y-%m-%dT%H:%MZ")
                    
                    # Only keep games from today onwards
                    if game_time < datetime.utcnow() - timedelta(hours=12):
                        continue
                    
                    # Competition details
                    competitions = event.get('competitions', [])
                    if not competitions:
                        continue
                    
                    comp = competitions[0]
                    competitors = comp.get('competitors', [])
                    
                    opponent = "Unknown"
                    is_home = False
                    
                    for competitor in competitors:
                        comp_team = competitor.get('team', {})
                        if str(comp_team.get('id')) != str(team_id):
                            opponent = comp_team.get('displayName', "Unknown")
                        else:
                            is_home = competitor.get('homeAway') == 'home'
                    
                    venue_data = comp.get('venue', {})
                    venue = f"{venue_data.get('fullName', 'Unknown')}, {venue_data.get('address', {}).get('city', '')}"
                    
                    # Get broadcast info
                    broadcasts = comp.get('broadcasts', [])
                    broadcast = broadcasts[0].get('names', ['-'])[0] if broadcasts else "-"
                    
                    games.append({
                        'team': team_name,
                        'opponent': opponent,
                        'game_time': game_time,
                        'venue': venue,
                        'broadcast': broadcast,
                        'is_home': is_home,
                        'league': league.upper(),
                        'espn_id': event.get('id')
                    })
                    
                return games
                
    except Exception as e:
        logger.warning(f"[WARN] Sports fetch error for {team_name}: {e}")
        return []


async def fetch_all_sports() -> int:
    """Fetch schedules for all configured teams."""
    db = SessionLocal()
    total_added = 0
    
    try:
        # Clear old future games to keep schedule fresh
        db.query(SportsSchedule).filter(SportsSchedule.game_time > datetime.utcnow()).delete()
        
        all_games = []
        for team in SPORTS_TEAMS:
            games = await fetch_team_schedule(
                team['league'], 
                team['sport'], 
                team['id'], 
                team['name']
            )
            all_games.extend(games)
            await asyncio.sleep(1) # Be nice to the API
            
        for game_data in all_games:
            game = SportsSchedule(
                team=game_data['team'],
                opponent=game_data['opponent'],
                game_time=game_data['game_time'],
                venue=game_data['venue'],
                broadcast=game_data['broadcast'],
                is_home=game_data['is_home'],
                league=game_data['league'],
                espn_id=game_data['espn_id']
            )
            db.add(game)
            total_added += 1
            
        db.commit()
        logger.info(f"[OK] Updated sports schedule: {total_added} games found")
        return total_added
        
    finally:
        db.close()
