"""
Sources API Router
CRUD operations for managing content sources.
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, Source, SourceType, Category

router = APIRouter(prefix="/api/sources", tags=["sources"])


class SourceCreate(BaseModel):
    name: str
    type: str  # "rss" or "reddit"
    url: str
    category: str
    subreddit: Optional[str] = None
    sort_by: Optional[str] = "hot"
    limit: Optional[int] = 5


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    category: Optional[str] = None
    sort_by: Optional[str] = None
    limit: Optional[int] = None


@router.get("")
async def list_sources(
    db: Session = Depends(get_db),
    type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    enabled_only: bool = Query(False)
):
    """List all content sources."""
    query = db.query(Source)
    
    if type:
        try:
            source_type = SourceType(type)
            query = query.filter(Source.type == source_type)
        except ValueError:
            pass
    
    if category:
        try:
            cat = Category(category)
            query = query.filter(Source.category == cat)
        except ValueError:
            pass
    
    if enabled_only:
        query = query.filter(Source.enabled == True)
    
    sources = query.order_by(Source.category, Source.name).all()
    
    return {
        "sources": [
            {
                "id": s.id,
                "name": s.name,
                "type": s.type.value,
                "url": s.url,
                "category": s.category.value,
                "enabled": s.enabled,
                "subreddit": s.subreddit,
                "sort_by": s.sort_by,
                "limit": s.limit,
                "last_fetched": s.last_fetched.isoformat() if s.last_fetched else None,
                "fetch_error": s.fetch_error
            }
            for s in sources
        ]
    }


@router.post("")
async def create_source(source: SourceCreate, db: Session = Depends(get_db)):
    """Add a new content source."""
    # Validate type
    try:
        source_type = SourceType(source.type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid source type: {source.type}")
    
    # Validate category
    try:
        category = Category(source.category)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid category: {source.category}")
    
    # Check for duplicate
    existing = db.query(Source).filter(Source.url == source.url).first()
    if existing:
        raise HTTPException(status_code=400, detail="Source with this URL already exists")
    
    new_source = Source(
        name=source.name,
        type=source_type,
        url=source.url,
        category=category,
        subreddit=source.subreddit,
        sort_by=source.sort_by or "hot",
        limit=source.limit or 5,
        enabled=True
    )
    
    db.add(new_source)
    db.commit()
    db.refresh(new_source)
    
    return {
        "success": True,
        "source": {
            "id": new_source.id,
            "name": new_source.name,
            "type": new_source.type.value,
            "url": new_source.url,
            "category": new_source.category.value
        }
    }


@router.put("/{source_id}")
async def update_source(source_id: int, update: SourceUpdate, db: Session = Depends(get_db)):
    """Update a content source."""
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    if update.name is not None:
        source.name = update.name
    if update.enabled is not None:
        source.enabled = update.enabled
    if update.category is not None:
        try:
            source.category = Category(update.category)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid category: {update.category}")
    if update.sort_by is not None:
        source.sort_by = update.sort_by
    if update.limit is not None:
        source.limit = update.limit
    
    db.commit()
    
    return {"success": True, "source_id": source_id}


@router.delete("/{source_id}")
async def delete_source(source_id: int, db: Session = Depends(get_db)):
    """Delete a content source and all its articles."""
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    db.delete(source)
    db.commit()
    
    return {"success": True, "source_id": source_id}


@router.post("/{source_id}/toggle")
async def toggle_source(source_id: int, db: Session = Depends(get_db)):
    """Toggle a source's enabled status."""
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    source.enabled = not source.enabled
    db.commit()
    
    return {"success": True, "source_id": source_id, "enabled": source.enabled}


@router.post("/{source_id}/fetch")
async def force_fetch_source(source_id: int, db: Session = Depends(get_db)):
    """Force an immediate fetch of a specific source."""
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Import fetchers
    if source.type == SourceType.RSS:
        from fetchers.rss import fetch_rss_source
        new_count = await fetch_rss_source(source, db)
    elif source.type == SourceType.REDDIT:
        from fetchers.reddit import fetch_subreddit_posts
        new_count = await fetch_subreddit_posts(source, db)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown source type: {source.type}")
    
    return {
        "success": True,
        "source_id": source_id,
        "new_articles": new_count
    }


@router.get("/categories")
async def list_categories():
    """List all available categories."""
    return {
        "categories": [
            {"value": c.value, "name": c.name.replace("_", " ").title()}
            for c in Category
        ]
    }
