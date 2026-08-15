import os
import requests
import yfinance as yf
import logging

logger = logging.getLogger(__name__)

import requests as _requests

class YahooFinanceClient:
    def get_price(self, symbol: str) -> float:
        try:
            session = _requests.Session()
            session.request = lambda *args, **kwargs: _requests.Session.request(session, *args, **{**kwargs, "timeout": 5})
            ticker = yf.Ticker(symbol, session=session)
            # Use '1d' to get current day's price
            todays_data = ticker.history(period='1d')
            if not todays_data.empty:
                return float(todays_data['Close'].iloc[0])
            return None
        except Exception as e:
            logger.error(f"Error fetching from Yahoo Finance for {symbol}: {e}")
            return None

class NewsAPIClient:
    def __init__(self):
        self.api_key = os.getenv("NEWS_API_KEY")
        
    def get_news(self, query: str = "finance"):
        if not self.api_key or self.api_key == "dummy":
            logger.warning("No valid NEWS_API_KEY found")
            return []
        try:
            url = f"https://newsapi.org/v2/everything?q={query}&apiKey={self.api_key}"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            return data.get("articles", [])[:5]
        except Exception as e:
            logger.error(f"Error fetching News: {e}")
            return []

class FREDClient:
    def __init__(self):
        self.api_key = os.getenv("FRED_API_KEY")
        
    def get_indicator(self, series_id: str) -> float:
        if not self.api_key or self.api_key == "dummy":
            logger.warning("No valid FRED_API_KEY found")
            return None
        try:
            url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={self.api_key}&file_type=json"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            observations = data.get("observations", [])
            # Find the last valid observation
            for obs in reversed(observations):
                val = obs.get("value")
                if val and val != ".":
                    return float(val)
            return None
        except Exception as e:
            logger.error(f"Error fetching FRED data for {series_id}: {e}")
            return None

class ExchangeRateClient:
    def __init__(self):
        self.api_key = os.getenv("EXCHANGE_RATE_API_KEY")
        
    def get_exchange_rate(self, base: str, target: str) -> float:
        if not self.api_key or self.api_key == "dummy":
            logger.warning("No valid EXCHANGE_RATE_API_KEY found")
            return None
        try:
            url = f"https://v6.exchangerate-api.com/v6/{self.api_key}/pair/{base}/{target}"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            if data.get("result") == "success":
                return float(data.get("conversion_rate"))
            return None
        except Exception as e:
            logger.error(f"Error fetching exchange rate for {base}/{target}: {e}")
            return None
