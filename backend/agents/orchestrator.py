from typing import Dict, Any, List
import uuid
import datetime

from backend.agents.sub_agents import data_agent, risk_agent, compliance_agent, explainer_agent
from backend.schemas.api_models import ChatResponse
from backend.market_intelligence.service import MarketIntelligenceService
from backend.database import SessionLocal

class Orchestrator:
    def process_query(self, profile: Any, query: str) -> ChatResponse:
        trace = []
        
        # 0. Fetch Market Intelligence Context
        db = SessionLocal()
        try:
            mi_service = MarketIntelligenceService(db)
            usd_inr = mi_service.get_exchange_rate("USDINR=X")
            nifty = mi_service.get_stock_price("^NSEI")
            inflation = mi_service.get_economic_indicator("INFLATION_IN", "INFCPIITM")
            news = mi_service.get_news_sentiment("finance")
            
            mi_context = {
                "USDINR": usd_inr,
                "NIFTY": nifty,
                "INFLATION_IN": inflation,
                "news_sentiment": news
            }
        except Exception as e:
            mi_context = {"error": str(e)}
        finally:
            db.close()
        
        # 1. Data Agent
        data_ctx = {"profile_id": profile.id, "metrics": profile.metrics, "alerts": profile.alerts, "market_intelligence": mi_context}
        data_res = data_agent.process(data_ctx, f"Extract required data for query: {query}")
        trace.append({"agent": "Data", "action": "Fetched user profile metrics, alerts, and market intelligence", "output": data_res})
        
        # 2. Risk/Simulation Agent
        risk_res = risk_agent.process({"data": data_res}, f"Simulate financial impact for query: {query}")
        trace.append({"agent": "Risk", "action": "Simulated potential outcomes", "output": risk_res})
        
        # 3. Compliance Agent
        comp_res = compliance_agent.process({"simulation": risk_res}, f"Check for unlicensed advice flags in this context: {query}")
        trace.append({"agent": "Compliance", "action": "Checked against guardrails", "output": comp_res})
        
        # 4. Explainer Agent
        exp_res = explainer_agent.process({"data": data_res, "simulation": risk_res, "compliance": comp_res}, 
                                          f"Format response as a 10-point response for query: {query}")
        trace.append({"agent": "Explainer", "action": "Formatted final structured output", "output": exp_res})
        
        # Construct response
        response = ChatResponse(
            answer=exp_res,
            confidence="high",
            sources=[
                {"source": "Profile Database", "timestamp": datetime.datetime.utcnow().isoformat()},
                {"source": "Market Intelligence API", "timestamp": datetime.datetime.utcnow().isoformat()}
            ],
            reasoning_trace=trace,
            disclaimer="This is an AI-generated simulation and does not constitute financial advice. " + comp_res
        )
        return response

orchestrator = Orchestrator()
