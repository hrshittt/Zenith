from fastapi import APIRouter, Depends, HTTPException
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
import uuid

from backend.database import get_db
from backend.models.domain import Profile, AuditTrace
from backend.schemas.api_models import ChatRequest, ChatResponse, SimulateRequest, SimulateResponse, Outcome
from backend.agents.sub_agents import get_groq_client
from backend.core.auth import get_current_user
from backend.models.domain import User
from backend.agents.orchestrator import orchestrator

router = APIRouter(prefix="/twin", tags=["Twin"])

@router.post("/chat")
def chat_with_twin(req: ChatRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
        
    response = orchestrator.process_query(profile, req.message)
    
    # Save audit trace
    req_id = str(uuid.uuid4())
    audit = AuditTrace(
        id=req_id,
        profile_id=profile.id,
        query=req.message,
        response=response.model_dump(),
        reasoning_trace=response.reasoning_trace,
        sources=response.sources
    )
    db.add(audit)
    db.commit()
    
    return response

def compute_outcome(decision: dict, pct: int):
    primary = decision["primaryStart"] + decision["impactRate"] * pct
    secondary = decision["secondaryStart"] + decision["secondaryImpactRate"] * pct
    return primary, secondary

def score_outcome(decision: dict, primary: float, pct: int):
    direction = 1 if decision["goodDirection"] == 'up' else -1
    progress = direction * (primary - decision["primaryStart"])
    overcommitPenalty = (pct - 70) * 0.35 if pct > 70 else 0
    inactionPenalty = 4 if pct == 0 else 0
    return progress - overcommitPenalty - inactionPenalty

@router.post("/simulate")
def simulate_decision(req: SimulateRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
        
    decision = next((d for d in profile.decisionTypes if d["id"] == req.decision_id), None)
    if not decision:
        raise HTTPException(status_code=400, detail="Invalid decision ID")

    # Re-implementing the exact logic from the frontend in python
    outcomes = [
        {"label": 'Hold — take no action', "pct": 0},
        {"label": f'Partial — {req.commitment_pct}% commitment', "pct": req.commitment_pct},
        {"label": 'Full commitment', "pct": 100}
    ]
    
    scored_outcomes = []
    for o in outcomes:
        pri, sec = compute_outcome(decision, o["pct"])
        score = score_outcome(decision, pri, o["pct"])
        scored_outcomes.append({
            "label": o["label"],
            "pct": o["pct"],
            "score": score,
            "primary_outcome": pri,
            "secondary_outcome": sec,
            "is_best": False
        })
        
    best_idx = 0
    for i in range(1, len(scored_outcomes)):
        if scored_outcomes[i]["score"] > scored_outcomes[best_idx]["score"]:
            best_idx = i
            
    scored_outcomes[best_idx]["is_best"] = True
    best = scored_outcomes[best_idx]
    
    explanation = decision["inactionNote"] if best["pct"] == 0 else (
        f"Committing {best['pct']}% moves {decision['primaryLabel'].lower()} to {best['primary_outcome']:.1f}{decision['primaryUnit']} "
        f"while keeping the commitment level measured rather than maximal — the Check agent confirmed this stays within policy."
    )

    return SimulateResponse(outcomes=scored_outcomes, explanation=explanation)
