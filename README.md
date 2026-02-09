# Lighthouse

A personal content aggregator that replaces doomscrolling with intentional reading. Lighthouse brings together your news, sports, weather, and more into a single, customizable dashboard.

## ✨ Features

- **📰 RSS Aggregation** - Pull from any RSS feed (news sites, blogs, The Athletic)
- **🏀 Sports Schedule** - Track upcoming games for your favorite teams via ESPN
- **🌤️ Local Weather** - Current conditions and forecasts from National Weather Service
- **⚠️ Weather Alerts** - Severe weather warnings for your area
- **🤖 AI Summaries** - Optional LLM-powered article summaries (Groq or Gemini)
- **🎬 Movie Releases** - New releases and upcoming films from TMDB
- **💬 Reddit Integration** - Top posts from your favorite subreddits
- **📱 Mobile-Friendly PWA** - Installable as a native-like app on Android/Desktop with offline support
- **🌑 Dark Mode** - Easier on the eyes for night reading
- **⚡ Offline Mode** - Read cached articles and queue actions when disconnected

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- (Optional) [Groq API Key](https://console.groq.com) for AI summaries (recommended - 14,400 free requests/day)
- (Optional) [Gemini API Key](https://ai.google.dev/) for AI summaries (backup)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/lighthouse.git
   cd lighthouse
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings (see Configuration below)
   ```

5. **Run the server**
   ```bash
   cd backend
   python main.py
   ```

6. **Open your browser**
   Navigate to `http://localhost:8000`

7. **Stop the server** (when needed)
   ```bash
   # Windows - double-click stop.bat or run:
   python stop.py
   ```

## ⚙️ Configuration

Edit `.env` to customize Lighthouse for your needs:

### Location Settings
| Variable | Description | Default |
|----------|-------------|---------|
| `LOCATION_NAME` | Display name for your location | `New York, NY` |
| `LOCATION_LAT` | Latitude | `40.7128` |
| `LOCATION_LON` | Longitude | `-74.0060` |
| `NWS_ZONE_CODES` | NWS forecast zones (comma-separated) | `NYZ072,NYZ073` |

### LLM Summarization (Optional)
| Variable | Description |
|----------|-------------|
| `LLM_PROVIDER` | `groq` (recommended) or `gemini` |
| `GROQ_API_KEY` | Groq API key for fast, free summaries |
| `GEMINI_API_KEY` | Gemini API key (backup option) |
| `LLM_SUMMARY_ENABLED` | Enable AI summaries (`True`/`False`) |

### Sports Teams (Optional)
| Variable | Description |
|----------|-------------|
| `SPORTS_TEAMS_JSON` | JSON array of ESPN teams to track |

Example:
```json
[
  {"name": "Lakers", "league": "nba", "sport": "basketball", "id": "13"},
  {"name": "Yankees", "league": "mlb", "sport": "baseball", "id": "10"}
]
```

### Reddit API (Optional)
| Variable | Description |
|----------|-------------|
| `REDDIT_CLIENT_ID` | Reddit app client ID |
| `REDDIT_CLIENT_SECRET` | Reddit app client secret |
| `REDDIT_USER_AGENT` | User agent string |

> **Note**: Reddit integration works without credentials using public JSON endpoints.

### The Athletic (Optional)
| Variable | Description |
|----------|-------------|
| `ATHLETIC_USERNAME` | The Athletic email for premium RSS |
| `ATHLETIC_PASSWORD` | The Athletic password |

### Server Settings
| Variable | Description | Default |
|----------|-------------|---------|
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `DEBUG` | Debug mode | `True` |
| `TEST_MODE` | Skip external APIs, use sample data | `False` |

## 🔧 Finding Your Settings

### NWS Zone Codes
1. Go to [alerts.weather.gov](https://alerts.weather.gov/)
2. Click your state → county
3. Note the zone code (e.g., `NYZ072`)

### ESPN Team IDs
1. Go to ESPN and find your team's page
2. The URL contains the team ID: `espn.com/nba/team/_/id/13/los-angeles-lakers`
3. In this example, the ID is `13`

### Reddit App Credentials
1. Go to [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)
2. Create a new "script" application
3. Copy the client ID and secret

## 📁 Project Structure

```
lighthouse/
├── backend/
│   ├── main.py           # FastAPI application
│   ├── config.py         # Configuration loading
│   ├── database.py       # SQLAlchemy models
│   ├── scheduler.py      # Background task scheduling
│   ├── fetchers/         # Data fetching modules
│   │   ├── rss.py        # RSS feed parsing
│   │   ├── weather.py    # NWS weather data
│   │   ├── sports.py     # ESPN sports schedules
│   │   ├── reddit.py     # Reddit posts
│   │   ├── movies.py     # TMDB movie data
│   │   └── traffic.py    # Traffic data (optional)
│   ├── routers/          # API endpoints
│   │   ├── dashboard.py  # Main dashboard API
│   │   ├── articles.py   # Article endpoints
│   │   └── sources.py    # Feed source management
│   └── services/         # Business logic
│       └── summarizer.py # LLM summarization
├── frontend/
│   ├── index.html
│   ├── css/styles.css
│   └── js/dashboard.js
├── data/                 # Database & logs (gitignored)
├── .env.example
├── requirements.txt
├── stop.py               # Server shutdown script
├── stop.bat              # Windows shutdown helper
└── stop.ps1              # PowerShell shutdown script
```

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.
