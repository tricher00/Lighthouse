# Lighthouse — CLAUDE.md

## Project Overview

Lighthouse is a personal content aggregator designed to replace doomscrolling with intentional reading. It pulls together multiple content sources (RSS feeds, Reddit, weather, sports scores, and movies) into a single, customizable dark-mode dashboard.

- Backend: FastAPI serving a REST API, with SQLite for persistence and APScheduler for background fetching
- Frontend: Vanilla HTML/CSS/JavaScript — no build tools, no framework
- LLM: Optional AI article summarization via Groq (primary) or Google Gemini (fallback)

---

## Tech Stack

| Layer      | Technology                                      |
|------------|-------------------------------------------------|
| Backend    | Python 3.10+, FastAPI, Uvicorn                  |
| Database   | SQLite via SQLAlchemy 2.x ORM                   |
| Scheduling | APScheduler 3.x                                 |
| HTTP       | aiohttp (async), httpx, requests                |
| Parsing    | feedparser (RSS), BeautifulSoup4, lxml          |
| Reddit     | PRAW 7.x                                        |
| LLM        | Groq API or Google Gemini API                   |
| Frontend   | Vanilla HTML/CSS/JavaScript                     |
| Testing    | pytest                                          |

---

## Project Structure

```
Lighthouse/
├── backend/
│   ├── main.py             # FastAPI app entry point, mounts routers
│   ├── config.py           # Pydantic-based env config (reads .env)
│   ├── database.py         # SQLAlchemy models + custom migration logic
│   ├── scheduler.py        # APScheduler jobs — fetch intervals per source
│   ├── fetchers/
│   │   ├── rss.py          # RSS feed parsing
│   │   ├── weather.py      # National Weather Service (NWS) keyless API
│   │   ├── sports.py       # ESPN sports schedules
│   │   ├── reddit.py       # Reddit posts via PRAW or public JSON
│   │   ├── movies.py       # TMDB upcoming movie releases
│   │   └── traffic.py      # Optional traffic alerts
│   ├── routers/
│   │   ├── dashboard.py    # GET /api/dashboard — main aggregated endpoint
│   │   ├── articles.py     # Article interactions: read, rate, sync
│   │   └── sources.py      # Feed source CRUD
│   └── services/
│       └── summarizer.py   # LLM-based article summarization
├── frontend/
│   ├── index.html          # Single-page dashboard
│   ├── css/styles.css      # CSS variables, dark theme, responsive layout
│   └── js/dashboard.js     # Fetches /api/dashboard and renders all widgets
├── data/                   # Gitignored — SQLite DB and logs live here
├── requirements.txt
├── .env.example            # Template for all environment variables
├── stop.py                 # Cross-platform server stop script
├── stop.bat / stop.ps1     # Windows-specific stop scripts
└── README.md
```

---

## Development Commands

```bash
# --- Initial Setup ---
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows
pip install -r requirements.txt
cp .env.example .env            # Then fill in required values

# --- Run the server ---
cd backend
python main.py
# Serves at http://localhost:8000
# API docs at http://localhost:8000/docs

# --- Stop the server ---
python stop.py      # Linux/macOS (from repo root)
stop.bat            # Windows CMD
stop.ps1            # Windows PowerShell

# --- Run tests ---
cd backend
pytest

# --- Run without external APIs (sample data only) ---
TEST_MODE=True python main.py
```

---

## Configuration

Copy `.env.example` to `.env` and fill in values. Key settings:

| Variable              | Description                                          |
|-----------------------|------------------------------------------------------|
| `LOCATION_LAT/LON`    | Latitude/longitude for weather                       |
| `NWS_ZONE_CODES`      | NWS zone codes for weather alerts (e.g. `NYZ072`)    |
| `LLM_PROVIDER`        | `groq` or `gemini`                                   |
| `GROQ_API_KEY`        | Groq API key (14,400 free req/day)                   |
| `GEMINI_API_KEY`      | Google Gemini API key (fallback)                     |
| `REDDIT_CLIENT_ID`    | Reddit app credentials                               |
| `REDDIT_CLIENT_SECRET`| Reddit app credentials                               |
| `SPORTS_TEAMS_JSON`   | JSON array of ESPN team IDs to track                 |
| `TEST_MODE`           | `True` to skip all external APIs (safe for dev)      |
| `PORT`                | Server port (default `8000`)                         |

`TEST_MODE=True` is the safest way to develop without any API keys configured.

---

## Key Architecture Notes

- **Single dashboard endpoint:** `GET /api/dashboard` returns all widget data (articles, weather, sports, traffic) in one response. The frontend makes exactly one API call on load.

- **Background scheduler:** `scheduler.py` registers APScheduler jobs that run fetchers on intervals:
  - RSS feeds: every 15 minutes
  - Reddit: every 10 minutes
  - Weather: every 30 minutes
  - Traffic: every 15 minutes
  - Sports: every 24 hours
  - LLM summarization: every 5 minutes

- **Deduplication:** `routers/dashboard.py` deduplicates articles by title similarity using a 60% threshold before returning results.

- **Rage-bait filtering:** Keyword-based filtering runs during article ingestion to suppress low-quality content.

- **Rating system:** Articles support ratings of `-1`, `0`, or `1` via `POST /api/articles/{id}/rate`.

- **Schema migration:** `database.py` contains custom `ALTER TABLE` migration logic. Do **not** introduce Alembic — existing migration approach must be preserved.

- **PWA sync:** `POST /api/articles/sync-read-status` handles batched read-status sync for offline PWA use.

- **Article retention:** Articles older than 7 days are purged automatically.

---

## Adding a New Content Source

1. Create `backend/fetchers/<source>.py` with an async fetch function that writes to the DB
2. Add a SQLAlchemy model in `database.py` if the source requires new storage (include migration logic)
3. Register a scheduled job in `scheduler.py` with an appropriate interval
4. Include the fetched data in `GET /api/dashboard` response (`routers/dashboard.py`)
5. Render the widget in `frontend/js/dashboard.js` and style it in `frontend/css/styles.css`

---

## API Reference (Key Endpoints)

| Method | Path                              | Description                          |
|--------|-----------------------------------|--------------------------------------|
| GET    | `/api/health`                     | Health check                         |
| GET    | `/api/dashboard`                  | All dashboard data in one response   |
| GET    | `/api/articles`                   | Paginated articles with filters      |
| POST   | `/api/articles/{id}/read`         | Mark article as read                 |
| POST   | `/api/articles/{id}/rate`         | Rate article (-1, 0, 1)              |
| POST   | `/api/articles/sync-read-status`  | Batch sync read status (PWA)         |
| GET    | `/api/sources`                    | List configured sources              |
| POST   | `/api/sources`                    | Add a new source                     |

Full interactive docs available at `http://localhost:8000/docs` when the server is running.
