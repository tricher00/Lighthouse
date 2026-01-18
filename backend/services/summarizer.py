"""
LLM Summarization Service
Uses Google Gemini to generate 3-5 sentence summaries for articles.
"""
from google import genai
import asyncio
import logging
from typing import Optional
from sqlalchemy.orm import Session

from database import Article, SessionLocal
from config import GEMINI_API_KEY, LLM_SUMMARY_ENABLED

logger = logging.getLogger("lighthouse")


def get_client() -> Optional[genai.Client]:
    """Initialize and return the Gemini client."""
    if not GEMINI_API_KEY or not LLM_SUMMARY_ENABLED:
        return None
    
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        return client
    except Exception as e:
        logger.warning(f"[WARN] Failed to initialize Gemini client: {e}")
        return None


async def summarize_article(article: Article, db: Session) -> bool:
    """Generate a summary for an article using Gemini (google-genai SDK)."""
    client = get_client()
    if not client:
        return False
    
    if article.summary_llm:
        return True  # Already summarized
    
    logger.info(f"[LLM] Summarizing: {article.title}")
    
    prompt = f"""
    Summarize the following article in 3-5 concise bullet points or sentences. 
    Focus on the "why it matters" and core facts. 
    Avoid fluff. Use a professional but engaging tone.
    
    Title: {article.title}
    Original Summary/Snippet: {article.summary or "No summary provided."}
    URL: {article.url}
    
    If the article seems to be just a headline without much info, just say "No further details available."
    """
    
    try:
        # Using the new genai SDK
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        
        if response and response.text:
            article.summary_llm = response.text.strip()
            db.commit()
            return True
        return False
        
    except Exception as e:
        logger.warning(f"[WARN] Summarization error for {article.title}: {e}")
        return False


async def summarize_latest_articles(limit: int = 10) -> int:
    """Summarize the most recent unsummarized articles."""
    db = SessionLocal()
    try:
        articles = db.query(Article).filter(
            Article.summary_llm == None,
            Article.is_read == False,
            Article.is_rage_bait == False
        ).order_by(Article.published_at.desc()).limit(limit).all()
        
        count = 0
        for article in articles:
            if await summarize_article(article, db):
                count += 1
                # Respect free tier rate limits (e.g., 5-15 RPM)
                # 12 seconds = 5 RPM exactly. 
                await asyncio.sleep(12)
                
        return count
    finally:
        db.close()
