"""
RSS Feed Fetcher
Fetches and parses RSS feeds from configured sources.
"""
import asyncio
import logging
from datetime import datetime
from typing import List, Optional
import aiohttp
import feedparser
from sqlalchemy.orm import Session

from database import Source, Article, SourceType, get_db, SessionLocal
from config import (
    MAX_ARTICLES_PER_SOURCE, RAGE_BAIT_KEYWORDS,
    ATHLETIC_USERNAME, ATHLETIC_PASSWORD
)
import base64

logger = logging.getLogger("lighthouse")


def is_rage_bait(title: str) -> bool:
    """Check if a title contains rage-bait keywords."""
    title_upper = title.upper()
    return any(keyword.upper() in title_upper for keyword in RAGE_BAIT_KEYWORDS)


def parse_date(entry) -> Optional[datetime]:
    """Parse date from a feedparser entry."""
    date_fields = ['published_parsed', 'updated_parsed', 'created_parsed']
    for field in date_fields:
        parsed = getattr(entry, field, None)
        if parsed:
            try:
                return datetime(*parsed[:6])
            except (TypeError, ValueError):
                continue
    return None


def get_thumbnail(entry) -> Optional[str]:
    """Extract thumbnail URL from a feedparser entry."""
    # Check for media:thumbnail
    media_content = getattr(entry, 'media_content', [])
    if media_content:
        return media_content[0].get('url')
    
    # Check for media:thumbnail
    media_thumbnail = getattr(entry, 'media_thumbnail', [])
    if media_thumbnail:
        return media_thumbnail[0].get('url')
    
    # Check for enclosure
    enclosures = getattr(entry, 'enclosures', [])
    for enc in enclosures:
        if enc.get('type', '').startswith('image'):
            return enc.get('href') or enc.get('url')
    
    return None


async def fetch_feed(url: str, auth_headers: dict = None, timeout: int = 30) -> Optional[feedparser.FeedParserDict]:
    """Fetch and parse an RSS feed."""
    try:
        headers = {'User-Agent': 'Lighthouse/0.1 (personal-aggregator)'}
        if auth_headers:
            headers.update(auth_headers)
            
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status != 200:
                    logger.warning(f"[WARN] Failed to fetch {url}: HTTP {response.status}")
                    return None
                
                content = await response.read()
                return feedparser.parse(content)
    except asyncio.TimeoutError:
        logger.warning(f"[WARN] Timeout fetching {url}")
        return None
    except Exception as e:
        logger.warning(f"[WARN] Error fetching {url}: {e}")
        return None


async def fetch_rss_source(source: Source, db: Session) -> int:
    """
    Fetch articles from a single RSS source.
    Returns the number of new articles added.
    """
    logger.info(f"[FETCH] Fetching RSS: {source.name}")
    
    auth_headers = {}
    if "theathletic.com" in source.url and ATHLETIC_USERNAME and ATHLETIC_PASSWORD:
        # Basic Auth is a common standard for protected RSS feeds
        auth_string = f"{ATHLETIC_USERNAME}:{ATHLETIC_PASSWORD}"
        base64_auth = base64.b64encode(auth_string.encode()).decode()
        auth_headers["Authorization"] = f"Basic {base64_auth}"
        # Some sites also check Referer
        auth_headers["Referer"] = "https://theathletic.com/"
    
    feed = await fetch_feed(source.url, auth_headers=auth_headers)
    if not feed or not feed.entries:
        source.fetch_error = "No entries found or feed unavailable"
        source.last_fetched = datetime.utcnow()
        db.commit()
        return 0
    
    new_count = 0
    entries = feed.entries[:MAX_ARTICLES_PER_SOURCE]
    
    for entry in entries:
        url = entry.get('link', '')
        if not url:
            continue
        
        # Check if article already exists
        existing = db.query(Article).filter(Article.url == url).first()
        if existing:
            continue
        
        title = entry.get('title', 'Untitled')
        
        # Extract summary/description
        summary = None
        if hasattr(entry, 'summary'):
            summary = entry.summary
        elif hasattr(entry, 'description'):
            summary = entry.description
        
        # Clean HTML from summary if present
        if summary and '<' in summary:
            from bs4 import BeautifulSoup
            summary = BeautifulSoup(summary, 'lxml').get_text()[:500]
        
        article = Article(
            source_id=source.id,
            title=title,
            url=url,
            author=entry.get('author'),
            summary=summary,
            thumbnail=get_thumbnail(entry),
            published_at=parse_date(entry),
            is_rage_bait=is_rage_bait(title),
            meta_data={
                'feed_title': feed.feed.get('title', ''),
            }
        )
        
        db.add(article)
        new_count += 1
    
    source.last_fetched = datetime.utcnow()
    source.fetch_error = None
    db.commit()
    
    logger.info(f"   [OK] Added {new_count} new articles from {source.name}")
    return new_count


