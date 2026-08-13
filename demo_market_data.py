import os
from backend.database import SessionLocal
from backend.market_intelligence.service import MarketIntelligenceService

def run_demo():
    print("Connecting to Market Intelligence Service...")
    db = SessionLocal()
    try:
        mi_service = MarketIntelligenceService(db)
        
        print("\n1. Fetching Exchange Rates (USD to INR)...")
        usd_inr = mi_service.get_exchange_rate("USDINR=X")
        print(f"   Result: 1 USD = {usd_inr} INR")
        
        print("\n2. Fetching Stock Data (NIFTY 50)...")
        nifty = mi_service.get_stock_price("^NSEI")
        print(f"   Result: NIFTY 50 = {nifty}")
        
        print("\n3. Fetching Economic Indicators (Inflation)...")
        # Assuming INFCPIITM is the FRED ticker for Indian CPI
        inflation = mi_service.get_economic_indicator("INFLATION_IN", "INFCPIITM")
        print(f"   Result: Inflation Indicator = {inflation}")
        
        print("\n4. Fetching News Sentiment ('indian economy')...")
        news = mi_service.get_news_sentiment("indian economy")
        print(f"   Result: News Sentiment Score = {news}")
        
        print("\n--- Summary ---")
        print(f"All this data is periodically stored and used by your AI agents to simulate how real-world conditions affect user financial profiles!")
        
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_demo()
