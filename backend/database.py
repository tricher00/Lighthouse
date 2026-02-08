"""
Lighthouse Database Models
SQLAlchemy models for storing sources, articles, schedules, and user preferences.
"""
import os
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Boolean, 
    DateTime, Float, ForeignKey, JSON, Enum as SQLEnum
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.pool import StaticPool
import enum

from config import DATABASE_URL, DATA_DIR

logger = logging.getLogger("lighthouse")

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# Create engine with SQLite-specific settings
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False  # Set True for SQL debugging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class SourceType(enum.Enum):
    RSS = "rss"
    REDDIT = "reddit"
    API = "api"


class Category(enum.Enum):
    BOSTON_SPORTS = "boston_sports"
    OTHER_TEAMS = "other_teams"
    LEAGUE_WIDE = "league_wide"
    NATIONAL_NEWS = "national_news"
    LOCAL_NEWS = "local_news"
    LONG_FORM = "long_form"
    MOVIES = "movies"
    DISCOVERY = "discovery"


class Source(Base):
    """A content source (RSS feed, subreddit, or API endpoint)."""
    __tablename__ = "sources"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    type = Column(SQLEnum(SourceType), nullable=False)
    url = Column(String(1024), nullable=False)
    category = Column(SQLEnum(Category), nullable=False)
    enabled = Column(Boolean, default=True)
    last_fetched = Column(DateTime, nullable=True)
    fetch_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # For Reddit sources
    subreddit = Column(String(255), nullable=True)
    sort_by = Column(String(50), default="hot")
    limit = Column(Integer, default=5)
    
    # Relationships
    articles = relationship("Article", back_populates="source", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Source {self.name} ({self.type.value})>"


class Article(Base):
    """An individual article or post from a source."""
    __tablename__ = "articles"
    
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    
    # Content
    title = Column(String(1024), nullable=False)
    url = Column(String(2048), nullable=False, unique=True)
    author = Column(String(255), nullable=True)
    summary = Column(Text, nullable=True)  # Raw snippet from source
    summary_llm = Column(Text, nullable=True)  # LLM-generated summary
    content = Column(Text, nullable=True)  # Full text for reader mode
    content_extracted_at = Column(DateTime, nullable=True)  # When content was extracted
    thumbnail = Column(String(2048), nullable=True)
    
    # Timestamps
    published_at = Column(DateTime, nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    
    # User interaction
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    rating = Column(Integer, default=0)  # -1 = thumbs down, 0 = neutral, 1 = thumbs up
    rated_at = Column(DateTime, nullable=True)
    
    # Metadata (e.g., upvotes, comment count for Reddit)
    meta_data = Column(JSON, default=dict)
    
    # Quality signals
    quality_score = Column(Float, default=0.0)
    is_rage_bait = Column(Boolean, default=False)
    
    # Relationships
    source = relationship("Source", back_populates="articles")
    
    def __repr__(self):
        return f"<Article {self.title[:50]}...>"


class SportsSchedule(Base):
    """Upcoming game schedule for tracked teams."""
    __tablename__ = "sports_schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    team = Column(String(255), nullable=False)
    opponent = Column(String(255), nullable=False)
    game_time = Column(DateTime, nullable=False)
    venue = Column(String(255), nullable=True)
    broadcast = Column(String(255), nullable=True)
    is_home = Column(Boolean, default=True)
    league = Column(String(50), nullable=True)  # NBA, MLB, NHL, NFL, CBB
    espn_id = Column(String(100), nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Game {self.team} vs {self.opponent}>"


class TrafficAlert(Base):
    """Traffic alerts for monitored routes (e.g., NWS weather alerts)."""
    __tablename__ = "traffic_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    route = Column(String(255), nullable=False)
    alert_type = Column(String(100), nullable=False)  # accident, construction, closure
    description = Column(Text, nullable=False)
    location = Column(String(512), nullable=True)
    reported_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    severity = Column(String(50), default="moderate")  # minor, moderate, major
    url = Column(String(1024), nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<TrafficAlert {self.route}: {self.alert_type}>"


class TrafficRoute(Base):
    """Real-time traffic estimates for specific routes."""
    __tablename__ = "traffic_routes"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    origin = Column(String(255), nullable=False)
    destination = Column(String(255), nullable=False)
    origin_lat = Column(Float, nullable=True)
    origin_lon = Column(Float, nullable=True)
    dest_lat = Column(Float, nullable=True)
    dest_lon = Column(Float, nullable=True)
    origin_zone = Column(String(50), nullable=True)
    dest_zone = Column(String(50), nullable=True)
    current_duration_minutes = Column(Integer, nullable=True)
    typical_duration_minutes = Column(Integer, nullable=True)
    delay_minutes = Column(Integer, nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<TrafficRoute {self.name}: {self.delay_minutes}min delay>"


class WeatherData(Base):
    """Cached weather data."""
    __tablename__ = "weather_data"
    
    id = Column(Integer, primary_key=True, index=True)
    temperature = Column(Float, nullable=False)
    feels_like = Column(Float, nullable=True)
    conditions = Column(String(255), nullable=False)
    icon = Column(String(50), nullable=True)
    humidity = Column(Integer, nullable=True)
    wind_speed = Column(Float, nullable=True)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    dress_suggestion = Column(String(255), nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Weather {self.temperature}°F - {self.conditions}>"


class UserPreference(Base):
    """User preferences and settings."""
    __tablename__ = "user_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Preference {self.key}={self.value}>"


class SyncLog(Base):
    """Track sync events for hybrid PWA mode."""
    __tablename__ = "sync_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(255), nullable=False)
    sync_type = Column(String(50), nullable=False)  # full, incremental, read_status
    articles_synced = Column(Integer, default=0)
    synced_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<SyncLog {self.device_id} @ {self.synced_at}>"


class UserSettings(Base):
    """User-configurable settings for location, weather, and sports."""
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Location
    location_name = Column(String(255), nullable=True)
    location_lat = Column(Float, nullable=True)
    location_lon = Column(Float, nullable=True)
    nws_zone_codes = Column(String(255), nullable=True)
    
    # Sports teams (stored as JSON array)
    sports_teams = Column(JSON, default=list)
    
    # Traffic routes (stored as JSON array)
    traffic_routes = Column(JSON, default=list)
    
    # Reader mode settings
    reader_blacklisted_sources = Column(JSON, default=list)  # List of source IDs
    reader_cache_hours = Column(Integer, default=24)
    reader_theme = Column(String(50), default="auto")  # auto, light, dark
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<UserSettings {self.location_name}>"


# Database initialization
def init_db():
    """Create all tables if they don't exist, and migrate schema if needed."""
    Base.metadata.create_all(bind=engine)
    
    # Run simple schema migrations for SQLite
    # (SQLAlchemy's create_all doesn't add columns to existing tables)
    import sqlite3
    from config import DB_PATH
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # helper to check and add column
    def add_column_if_missing(table, column, col_type):
        cursor.execute(f'PRAGMA table_info({table})')
        columns = [row[1] for row in cursor.fetchall()]
        if column not in columns:
            cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} {col_type}')
            logger.info(f"[MIGRATE] Added {column} column to {table} table")
    
    # Migrations
    add_column_if_missing('articles', 'summary_llm', 'TEXT')
    add_column_if_missing('articles', 'content_extracted_at', 'DATETIME')
    add_column_if_missing('sports_schedules', 'espn_id', 'TEXT')
    add_column_if_missing('traffic_alerts', 'url', 'TEXT')
    add_column_if_missing('user_settings', 'reader_blacklisted_sources', 'JSON')
    add_column_if_missing('user_settings', 'reader_cache_hours', 'INTEGER')
    add_column_if_missing('user_settings', 'reader_theme', 'TEXT')
    add_column_if_missing('user_settings', 'traffic_routes', 'JSON')
    
    # TrafficRoute migrations
    add_column_if_missing('traffic_routes', 'origin_lat', 'FLOAT')
    add_column_if_missing('traffic_routes', 'origin_lon', 'FLOAT')
    add_column_if_missing('traffic_routes', 'dest_lat', 'FLOAT')
    add_column_if_missing('traffic_routes', 'dest_lon', 'FLOAT')
    add_column_if_missing('traffic_routes', 'origin_zone', 'TEXT')
    add_column_if_missing('traffic_routes', 'dest_zone', 'TEXT')
    
    # Ensure traffic_routes table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='traffic_routes'")
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE traffic_routes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                origin TEXT NOT NULL,
                destination TEXT NOT NULL,
                origin_lat FLOAT,
                origin_lon FLOAT,
                dest_lat FLOAT,
                dest_lon FLOAT,
                origin_zone TEXT,
                dest_zone TEXT,
                current_duration_minutes INTEGER,
                typical_duration_minutes INTEGER,
                delay_minutes INTEGER,
                fetched_at DATETIME
            )
        ''')
        logger.info("[MIGRATE] Created traffic_routes table")
    
    conn.commit()
    conn.close()
    logger.info("[OK] Database initialized")


# Database session getter
def get_db():
    """Get a database session (for FastAPI dependency injection)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
