"""
LLM Summarization Service
Uses Groq (Llama 3) or Gemini to generate article summaries.
Groq offers 14,400 requests/day free vs Gemini's 20/day.
"""
import asyncio
import logging
import httpx
from typing import Optional
from sqlalchemy.orm import Session

from database import Article, SessionLocal
from config import GROQ_API_KEY, GEMINI_API_KEY, LLM_PROVIDER, LLM_SUMMARY_ENABLED

logger = logging.getLogger("lighthouse")

# Groq API endpoint
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


async def summarize_with_groq(prompt: str) -> Optional[str]:
    """Call Groq API with Llama 3."""
    if not GROQ_API_KEY:
        return None
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 500
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                GROQ_API_URL,
                headers=headers,
                json=payload,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                logger.warning(f"[WARN] Groq API error: {response.status_code} - {response.text[:200]}")
                return None
        except Exception as e:
            logger.warning(f"[WARN] Groq request failed: {e}")
            return None


async def summarize_with_gemini(prompt: str) -> Optional[str]:
    """Call Gemini API (fallback)."""
    if not GEMINI_API_KEY:
        return None
    
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        if response and response.text:
            return response.text
    except Exception as e:
        logger.warning(f"[WARN] Gemini error: {e}")
    
    return None


async def summarize_article(article: Article, db: Session) -> bool:
    """Generate a summary for an article."""
    if not LLM_SUMMARY_ENABLED:
        return False

    # No need to summarize Reddit posts
    if article.source.type.value == "reddit":
        return False
    
    if article.summary_llm:
        return True  # Already summarized
    
    logger.info(f"[LLM] Summarizing: {article.title}")
    
    # Build context from available info
    context = article.summary or ""
    
    prompt = f"""Write a brief 2-sentence summary for this news article. 
Even if information is limited, provide what you can infer from the headline.
Make sure summary is succient and don't waste space restating the prompt.

Title: {article.title}
{f'Context: {context}' if context else ''}

Summary:"""

    # Try Groq first (higher limits), then Gemini as fallback
    result = None
    
    if LLM_PROVIDER == "groq" and GROQ_API_KEY:
        result = await summarize_with_groq(prompt)
    
    if not result and GEMINI_API_KEY:
        result = await summarize_with_gemini(prompt)
    
    if result:
        article.summary_llm = result.strip()
        db.commit()
        logger.info(f"[LLM] Saved summary for: {article.title[:50]}")
        return True
    
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
                # Groq allows 30 RPM, so 2 seconds between requests is safe
                await asyncio.sleep(2)
                
        return count
    finally:
        db.close()
