import io
import pandas as pd
import PyPDF2
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List

from backend.database import get_db
from sqlalchemy.orm import Session
from backend.models.domain import Profile, User, StartupProfile
from backend.services.gemini_service import gemini_service
from backend.core.auth import get_current_user
from backend.schemas.startup_models import StartupOnboardingRequest, StartupOverviewResponse
from backend.agents.startup_orchestrator import startup_orchestrator
from backend.routers.startup import build_overview_payload, log_startup_decision

router = APIRouter(prefix="/onboard", tags=["Onboarding"])

def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    if filename.endswith(".pdf"):
        try:
            reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted
            return text
        except Exception:
            return ""
    elif filename.endswith(".csv"):
        try:
            df = pd.read_csv(io.BytesIO(file_bytes))
            return df.to_csv(index=False)
        except:
            return ""
    elif filename.endswith((".xls", ".xlsx")):
        try:
            df = pd.read_excel(io.BytesIO(file_bytes))
            return df.to_csv(index=False)
        except:
            return ""
    return file_bytes.decode('utf-8', errors='ignore')

@router.post("/parse-statement")
async def parse_statement(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    contents = await file.read()
    text = extract_text_from_file(contents, file.filename)

    if not gemini_service.available():
        raise HTTPException(status_code=500, detail="LLM client not configured")

    prompt = f"""
    You are a financial data extraction AI. Extract the following from this bank statement/text:
    - Monthly Salary (Income)
    - Total Savings/Balance
    - Average Monthly Expenses (Categorized into Food, Rent, EMI, Shopping, Others)
    - Any active Loans detected

    Text: {text[:5000]}

    Output ONLY valid JSON matching this exact structure:
    {{
        "salary": 0,
        "savings": 0,
        "expenses": {{ "food": 0, "rent": 0, "emi": 0, "shopping": 0, "others": 0 }},
        "loans": 0
    }}
    """

    data = gemini_service.generate_json(prompt, temperature=0.1)
    if data is None:
        raise HTTPException(status_code=500, detail="Failed to parse statement")
    return data

from typing import Union

class SaveProfileRequest(BaseModel):
    persona: str
    metrics: List[Dict[str, Any]]

@router.post("/confirm")
def confirm_profile(req: SaveProfileRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile_key = f"custom_{current_user.username}"
    
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        profile = Profile(user_id=current_user.id, key=profile_key, label=req.persona.capitalize(), persona=f"{req.persona.capitalize()} (Custom)")
        db.add(profile)
    profile.currency = "₹"
    
    profile.metrics = req.metrics
    profile.goal = {"title": "Financial Independence", "progress": 25}
    profile.decisionTypes = [
        {"id": "invest_index", "label": "Invest in Index Fund", "primaryLabel": "Est. Return", "primaryUnit": "%", "secondaryLabel": "Risk", "secondaryUnit": " lvl"},
        {"id": "pay_debt", "label": "Pay off Debt", "primaryLabel": "Interest Saved", "primaryUnit": "₹", "secondaryLabel": "Liquidity Hit", "secondaryUnit": "₹"}
    ]
    
    db.commit()
    return {"status": "ok", "profile_key": profile_key}

class ChatMessage(BaseModel):
    role: str
    content: str

class AiOnboardingRequest(BaseModel):
    messages: List[ChatMessage]

@router.post("/chat")
def ai_onboarding_chat(req: AiOnboardingRequest, current_user: User = Depends(get_current_user)):
    if not gemini_service.available():
        raise HTTPException(status_code=500, detail="LLM client not configured.")

    system_prompt = """You are a financial onboarding AI for Indian users. All amounts are in Indian Rupees (₹) — always use the ₹ symbol when referring to money, never $. Ask the user 3 to 4 short, conversational questions one by one to figure out their monthly salary, total savings, average monthly expenses, and any active loans.

Once you have enough information, reply with the exact word ONBOARDING_COMPLETE followed immediately by a JSON block. The JSON MUST match this exact structure and these exact keys (numbers only, no currency symbols, no strings):

{
    "salary": 0,
    "savings": 0,
    "expenses": { "food": 0, "rent": 0, "emi": 0, "shopping": 0, "others": 0 },
    "loans": 0
}

Do not include any other text, explanation, or markdown after the JSON. Do not rename any keys. If a value wasn't mentioned by the user, estimate 0 for it rather than omitting the key."""

    msgs = [{"role": m.role, "content": m.content} for m in req.messages]
    if not msgs:
        raise HTTPException(status_code=400, detail="No messages provided.")

    try:
        reply = gemini_service.generate(
            msgs[-1]["content"],
            system_instruction=system_prompt,
            chat_history=msgs[:-1],
        )
        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/startup", response_model=StartupOverviewResponse)
def onboard_startup(req: StartupOnboardingRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Builds the Startup Financial Twin from the founder's onboarding wizard —
    completely separate from Individual's /onboard/confirm (own model, own
    engine, own dashboard)."""
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        profile = Profile(user_id=current_user.id)
        db.add(profile)
        db.flush()

    profile.key = "startup"
    profile.label = "Startup"
    profile.persona = req.company.name
    profile.currency = "₹"
    db.commit()
    db.refresh(profile)

    sp = profile.startup_profile
    if not sp:
        sp = StartupProfile(profile_id=profile.id)
        db.add(sp)

    sp.founder_name = req.founder.name
    sp.founder_email = req.founder.email
    sp.founder_mobile = req.founder.mobile
    sp.preferred_language = req.founder.preferred_language
    sp.company_name = req.company.name
    sp.industry = req.company.industry
    sp.business_model = req.company.business_model
    sp.founded_year = req.company.founded_year
    sp.stage = req.company.stage
    sp.location = req.company.location
    sp.website = req.company.website
    sp.headcount = req.company.headcount
    sp.is_pre_revenue = req.revenue.is_pre_revenue
    sp.monthly_revenue = None if req.revenue.is_pre_revenue else req.revenue.monthly_revenue
    sp.revenue_streams = req.revenue.revenue_streams
    sp.revenue_growth_pct_input = req.revenue.revenue_growth_pct
    sp.paying_customers = req.revenue.paying_customers
    sp.fixed_costs = req.expenses.fixed_costs
    sp.variable_costs = req.expenses.variable_costs
    sp.current_cash = req.cash.current_cash
    sp.monthly_burn_input = req.cash.monthly_burn
    sp.business_loans_debt = req.debt.business_loans_debt
    sp.total_funding = req.funding.total_funding
    sp.last_round = req.funding.last_round
    sp.currently_fundraising = req.funding.currently_fundraising
    sp.fundraising_target = req.funding.fundraising_target
    sp.planned_hires = req.team.planned_hires
    sp.cost_per_hire = req.team.cost_per_hire
    sp.goals = [g.model_dump() for g in req.goals]
    sp.current_decision = req.current_decision

    db.commit()
    db.refresh(profile)
    db.refresh(sp)

    # Log the founder's "current financial decision" as the first Recent Decision,
    # if it parses into a computable scenario (deterministic — same pipeline as Simulate).
    if req.current_decision and req.current_decision.strip():
        try:
            sim_response = startup_orchestrator.run_scenario_simulation(profile, req.current_decision.strip())
            log_startup_decision(db, profile, req.current_decision.strip(), sim_response)
        except Exception:
            pass  # Onboarding should never fail because the decision text didn't parse cleanly.

    return build_overview_payload(db, profile)
