import io
import json
import pandas as pd
import PyPDF2
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List

from backend.database import get_db
from sqlalchemy.orm import Session
from backend.models.domain import Profile, User
from backend.agents.sub_agents import get_groq_client
from backend.core.auth import get_current_user

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
    
    client = get_groq_client()
    if not client:
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
    
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        {"id": "pay_debt", "label": "Pay off Debt", "primaryLabel": "Interest Saved", "primaryUnit": "$", "secondaryLabel": "Liquidity Hit", "secondaryUnit": "$"}
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
    client = get_groq_client()
    if not client:
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
    
    msgs = [{"role": "system", "content": system_prompt}]
    for m in req.messages:
        msgs.append({"role": m.role, "content": m.content})
        
    try:
        response = client.chat.completions.create(
            messages=msgs,
            model="llama-3.1-8b-instant"
        )
        return {"reply": response.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
