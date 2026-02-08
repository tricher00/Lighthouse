"""
Lighthouse - Personal Content Aggregator
Main FastAPI application entry point.
"""
import os
import sys
import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Ensure backend directory is in path for imports
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

# Load environment variables
load_dotenv()

# Import config first to get paths
from config import HOST, PORT, DEBUG, DATA_DIR, FRONTEND_DIR

# Setup directories and logging IMMEDIATELY
LOG_DIR = DATA_DIR / "logs"
DATA_DIR.mkdir(exist_ok=True, parents=True)
LOG_DIR.mkdir(exist_ok=True, parents=True)

# In DEBUG mode: one log per instance (with timestamp)
# In PROD mode: one log per day
if DEBUG:
    LOG_FILE = LOG_DIR / f"lighthouse_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
else:
    LOG_FILE = LOG_DIR / f"lighthouse_{datetime.now().strftime('%Y%m%d')}.log"

# Create a safe stream handler that handles encoding errors
class SafeStreamHandler(logging.StreamHandler):
    """Stream handler that replaces unencodable characters."""
    def emit(self, record):
        try:
            msg = self.format(record)
            # Replace emojis/special chars with safe equivalents for Windows console
            safe_msg = msg.encode('ascii', 'replace').decode('ascii')
            self.stream.write(safe_msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

# Configure logging to both file (UTF-8) and console (safe ASCII)
# We do this specifically on the "lighthouse" logger to avoid uvicorn overrides
logger = logging.getLogger("lighthouse")
logger.setLevel(logging.INFO)
logger.handlers = [] # Clear existing handlers if any

# File handler
fh = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(fh)

# Safe console handler
ch = SafeStreamHandler(sys.stdout)
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(ch)

# Now safe to import database and routers
try:
    from database import init_db, SessionLocal
    from routers import dashboard, articles, sources, settings
except Exception as e:
    logger.critical(f"[FATAL] Failed to import database or routers: {e}", exc_info=True)
    sys.exit(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("[Lighthouse] Starting up...")
    logger.info(f"   Frontend: {FRONTEND_DIR}")
    logger.info(f"   Data: {DATA_DIR}")
    logger.info(f"   Logs: {LOG_FILE}")
    
    scheduler = None
    
    try:
        # Initialize database
        init_db()
        
        # Seed initial sources
        db = SessionLocal()
        try:
            from fetchers.rss import seed_rss_sources, fetch_all_rss_sources
            from fetchers.reddit import seed_reddit_sources, fetch_all_reddit_sources
            from fetchers.weather import fetch_and_save_weather
            from fetchers.sports import fetch_all_sports
            from fetchers.movies import fetch_movie_releases
            from fetchers.traffic import fetch_traffic_alerts
            from services.summarizer import summarize_latest_articles
            
            seed_rss_sources(db)
            seed_reddit_sources(db)
            
            # Initial async fetches (best effort) in background to not block startup
            logger.info("[>] Starting initial fetch in background...")
            
            async def run_initial_fetch():
                try:
                    await fetch_and_save_weather()
                    await fetch_all_rss_sources()
                    await fetch_all_sports()
                    await fetch_movie_releases()
                    await fetch_traffic_alerts()
                    await fetch_all_reddit_sources()
                    # Initial summarization
                    await summarize_latest_articles(10)
                except Exception as fetch_err:
                    logger.warning(f"[WARN] Initial fetch encountered issues: {fetch_err}")
                    logger.info("      Server will still start; data will refresh in background.")
            
            asyncio.create_task(run_initial_fetch())
            
        finally:
            db.close()
        
        # Start background scheduler
        from scheduler import start_scheduler
        scheduler = start_scheduler()
        
        logger.info("[OK] Lighthouse is ready!")
        logger.info(f"   Open http://localhost:{PORT} in your browser")
        
        yield
        
    except Exception as e:
        logger.error(f"[FATAL] Error during startup: {e}", exc_info=True)
        raise
    finally:
        # Shutdown
        logger.info("[Lighthouse] Shutting down...")
        if scheduler:
            scheduler.shutdown()
        logger.info("[OK] Shutdown complete")


app = FastAPI(
    title="Lighthouse",
    description="Your personal content aggregator",
    version="0.1.0",
    lifespan=lifespan
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Routers ---
app.include_router(dashboard.router)
app.include_router(articles.router)
app.include_router(sources.router)
app.include_router(settings.router)


@app.get("/api/health")
async def health_check():
    """Health check endpoint for connectivity testing."""
    return {
        "status": "ok",
        "message": "Lighthouse is shining",
        "version": "0.1.0"
    }


# --- Static Files & Frontend ---
# Must be after API routes

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def serve_dashboard():
    """Serve the main dashboard HTML."""
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/reader")
async def serve_reader():
    """Serve the main app (reader is a modal)."""
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/sources")
async def serve_sources_page():
    """Serve the main app (sources are managed in a modal)."""
    return FileResponse(FRONTEND_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    import socket
    
    # Hard check if port is busy
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((HOST, PORT))
        sock.close()
    except socket.error as e:
        print(f"FATAL: Port {PORT} is already in use. Please kill existing Python processes.")
        logger.critical(f"[FATAL] Port {PORT} is busy. Shutdown any existing Lighthouse instances.")
        sys.exit(1)

    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG
    )
