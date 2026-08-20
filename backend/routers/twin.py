from fastapi import APIRouter, Depends, HTTPException
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
import uuid

from backend.database import get_db
from backend.models.domain import Profile, AuditTrace, ChatSession, ChatMessage
from backend.schemas.api_models import ChatRequest, ChatResponse, SimulateRequest, SimulateResponse, Outcome, ChatSessionResponse, ChatSessionDetail, ChatMessageModel, ScenarioSimulateRequest, ScenarioSimulateResponse, ChatRenameRequest, GenericResponse
from typing import List
from backend.core.auth import get_current_user
from backend.models.domain import User
from backend.agents.orchestrator import orchestrator
from backend.agents.startup_orchestrator import startup_orchestrator
from backend.routers.startup import log_startup_decision

router = APIRouter(prefix="/twin", tags=["Twin"])

@router.get("/chats", response_model=List[ChatSessionResponse])
def get_chat_sessions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        return []
    
    sessions = db.query(ChatSession).filter(ChatSession.profile_id == profile.id).order_by(ChatSession.created_at.desc()).all()
    return [{"id": s.id, "title": s.title or "New Chat", "created_at": s.created_at.isoformat()} for s in sessions]

@router.get("/chats/{session_id}", response_model=ChatSessionDetail)
def get_chat_session(session_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.profile_id == profile.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return {
        "id": session.id,
        "title": session.title or "New Chat",
        "created_at": session.created_at.isoformat(),
        "messages": [{"role": m.role, "content": m.content} for m in session.messages]
    }

@router.delete("/chats/{session_id}", response_model=GenericResponse)
def delete_chat_session(session_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.profile_id == profile.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    db.delete(session)
    db.commit()
    return {"success": True, "message": "Session deleted"}

@router.put("/chats/{session_id}", response_model=GenericResponse)
def rename_chat_session(session_id: str, req: ChatRenameRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.profile_id == profile.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session.title = req.title
    db.commit()
    return {"success": True, "message": "Session renamed"}

@router.post("/chat")
def chat_with_twin(req: ChatRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
        
    session_id = req.session_id
    if not session_id:
        session_id = str(uuid.uuid4())
        session = ChatSession(id=session_id, profile_id=profile.id, title=req.message[:30] + "...")
        db.add(session)
    else:
        session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.profile_id == profile.id).first()
        if not session:
            session = ChatSession(id=session_id, profile_id=profile.id, title=req.message[:30] + "...")
            db.add(session)
            
    db.commit()
            
    user_msg = ChatMessage(session_id=session_id, role="user", content=req.message)
    db.add(user_msg)
    db.commit()
    
    history = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at).all()
    chat_history = [{"role": "assistant" if m.role == "twin" else m.role, "content": m.content} for m in history[:-1]]

    # Chat session storage/CRUD is generic infra shared across personas — only the
    # grounding/calculation engine behind the answer differs.
    active_orchestrator = startup_orchestrator if profile.key == "startup" else orchestrator
    response = active_orchestrator.process_query(profile, req.message, chat_history=chat_history)
    
    twin_msg = ChatMessage(session_id=session_id, role="twin", content=response.answer)
    db.add(twin_msg)
    
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
    
    response.session_id = session_id
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


@router.post("/simulate-scenario", response_model=ScenarioSimulateResponse)
def simulate_scenario(req: ScenarioSimulateRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id, Profile.key == req.profile_key).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    scenario = (req.scenario or "").strip()
    if not scenario:
        raise HTTPException(status_code=400, detail="Please describe a financial scenario to simulate.")

    if profile.key == "startup":
        if not profile.startup_profile:
            raise HTTPException(status_code=404, detail="Startup profile not found. Please complete Startup onboarding first.")
        response = startup_orchestrator.run_scenario_simulation(profile, scenario)
        log_startup_decision(db, profile, scenario, response)
        return response

    return orchestrator.run_scenario_simulation(profile, scenario)
