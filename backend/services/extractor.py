"""
Article Content Extractor
Uses readability-lxml to extract clean article content for reader mode.
"""
import logging
from datetime import datetime
from typing import Optional
import httpx
from readability import Document

logger = logging.getLogger("lighthouse")


async def extract_article_content(url: str) -> dict:
    """
    Extract clean article content from URL using readability-lxml.
    
    Returns:
        {
            "title": str,
            "content": str (cleaned HTML),
            "excerpt": str,
            "extracted_at": datetime
        }
    
    Raises:
        ExtractionError: If extraction fails
    """
    try:
        # Fetch the page content
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
        
        # Extract content using readability
        doc = Document(html)
        
        title = doc.title()
        raw_content = doc.summary()  # Returns cleaned HTML
        excerpt = doc.short_title() or title[:200] if title else ""
        
        # Further clean the HTML to prevent layout breakage
        from lxml import html as lxml_html
        content_tree = lxml_html.fromstring(raw_content)
        
        # Strip all 'style' attributes
        for el in content_tree.xpath('//*[@style]'):
            el.attrib.pop('style')
            
        # Strip other problematic attributes if needed
        for el in content_tree.xpath('//*[@align]'):
            el.attrib.pop('align')

        # Convert back to string
        content = lxml_html.tostring(content_tree, encoding='unicode')
        
        # Basic validation - check if we got meaningful content
        if not content or len(content) < 100:
            raise ExtractionError("Extracted content too short or empty")
        
        logger.info(f"[EXTRACTOR] Successfully extracted content from {url}")
        
        return {
            "title": title,
            "content": content,
            "excerpt": excerpt,
            "extracted_at": datetime.utcnow()
        }
        
    except httpx.HTTPStatusError as e:
        logger.error(f"[EXTRACTOR] HTTP error fetching {url}: {e.response.status_code}")
        raise ExtractionError(f"Failed to fetch article: HTTP {e.response.status_code}")
    except httpx.TimeoutException:
        logger.error(f"[EXTRACTOR] Timeout fetching {url}")
        raise ExtractionError("Request timed out")
    except httpx.RequestError as e:
        logger.error(f"[EXTRACTOR] Request error for {url}: {e}")
        raise ExtractionError(f"Network error: {str(e)}")
    except Exception as e:
        logger.error(f"[EXTRACTOR] Extraction failed for {url}: {e}")
        raise ExtractionError(f"Extraction failed: {str(e)}")


class ExtractionError(Exception):
    """Raised when article extraction fails."""
    pass
