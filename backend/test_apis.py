"""Quick standalone check for every external API key in .env.
Run with: python -m backend.test_apis
"""
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

def check(name, fn):
    try:
        result = fn()
        print(f"✅ {name}: OK -> {result}")
    except Exception as e:
        print(f"❌ {name}: FAILED -> {e}")

print("=== Testing external APIs ===\n")

# 1. Gemini
def test_gemini():
    from backend.services.gemini_service import gemini_service
    if not gemini_service.available():
        raise RuntimeError("client not configured / key missing")
    return gemini_service.generate("Say 'ok' and nothing else.", temperature=0.0, max_output_tokens=5)
check("Gemini", test_gemini)

# 2. Groq
def test_groq():
    from backend.services.groq_service import groq_service
    if not groq_service.available():
        raise RuntimeError("client not configured / key missing")
    return groq_service.generate("Say 'ok' and nothing else.")
check("Groq", test_groq)

# 3. NewsAPI
def test_news():
    from backend.market_intelligence.api_clients import NewsAPIClient
    client = NewsAPIClient()
    articles = client.get_news("startup")
    if not articles:
        raise RuntimeError("no articles returned (key may be invalid or rate-limited)")
    return f"{len(articles)} articles, first: {articles[0].get('title')}"
check("NewsAPI", test_news)

# 4. FRED
def test_fred():
    from backend.market_intelligence.api_clients import FREDClient
    client = FREDClient()
    value = client.get_indicator("CPIAUCSL")  # adjust series id if needed
    if value is None:
        raise RuntimeError("no value returned (key or series id may be invalid)")
    return value
check("FRED", test_fred)

# 5. Exchange Rate
def test_exchange_rate():
    from backend.market_intelligence.api_clients import ExchangeRateClient
    client = ExchangeRateClient()
    rate = client.get_exchange_rate("USD", "INR")
    if rate is None:
        raise RuntimeError("no rate returned (key or endpoint may be invalid)")
    return rate
check("ExchangeRate", test_exchange_rate)

# 6. Alpha Vantage
def test_alpha_vantage():
    from backend.market_intelligence.api_clients import AlphaVantageClient
    client = AlphaVantageClient()
    price = client.get_quote("AAPL")
    if price is None:
        raise RuntimeError("no price returned (key may be invalid or rate-limited)")
    return price
check("AlphaVantage", test_alpha_vantage)

# 7. CoinGecko
def test_coingecko():
    from backend.market_intelligence.api_clients import CoinGeckoClient
    client = CoinGeckoClient()
    price = client.get_price("bitcoin", "usd")
    if price is None:
        raise RuntimeError("no price returned")
    return price
check("CoinGecko", test_coingecko)

print("\n=== Done ===")