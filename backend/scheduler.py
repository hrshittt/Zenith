import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime

from backend.database import SessionLocal
from backend.models.domain import Profile, Alert

logger = logging.getLogger(__name__)

from backend.market_intelligence.service import MarketIntelligenceService

def evaluate_profiles():
    db = SessionLocal()
    try:
        # Fetch Market Intelligence proactively
        mi_service = MarketIntelligenceService(db)
        usd_inr = mi_service.get_exchange_rate("USDINR=X")
        nifty = mi_service.get_stock_price("^NSEI")
        inflation = mi_service.get_economic_indicator("INFLATION_IN", "INFCPIITM")
        news = mi_service.get_news_sentiment("indian economy")
        
        logger.info(f"Scheduler fetched Market Data - USDINR: {usd_inr}, NIFTY: {nifty}, Inflation: {inflation}, News: {news}")

        profiles = db.query(Profile).all()
        for profile in profiles:
            # Example logic for proactive alert generation
            # In a real scenario, this would call out to the Data Agent to fetch live data
            # and Risk Agent to simulate constraints.
            
            if profile.key == "individual":
                # Check goal progress artificially
                if profile.goal.get("progress", 0) < 50:
                    pass # We could add an alert here
            elif profile.key == "startup":
                pass
            elif profile.key == "enterprise":
                pass
            
            # For demonstration, we simply log that evaluation happened
            logger.info(f"Evaluated profile {profile.key} at {datetime.now()}")
            
    finally:
        db.close()

scheduler = BackgroundScheduler()

def start_scheduler():
    scheduler.add_job(
        evaluate_profiles,
        trigger=IntervalTrigger(minutes=60), # Run every hour
        id="evaluate_profiles",
        name="Evaluate user financial profiles against live market data",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Background scheduler started")

def stop_scheduler():
    scheduler.shutdown()
