"""
Movie Release Fetcher
Fetches upcoming movie releases using RSS feeds.
"""
import feedparser
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from database import Article, Source, SourceType, Category, SessionLocal
from config import MAX_ARTICLES_PER_SOURCE

logger = logging.getLogger("lighthouse")


async def fetch_movie_releases() -> int:
    """Fetch upcoming movie releases from RSS sources."""
    # Movie news and release RSS feeds
    sources = [
        {"name": "Coming Soon", "url": "https://www.comingsoon.net/feed"},
        {"name": "Collider Movies", "url": "https://collider.com/feed/"},
        {"name": "MovieWeb News", "url": "https://movieweb.com/feed/"},
    ]
    
    db = SessionLocal()
    total_added = 0
    
    try:
        for src_info in sources:
            # Ensure source exists in DB
            source = db.query(Source).filter(Source.url == src_info["url"]).first()
            if not source:
                source = Source(
                    name=src_info["name"],
                    type=SourceType.RSS,
                    url=src_info["url"],
                    category=Category.MOVIES,
                    enabled=True
                )
                db.add(source)
                db.commit()
                db.refresh(source)
            
            feed = feedparser.parse(src_info["url"])
            if not feed.entries:
                continue
                
            new_count = 0
            for entry in feed.entries[:MAX_ARTICLES_PER_SOURCE]:
                url = entry.get('link', '')
                if not url:
                    continue
                    
                existing = db.query(Article).filter(Article.url == url).first()
                if existing:
                    continue
                    
                # Extract date
                published_at = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published_at = datetime(*entry.published_parsed[:6])
                
                # Cleanup thumbnail if present
                thumbnail = None
                if 'media_content' in entry:
                    thumbnail = entry.media_content[0].get('url')
                
                article = Article(
                    source_id=source.id,
                    title=entry.get('title', 'Untitled Movie'),
                    url=url,
                    summary=entry.get('summary', '')[:500],
                    thumbnail=thumbnail,
                    published_at=published_at,
                    meta_data={'type': 'movie_release'}
                )
                db.add(article)
                new_count += 1
                
            source.last_fetched = datetime.utcnow()
            total_added += new_count
            logger.info(f"[MOVIES] Added {new_count} movies from {src_info['name']}")
            
        db.commit()
        return total_added
        
    finally:
        db.close()
