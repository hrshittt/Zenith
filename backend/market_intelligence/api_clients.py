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
            response = requests.get(url, timeout=15)
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
        self.base_url = os.getenv("EXCHANGE_RATE_API_URL", "https://api.frankfurter.dev/v2")

    def get_exchange_rate(self, base: str, target: str) -> float:
        try:
            url = f"{self.base_url}/rate/{base}/{target}"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            rate = data.get("rate")
            return float(rate) if rate is not None else None
        except Exception as e:
            logger.error(f"Error fetching exchange rate for {base}/{target}: {e}")
            return None


class AlphaVantageClient:
    def __init__(self):
        self.api_key = os.getenv("ALPHA_VANTAGE_API_KEY")

    def get_quote(self, symbol: str) -> float:
        if not self.api_key or self.api_key == "dummy":
            logger.warning("No valid ALPHA_VANTAGE_API_KEY found")
            return None
        try:
            url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={self.api_key}"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            price = data.get("Global Quote", {}).get("05. price")
            return float(price) if price else None
        except Exception as e:
            logger.error(f"Error fetching Alpha Vantage quote for {symbol}: {e}")
            return None


class CoinGeckoClient:
    def __init__(self):
        self.api_key = os.getenv("COINGECKO_API_KEY")

    def get_price(self, coin_id: str = "bitcoin", vs_currency: str = "usd") -> float:
        try:
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies={vs_currency}"
            headers = {"x-cg-demo-api-key": self.api_key} if self.api_key else {}
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()
            return float(data.get(coin_id, {}).get(vs_currency))
        except Exception as e:
            logger.error(f"Error fetching CoinGecko price for {coin_id}: {e}")
            return None