async def fetch_all_rss_sources() -> int:
    """Fetch all enabled RSS sources. Returns total new articles."""
    db = SessionLocal()
    try:
        sources = db.query(Source).filter(
            Source.type == SourceType.RSS,
            Source.enabled == True
        ).all()
        
        logger.info(f"[SYNC] Fetching {len(sources)} RSS sources...")
        
        total_new = 0
        for source in sources:
            new_count = await fetch_rss_source(source, db)
            total_new += new_count
        
        logger.info(f"[OK] RSS fetch complete: {total_new} new articles")
        return total_new
    finally:
        db.close()


def seed_rss_sources(db: Session):
    """Seed the database with initial RSS sources."""
    
    sources = [
        # Boston Sports - The Athletic (now hosted on nytimes.com)
        {"name": "The Athletic - Celtics", "url": "https://www.nytimes.com/athletic/rss/nba/celtics/", "category": "boston_sports"},
        {"name": "The Athletic - Bruins", "url": "https://www.nytimes.com/athletic/rss/nhl/bruins/", "category": "boston_sports"},
        {"name": "The Athletic - Patriots", "url": "https://www.nytimes.com/athletic/rss/nfl/patriots/", "category": "boston_sports"},
        {"name": "The Athletic - Red Sox", "url": "https://www.nytimes.com/athletic/rss/mlb/redsox/", "category": "boston_sports"},
        
        # Other Teams - The Athletic
        {"name": "The Athletic - Padres", "url": "https://www.nytimes.com/athletic/rss/mlb/padres/", "category": "other_teams"},
        {"name": "The Athletic - Jazz", "url": "https://www.nytimes.com/athletic/rss/nba/jazz/", "category": "other_teams"},
        {"name": "The Athletic - Syracuse", "url": "https://www.nytimes.com/athletic/rss/college-basketball/syracuse-orange-college-basketball/", "category": "other_teams"},
        
        # Backup Boston Sports sources (if Athletic doesn't work)
        {"name": "Boston.com - Celtics", "url": "https://www.boston.com/tag/boston-celtics/feed/", "category": "boston_sports"},
        {"name": "Boston.com - Bruins", "url": "https://www.boston.com/tag/boston-bruins/feed/", "category": "boston_sports"},
        {"name": "Boston.com - Patriots", "url": "https://www.boston.com/tag/new-england-patriots/feed/", "category": "boston_sports"},
        {"name": "Boston.com - Red Sox", "url": "https://www.boston.com/tag/boston-red-sox/feed/", "category": "boston_sports"},
        
        # National News
        {"name": "NPR News", "url": "https://feeds.npr.org/1001/rss.xml", "category": "national_news"},
        {"name": "Google News World", "url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtVnVHZ0pWVXlnQVAB", "category": "national_news"},
        
        # Local News (Boston.com as Globe is broken)
        {"name": "Boston.com News", "url": "https://www.boston.com/tag/local-news/feed/", "category": "local_news"},
        
        # Long-form
        {"name": "Longreads", "url": "https://longreads.com/feed/", "category": "long_form"},
    ]
    
    from database import Category
    
    category_map = {
        "boston_sports": Category.BOSTON_SPORTS,
        "other_teams": Category.OTHER_TEAMS,
        "league_wide": Category.LEAGUE_WIDE,
        "national_news": Category.NATIONAL_NEWS,
        "local_news": Category.LOCAL_NEWS,
        "long_form": Category.LONG_FORM,
        "movies": Category.MOVIES,
    }
    
    added = 0
    for src in sources:
        existing = db.query(Source).filter(Source.url == src["url"]).first()
        if not existing:
            source = Source(
                name=src["name"],
                type=SourceType.RSS,
                url=src["url"],
                category=category_map[src["category"]],
                enabled=True
            )
            db.add(source)
            added += 1
    
    db.commit()
    if added > 0:
        logger.info(f"[SEED] Seeded {added} RSS sources")
    
    return added
