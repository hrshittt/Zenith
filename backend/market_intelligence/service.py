import os
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import json
try:
    import redis
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    # Check if redis is actually reachable
    redis_client.ping()
    REDIS_AVAILABLE = True
except Exception:
    REDIS_AVAILABLE = False
    print("Redis not available, falling back to Database/Memory cache")

from backend.market_intelligence.api_clients import YahooFinanceClient, NewsAPIClient, FREDClient, ExchangeRateClient
from backend.models.domain import MarketData, NewsItem, EconomicIndicator
from backend.services.gemini_service import gemini_service

logger = logging.getLogger(__name__)

class MarketIntelligenceService:
    def __init__(self, db: Session):
        self.db = db
        self.yahoo = YahooFinanceClient()
        self.news_api = NewsAPIClient()
        self.fred = FREDClient()
        self.exchange = ExchangeRateClient()

    def _get_from_cache(self, key):
        if REDIS_AVAILABLE:
            try:
                val = redis_client.get(key)
                if val:
                    return json.loads(val)
            except Exception as e:
                logger.error(f"Redis get error: {e}")
        return None

    def _set_cache(self, key, value, expire=3600):
        if REDIS_AVAILABLE:
            try:
                redis_client.setex(key, expire, json.dumps(value))
            except Exception as e:
                logger.error(f"Redis set error: {e}")

    def get_stock_price(self, symbol: str) -> float:
        cache_key = f"market_data:price:{symbol}"
        
        # 1. Check Redis Cache
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
            
        # 2. Check External API (Live)
        price = self.yahoo.get_price(symbol)
        if price is not None:
            # Save to Database history
            new_data = MarketData(symbol=symbol, asset_type='stock', price=price)
            self.db.add(new_data)
            self.db.commit()
            
            # Cache it
            self._set_cache(cache_key, price, expire=1800) # Cache for 30 mins
            return price
            
        # 3. Fallback to Database History (if live API fails)
        recent = self.db.query(MarketData).filter(MarketData.symbol == symbol).order_by(MarketData.timestamp.desc()).first()
        if recent:
            logger.info(f"Using fallback DB price for {symbol}")
            return recent.price
            
        # 4. Fallback to Seeded Mock Data
        mock_data = {
            "AAPL": 175.0,
            "RELIANCE.NS": 2800.0,
            "USDINR=X": 83.5
        }
        return mock_data.get(symbol, 100.0)

    def get_exchange_rate(self, pair: str) -> float:
        cache_key = f"market_data:exchange:{pair}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
            
        base = pair[:3]
        target = pair[3:6]
        rate = self.exchange.get_exchange_rate(base, target)
        
        if rate is not None:
            new_data = MarketData(symbol=pair, asset_type='forex', price=rate)
            self.db.add(new_data)
            self.db.commit()
            self._set_cache(cache_key, rate, expire=3600)
            return rate
            
        # Fallback to Database History
        recent = self.db.query(MarketData).filter(MarketData.symbol == pair).order_by(MarketData.timestamp.desc()).first()
        if recent:
            return recent.price
            
        # Fallback to Mock Data
        mock_data = {"USDINR=X": 83.5}
        return mock_data.get(pair, 1.0)

    def get_economic_indicator(self, name: str, fred_series_id: str) -> float:
        cache_key = f"market_data:indicator:{name}"
        
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
            
        value = self.fred.get_indicator(fred_series_id)
        if value is not None:
            new_ind = EconomicIndicator(indicator_name=name, value=value)
            self.db.add(new_ind)
            self.db.commit()
            self._set_cache(cache_key, value, expire=86400) # Cache for 1 day
            return value
            
        recent = self.db.query(EconomicIndicator).filter(EconomicIndicator.indicator_name == name).order_by(EconomicIndicator.timestamp.desc()).first()
        if recent:
            return recent.value
            
        # Mock Fallback
        mock_data = {
            "INFLATION_US": 3.4,
            "INFLATION_IN": 4.8,
            "REPO_RATE_IN": 6.5
        }
        return mock_data.get(name, 5.0)

    def analyze_news_sentiment(self, text: str) -> str:
        if not gemini_service.available():
            return "neutral"
        try:
            # Fast sentiment check using LLM
            prompt = f"Analyze the sentiment of this text strictly in one word: 'positive', 'neutral', or 'negative'. Text: {text}"
            result = gemini_service.generate(prompt, temperature=0.0, max_output_tokens=10)
            return result.strip().lower()
        except Exception:
            return "neutral"

    def get_news_sentiment(self, topic: str):
        cache_key = f"market_data:news:{topic}"
        
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
            
        articles = self.news_api.get_news(topic)
        if articles:
            # Process sentiment for the top article
            top_article = articles[0]
            headline = top_article.get("title", "")
            summary = top_article.get("description", "")
            sentiment = self.analyze_news_sentiment(f"{headline}. {summary}")
            
            new_item = NewsItem(headline=headline, summary=summary, sentiment=sentiment, category=topic)
            self.db.add(new_item)
            self.db.commit()
            
            result = {"headline": headline, "sentiment": sentiment}
            self._set_cache(cache_key, result, expire=7200) # 2 hours
            return result
            
        # DB fallback
        recent = self.db.query(NewsItem).filter(NewsItem.category == topic).order_by(NewsItem.timestamp.desc()).first()
        if recent:
            return {"headline": recent.headline, "sentiment": recent.sentiment}
            
        # Mock fallback
        return {"headline": f"General {topic} updates.", "sentiment": "neutral"}
