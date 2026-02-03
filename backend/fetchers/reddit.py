"""
Reddit Fetcher (Keyless)
Fetches top posts from configured subreddits using public JSON endpoints.
No API key required.
"""
import aiohttp
import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from database import Source, Article, SourceType, Category, SessionLocal
from config import (
    REDDIT_MIN_UPVOTE_RATIO, REDDIT_MIN_SCORE, RAGE_BAIT_KEYWORDS,
    MAX_ARTICLES_PER_SOURCE
)

logger = logging.getLogger("lighthouse")


def is_rage_bait(title: str) -> bool:
    """Check if a title contains rage-bait keywords."""
    title_upper = title.upper()
    return any(keyword.upper() in title_upper for keyword in RAGE_BAIT_KEYWORDS)


async def fetch_subreddit_json(subreddit: str, sort_by: str = "hot", limit: int = 5) -> Optional[List[Dict[str, Any]]]:
    """Fetch posts from a subreddit using public JSON endpoint."""
    # Reddit's public JSON endpoint
    if sort_by == "top":
        url = f"https://www.reddit.com/r/{subreddit}/top.json?t=day&limit={limit}"
    elif sort_by == "new":
        url = f"https://www.reddit.com/r/{subreddit}/new.json?limit={limit}"
    else:  # hot
        url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    
    headers = {
        'User-Agent': 'Lighthouse/1.0 (personal content aggregator)'
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status != 200:
                    logger.warning(f"[WARN] Reddit fetch error for r/{subreddit}: HTTP {response.status}")
                    return None
                
                data = await response.json()
                posts = data.get('data', {}).get('children', [])
                return [post['data'] for post in posts if post.get('kind') == 't3']
                
    except Exception as e:
        logger.warning(f"[WARN] Error fetching r/{subreddit}: {e}")
        return None


async def fetch_subreddit_posts(source: Source, db: Session) -> int:
    """
    Fetch posts from a single subreddit.
    Returns the number of new articles added.
    """
    if not source.subreddit:
        logger.warning(f"[WARN] No subreddit configured for source {source.name}")
        return 0
    
    logger.info(f"[FETCH] Fetching Reddit: r/{source.subreddit}")
    
    posts = await fetch_subreddit_json(
        source.subreddit,
        source.sort_by or "hot",
        source.limit or 5
    )
    
    if not posts:
        return 0
    
    new_count = 0
    for post_data in posts:
        # Skip stickied posts
        if post_data.get('stickied'):
            continue
        
        # Quality filters
        upvote_ratio = post_data.get('upvote_ratio', 0)
        score = post_data.get('score', 0)
        
        if upvote_ratio < REDDIT_MIN_UPVOTE_RATIO:
            continue
        if score < REDDIT_MIN_SCORE:
            continue
        
        permalink = post_data.get('permalink', '')
        url = f"https://reddit.com{permalink}"
        
        # Check if already exists
        existing = db.query(Article).filter(Article.url == url).first()
        if existing:
            continue
        
        title = post_data.get('title', 'Untitled')
        is_self = post_data.get('is_self', False)
        
        # For link posts, use the linked URL
        content_url = post_data.get('url') if not is_self else url
        
        # Get thumbnail
        thumbnail = post_data.get('thumbnail')
        if thumbnail and not thumbnail.startswith('http'):
            thumbnail = None
        
        # Get selftext for text posts
        selftext = post_data.get('selftext', '')
        summary = selftext[:500] if is_self and selftext else None
        
        article = Article(
            source_id=source.id,
            title=title,
            url=url,
            author=post_data.get('author'),
            summary=summary,
            thumbnail=thumbnail,
            published_at=datetime.fromtimestamp(post_data.get('created_utc', 0)),
            is_rage_bait=is_rage_bait(title),
            meta_data={
                'subreddit': source.subreddit,
                'score': score,
                'upvote_ratio': upvote_ratio,
                'num_comments': post_data.get('num_comments', 0),
                'is_self': is_self,
                'linked_url': content_url if not is_self else None,
                'flair': post_data.get('link_flair_text')
            },
            quality_score=upvote_ratio * (1 + (post_data.get('num_comments', 0) / 100))
        )
        
        db.add(article)
        new_count += 1
    
    source.last_fetched = datetime.utcnow()
    source.fetch_error = None
    db.commit()
    
    logger.info(f"   [OK] Added {new_count} posts from r/{source.subreddit}")
    return new_count


async def fetch_all_reddit_sources() -> int:
    """Fetch all enabled Reddit sources. Returns total new articles."""
    db = SessionLocal()
    try:
        sources = db.query(Source).filter(
            Source.type == SourceType.REDDIT,
            Source.enabled == True
        ).all()
        
        logger.info(f"[SYNC] Fetching {len(sources)} Reddit sources...")
        
        total_new = 0
        for source in sources:
            try:
                new_count = await fetch_subreddit_posts(source, db)
                total_new += new_count
                # Be nice to Reddit - small delay between requests
                await asyncio.sleep(1)
            except Exception as e:
                source.fetch_error = str(e)
                source.last_fetched = datetime.utcnow()
                db.commit()
                logger.error(f"   [ERROR] Error fetching r/{source.subreddit}: {e}")
        
        logger.info(f"[OK] Reddit fetch complete: {total_new} new posts")
        return total_new
    finally:
        db.close()


def seed_reddit_sources(db: Session):
    """Seed the database with initial Reddit sources.
    
    NOTE: Team-specific and location-specific subreddits have been removed.
    Users should add their own subreddits via the Sources UI.
    This function now only seeds generic, location-agnostic sources.
    """
    
    subreddits = [
        # League-wide
        {"name": "r/nba", "subreddit": "nba", "category": "league_wide", "sort": "hot", "limit": 5},
        {"name": "r/baseball", "subreddit": "baseball", "category": "league_wide", "sort": "hot", "limit": 5},
        {"name": "r/nfl", "subreddit": "nfl", "category": "league_wide", "sort": "hot", "limit": 5},
        {"name": "r/hockey", "subreddit": "hockey", "category": "league_wide", "sort": "hot", "limit": 5},
        
        # National News
        {"name": "r/news", "subreddit": "news", "category": "national_news", "sort": "top", "limit": 10},
        {"name": "r/worldnews", "subreddit": "worldnews", "category": "national_news", "sort": "top", "limit": 5},
        
        # Long-form
        {"name": "r/TrueReddit", "subreddit": "TrueReddit", "category": "long_form", "sort": "hot", "limit": 3},
    ]

    
    category_map = {
        "boston_sports": Category.BOSTON_SPORTS,
        "other_teams": Category.OTHER_TEAMS,
        "league_wide": Category.LEAGUE_WIDE,
        "national_news": Category.NATIONAL_NEWS,
        "local_news": Category.LOCAL_NEWS,
        "long_form": Category.LONG_FORM,
    }
    
    added = 0
    for sub in subreddits:
        existing = db.query(Source).filter(Source.subreddit == sub["subreddit"]).first()
        if not existing:
            source = Source(
                name=sub["name"],
                type=SourceType.REDDIT,
                url=f"https://reddit.com/r/{sub['subreddit']}",
                subreddit=sub["subreddit"],
                category=category_map[sub["category"]],
                sort_by=sub["sort"],
                limit=sub["limit"],
                enabled=True
            )
            db.add(source)
            added += 1
    
    db.commit()
    if added > 0:
        logger.info(f"[SEED] Seeded {added} Reddit sources")
    
    return added
