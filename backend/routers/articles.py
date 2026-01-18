"""
Articles API Router
Handles article interactions like marking as read and rating.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, Article

router = APIRouter(prefix="/api/articles", tags=["articles"])


class RatingRequest(BaseModel):
    rating: int  # -1 = thumbs down, 0 = neutral, 1 = thumbs up


class SyncReadStatusRequest(BaseModel):
    article_urls: list[str]
    device_id: str


@router.post("/{article_id}/read")
async def mark_as_read(article_id: int, db: Session = Depends(get_db)):
    """Mark an article as read."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    article.is_read = True
    article.read_at = datetime.utcnow()
    db.commit()
    
    return {"success": True, "article_id": article_id}


@router.post("/{article_id}/unread")
async def mark_as_unread(article_id: int, db: Session = Depends(get_db)):
    """Mark an article as unread."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    article.is_read = False
    article.read_at = None
    db.commit()
    
    return {"success": True, "article_id": article_id}


@router.post("/{article_id}/rate")
async def rate_article(article_id: int, request: RatingRequest, db: Session = Depends(get_db)):
    """Rate an article (thumbs up/down)."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    if request.rating not in [-1, 0, 1]:
        raise HTTPException(status_code=400, detail="Rating must be -1, 0, or 1")
    
    article.rating = request.rating
    article.rated_at = datetime.utcnow()
    db.commit()
    
    return {"success": True, "article_id": article_id, "rating": request.rating}


@router.post("/sync-read-status")
async def sync_read_status(request: SyncReadStatusRequest, db: Session = Depends(get_db)):
    """
    Sync read status from a mobile/offline client.
    Used in the hybrid PWA mode when the phone reconnects.
    """
    updated_count = 0
    
    for url in request.article_urls:
        article = db.query(Article).filter(Article.url == url).first()
        if article and not article.is_read:
            article.is_read = True
            article.read_at = datetime.utcnow()
            updated_count += 1
    
    db.commit()
    
    # Log the sync
    from database import SyncLog
    sync_log = SyncLog(
        device_id=request.device_id,
        sync_type="read_status",
        articles_synced=updated_count
    )
    db.add(sync_log)
    db.commit()
    
    return {
        "success": True,
        "articles_synced": updated_count,
        "device_id": request.device_id
    }


@router.get("/stats")
async def get_article_stats(db: Session = Depends(get_db)):
    """Get reading statistics."""
    total = db.query(Article).count()
    read = db.query(Article).filter(Article.is_read == True).count()
    unread = db.query(Article).filter(Article.is_read == False).count()
    thumbs_up = db.query(Article).filter(Article.rating == 1).count()
    thumbs_down = db.query(Article).filter(Article.rating == -1).count()
    rage_bait_filtered = db.query(Article).filter(Article.is_rage_bait == True).count()
    
    return {
        "total": total,
        "read": read,
        "unread": unread,
        "thumbs_up": thumbs_up,
        "thumbs_down": thumbs_down,
        "rage_bait_filtered": rage_bait_filtered
    }
