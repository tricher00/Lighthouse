"""
Lighthouse Configuration
Loads settings from environment variables with sensible defaults.
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"

# Database - use forward slashes for SQLite URL (Windows compatibility)
DB_PATH = DATA_DIR / "lighthouse.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH.as_posix()}")

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
TEST_MODE = os.getenv("TEST_MODE", "False").lower() == "true"

# API Keys
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")  # Now optional, switched to NWS
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Reddit credentials now optional (using public JSON endpoints)
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "Lighthouse/0.1.0")

# The Athletic Credentials
ATHLETIC_USERNAME = os.getenv("ATHLETIC_USERNAME", "")
ATHLETIC_PASSWORD = os.getenv("ATHLETIC_PASSWORD", "")

# Location (configurable via environment)
LOCATION_LAT = float(os.getenv("LOCATION_LAT", "40.7128"))  # Default: NYC
LOCATION_LON = float(os.getenv("LOCATION_LON", "-74.0060"))
LOCATION_NAME = os.getenv("LOCATION_NAME", "New York, NY")

# NWS Weather Zones (find yours at https://alerts.weather.gov/)
NWS_ZONE_CODES = os.getenv("NWS_ZONE_CODES", "NYZ072,NYZ073")  # Default: NYC zones

# Traffic Routes (optional, for display purposes)
TRAFFIC_ORIGIN = os.getenv("TRAFFIC_ORIGIN", "")
TRAFFIC_DESTINATION = os.getenv("TRAFFIC_DESTINATION", "")
TRAFFIC_ROUTES = os.getenv("TRAFFIC_ROUTES", "").split(",") if os.getenv("TRAFFIC_ROUTES") else []

# Fetch Intervals (in seconds)
FETCH_INTERVAL_RSS = 15 * 60        # 15 minutes
FETCH_INTERVAL_REDDIT = 10 * 60     # 10 minutes
FETCH_INTERVAL_WEATHER = 30 * 60    # 30 minutes
FETCH_INTERVAL_TRAFFIC = 15 * 60    # 15 minutes
FETCH_INTERVAL_SPORTS = 24 * 60 * 60  # Daily

# LLM Settings
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")  # gemini or ollama
LLM_SUMMARY_ENABLED = os.getenv("LLM_SUMMARY_ENABLED", "True").lower() == "true"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Sports Teams (ESPN API IDs) - configurable via JSON env var
# Format: [{"name": "Lakers", "league": "nba", "sport": "basketball", "id": "13"}, ...]
DEFAULT_SPORTS_TEAMS = [
    {"name": "Lakers", "league": "nba", "sport": "basketball", "id": "13"},
    {"name": "Yankees", "league": "mlb", "sport": "baseball", "id": "10"},
    {"name": "Cowboys", "league": "nfl", "sport": "football", "id": "6"},
]
SPORTS_TEAMS_JSON = os.getenv("SPORTS_TEAMS_JSON", "")
SPORTS_TEAMS = json.loads(SPORTS_TEAMS_JSON) if SPORTS_TEAMS_JSON else DEFAULT_SPORTS_TEAMS

# Content Settings
MAX_ARTICLES_PER_SOURCE = 10
ARTICLE_RETENTION_DAYS = 7  # How long to keep old articles

# Quality Filters
REDDIT_MIN_UPVOTE_RATIO = 0.7
REDDIT_MIN_SCORE = 10

# Rage-bait keyword filter
RAGE_BAIT_KEYWORDS = [
    "SLAMS", "DESTROYS", "OBLITERATES", "EVISCERATES",
    "You Won't Believe", "EXPOSED", "SHOCKED",
    "This Changes Everything", "Gone Wrong"
]
