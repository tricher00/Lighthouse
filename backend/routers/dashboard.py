"""
Dashboard API Router
Provides the main dashboard data endpoint.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db, Article, Source, Category, WeatherData, SportsSchedule, TrafficAlert
from config import LOCATION_NAME

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
async def get_dashboard(
    db: Session = Depends(get_db),
    include_read: bool = Query(False, description="Include already-read articles")
):
    """
    Get all dashboard data in a single request.
    This is the main endpoint for populating the UI.
    """
    
    # Get weather
    weather = db.query(WeatherData).order_by(desc(WeatherData.fetched_at)).first()
    weather_data = None
    if weather:
        weather_data = {
            "temperature": weather.temperature,
            "feels_like": weather.feels_like,
            "conditions": weather.conditions,
            "icon": weather.icon,
            "humidity": weather.humidity,
            "wind_speed": weather.wind_speed,
            "high": weather.high,
            "low": weather.low,
            "dress_suggestion": weather.dress_suggestion,
            "fetched_at": weather.fetched_at.isoformat() if weather.fetched_at else None
        }
    
    # Get traffic alerts
    traffic_alerts = db.query(TrafficAlert).filter(
        TrafficAlert.expires_at > datetime.utcnow()
    ).order_by(desc(TrafficAlert.reported_at)).limit(5).all()
    
    traffic_data = [
        {
            "id": alert.id,
            "route": alert.route,
            "type": alert.alert_type,
            "description": alert.description,
            "severity": alert.severity,
            "location": alert.location,
            "url": alert.url
        }
        for alert in traffic_alerts
    ]
    
    # Get upcoming games
    upcoming_games = db.query(SportsSchedule).filter(
        SportsSchedule.game_time > datetime.utcnow()
    ).order_by(SportsSchedule.game_time).limit(7).all()
    
    games_data = [
        {
            "id": game.id,
            "team": game.team,
            "opponent": game.opponent,
            "game_time": game.game_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "venue": game.venue,
            "broadcast": game.broadcast,
            "is_home": game.is_home,
            "league": game.league
        }
        for game in upcoming_games
    ]
    
    # Helper to deduplicate articles by similar titles
    def dedupe_by_title(articles: list, threshold: float = 0.6) -> list:
        """Remove articles with very similar titles (same story, different source)."""
        import re
        
        def normalize(title: str) -> set:
            # Extract significant words (ignore common words and source names)
            words = re.findall(r'\b[a-z]{3,}\b', title.lower())
            stopwords = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 
                        'can', 'had', 'her', 'was', 'one', 'our', 'out', 'has',
                        'have', 'been', 'from', 'they', 'will', 'would', 'there',
                        'their', 'what', 'about', 'which', 'when', 'make', 'like',
                        'time', 'just', 'know', 'take', 'people', 'into', 'year',
                        'your', 'good', 'some', 'could', 'them', 'than', 'then',
                        'now', 'look', 'only', 'come', 'over', 'such', 'with',
                        'news', 'report', 'says', 'said', 'after'}
            return set(w for w in words if w not in stopwords)
        
        def similarity(t1: str, t2: str) -> float:
            w1, w2 = normalize(t1), normalize(t2)
            if not w1 or not w2:
                return 0.0
            intersection = len(w1 & w2)
            return intersection / min(len(w1), len(w2))
        
        seen = []
        for article in articles:
            is_dupe = False
            for existing in seen:
                if similarity(article.title, existing.title) >= threshold:
                    is_dupe = True
                    break
            if not is_dupe:
                seen.append(article)
        return seen
    
    # Helper to get articles by category
    def get_articles_by_category(category: Category, limit: int = 8) -> List[Dict]:
        query = db.query(Article).join(Source).filter(
            Source.category == category,
            Article.is_rage_bait == False
        )
        
        if not include_read:
            query = query.filter(Article.is_read == False)
        
        # Fetch more than needed to allow for deduplication
        articles = query.order_by(desc(Article.published_at)).limit(limit * 2).all()
        
        # Deduplicate similar titles
        articles = dedupe_by_title(articles)[:limit]
        
        return [
            {
                "id": a.id,
                "title": a.title,
                "url": a.url,
                "author": a.author,
                "summary": a.summary,
                "summary_llm": a.summary_llm,
                "thumbnail": a.thumbnail,
                "source_name": a.source.name,
                "published_at": a.published_at.isoformat() if a.published_at else None,
                "is_read": a.is_read,
                "rating": a.rating,
                "metadata": a.meta_data
            }
            for a in articles
        ]
    
    # Compile article sections
    sections = {
        "boston_sports": get_articles_by_category(Category.BOSTON_SPORTS, 8),
        "other_teams": get_articles_by_category(Category.OTHER_TEAMS, 5),
        "league_wide": get_articles_by_category(Category.LEAGUE_WIDE, 5),
        "national_news": get_articles_by_category(Category.NATIONAL_NEWS, 8),
        "local_news": get_articles_by_category(Category.LOCAL_NEWS, 5),
        "long_form": get_articles_by_category(Category.LONG_FORM, 3),
        "movies": get_articles_by_category(Category.MOVIES, 5),
        "discovery": get_articles_by_category(Category.DISCOVERY, 3),
    }
    
    # Count totals
    total_unread = db.query(Article).filter(Article.is_read == False).count()
    
    # Get location name from UserSettings or fallback to config
    from database import UserSettings
    user_settings = db.query(UserSettings).first()
    location_name = user_settings.location_name if user_settings and user_settings.location_name else LOCATION_NAME
    
    return {
        "location_name": location_name,
        "weather": weather_data,
        "traffic": traffic_data,
        "games": games_data,
        "sections": sections,
        "stats": {
            "total_unread": total_unread,
            "fetched_at": datetime.utcnow().isoformat()
        }
    }


@router.get("/articles")
async def get_articles(
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None),
    source_id: Optional[int] = Query(None),
    unread_only: bool = Query(True),
    limit: int = Query(20, le=100),
    offset: int = Query(0)
):
    """Get articles with filtering options."""
    query = db.query(Article).join(Source)
    
    if category:
        try:
            cat = Category(category)
            query = query.filter(Source.category == cat)
        except ValueError:
            pass
    
    if source_id:
        query = query.filter(Article.source_id == source_id)
    
    if unread_only:
        query = query.filter(Article.is_read == False)
    
    # Exclude rage bait
    query = query.filter(Article.is_rage_bait == False)
    
    total = query.count()
    articles = query.order_by(desc(Article.published_at)).offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "articles": [
            {
                "id": a.id,
                "title": a.title,
                "url": a.url,
                "author": a.author,
                "summary": a.summary,
                "summary_llm": a.summary_llm,
                "thumbnail": a.thumbnail,
                "source_name": a.source.name,
                "source_category": a.source.category.value,
                "published_at": a.published_at.isoformat() if a.published_at else None,
                "is_read": a.is_read,
                "rating": a.rating,
                "metadata": a.meta_data
            }
            for a in articles
        ]
    }
