# 🗼 Lighthouse

A personal content aggregator that replaces doomscrolling with intentional reading. Lighthouse brings together your news, sports, weather, and more into a single, customizable dashboard.

![Lighthouse Dashboard](docs/screenshot.png)

## ✨ Features

- **📰 RSS Aggregation** - Pull from any RSS feed (news sites, blogs, The Athletic)
- **🏀 Sports Schedule** - Track upcoming games for your favorite teams via ESPN
- **🌤️ Local Weather** - Current conditions and alerts from National Weather Service
- **⚠️ Weather Alerts** - Severe weather warnings for your area
- **🤖 AI Summaries** - Optional LLM-powered article summaries (via Gemini)
- **🎬 Movie Releases** - New releases and upcoming films from TMDB
- **📱 Mobile-Friendly** - Responsive dark mode UI

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- (Optional) [Gemini API Key](https://ai.google.dev/) for AI summaries

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

## ⚙️ Configuration

Edit `.env` to customize Lighthouse for your needs:

### Required
| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Your Gemini API key for AI summaries |

### Location
| Variable | Description | Default |
|----------|-------------|---------|
| `LOCATION_NAME` | Display name for your location | `New York, NY` |
| `LOCATION_LAT` | Latitude | `40.7128` |
| `LOCATION_LON` | Longitude | `-74.0060` |
| `NWS_ZONE_CODES` | NWS forecast zones (comma-separated) | `NYZ072,NYZ073` |

### Sports Teams
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

### Optional
| Variable | Description |
|----------|-------------|
| `ATHLETIC_USERNAME` | The Athletic email for premium RSS |
| `ATHLETIC_PASSWORD` | The Athletic password |
| `LLM_SUMMARY_ENABLED` | Enable AI summaries (`True`/`False`) |
| `TEST_MODE` | Skip external APIs, use sample data |

## 🔧 Finding Your Settings

### NWS Zone Codes
1. Go to [alerts.weather.gov](https://alerts.weather.gov/)
2. Click your state → county
3. Note the zone code (e.g., `NYZ072`)

### ESPN Team IDs
1. Go to ESPN and find your team's page
2. The URL contains the team ID: `espn.com/nba/team/_/id/13/los-angeles-lakers`
3. In this example, the ID is `13`

## 📁 Project Structure

```
lighthouse/
├── backend/
│   ├── main.py           # FastAPI application
│   ├── config.py         # Configuration loading
│   ├── database.py       # SQLAlchemy models
│   ├── fetchers/         # Data fetching modules
│   │   ├── rss.py
│   │   ├── weather.py
│   │   ├── sports.py
│   │   └── traffic.py
│   └── routers/          # API endpoints
├── frontend/
│   ├── index.html
│   ├── css/styles.css
│   └── js/dashboard.js
├── data/                 # Database & logs (gitignored)
├── .env.example
└── requirements.txt
```

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.
