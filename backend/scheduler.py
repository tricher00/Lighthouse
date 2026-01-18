"""
Background Scheduler
Runs periodic fetches for all content sources.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import asyncio
import logging

from config import (
    FETCH_INTERVAL_RSS,
    FETCH_INTERVAL_REDDIT,
    FETCH_INTERVAL_WEATHER,
    FETCH_INTERVAL_TRAFFIC,
    FETCH_INTERVAL_SPORTS
)

logger = logging.getLogger("lighthouse")


def run_async(coro):
    """Run an async coroutine from a sync context."""
    try:
        loop = asyncio.get_running_loop()
        # If we have a running loop, we can't use run_until_complete
        return loop.create_task(coro)
    except RuntimeError:
        # No running loop, safe to use asyncio.run
        return asyncio.run(coro)


def fetch_rss_job():
    """Job to fetch all RSS feeds."""
    logger.info("[CRON] Scheduled: Fetching RSS feeds...")
    from fetchers.rss import fetch_all_rss_sources
    run_async(fetch_all_rss_sources())


def fetch_reddit_job():
    """Job to fetch all Reddit sources."""
    logger.info("[CRON] Scheduled: Fetching Reddit posts...")
    from fetchers.reddit import fetch_all_reddit_sources
    fetch_all_reddit_sources()


def fetch_weather_job():
    """Job to fetch weather data."""
    logger.info("[CRON] Scheduled: Fetching weather...")
    from fetchers.weather import fetch_and_save_weather
    run_async(fetch_and_save_weather())


def fetch_traffic_job():
    """Job to fetch traffic alerts."""
    logger.info("[CRON] Scheduled: Fetching traffic...")
    from fetchers.traffic import fetch_traffic_alerts
    run_async(fetch_traffic_alerts())


def fetch_sports_job():
    """Job to fetch sports schedules."""
    logger.info("[CRON] Scheduled: Fetching sports schedules...")
    from fetchers.sports import fetch_all_sports
    run_async(fetch_all_sports())


def fetch_movies_job():
    """Job to fetch movie releases."""
    logger.info("[CRON] Scheduled: Fetching movie releases...")
    from fetchers.movies import fetch_movie_releases
    run_async(fetch_movie_releases())


def summarize_job():
    """Job to summarize latest articles."""
    logger.info("[CRON] Scheduled: Running summarizer...")
    from services.summarizer import summarize_latest_articles
    run_async(summarize_latest_articles(10))


def start_scheduler() -> BackgroundScheduler:
    """Start the background scheduler with all jobs."""
    scheduler = BackgroundScheduler()
    
    # RSS feeds - every 15 minutes
    scheduler.add_job(
        fetch_rss_job,
        trigger=IntervalTrigger(seconds=FETCH_INTERVAL_RSS),
        id="fetch_rss",
        name="Fetch RSS Feeds",
        replace_existing=True
    )
    
    # Reddit - every 10 minutes
    scheduler.add_job(
        fetch_reddit_job,
        trigger=IntervalTrigger(seconds=FETCH_INTERVAL_REDDIT),
        id="fetch_reddit",
        name="Fetch Reddit Posts",
        replace_existing=True
    )
    
    # Weather - every 30 minutes
    scheduler.add_job(
        fetch_weather_job,
        trigger=IntervalTrigger(seconds=FETCH_INTERVAL_WEATHER),
        id="fetch_weather",
        name="Fetch Weather",
        replace_existing=True
    )
    
    # Traffic - every 15 minutes
    scheduler.add_job(
        fetch_traffic_job,
        trigger=IntervalTrigger(seconds=FETCH_INTERVAL_TRAFFIC),
        id="fetch_traffic",
        name="Fetch Traffic Alerts",
        replace_existing=True
    )
    
    # Sports - daily
    scheduler.add_job(
        fetch_sports_job,
        trigger=IntervalTrigger(seconds=FETCH_INTERVAL_SPORTS),
        id="fetch_sports",
        name="Fetch Sports Schedules",
        replace_existing=True
    )
    
    # Quick summarize job - every 5 minutes
    scheduler.add_job(
        summarize_job,
        trigger=IntervalTrigger(minutes=5),
        id="summarize",
        name="Summarize Articles",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("[SCHED] Background scheduler started")
    
    return scheduler
