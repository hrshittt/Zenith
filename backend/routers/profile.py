from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from backend.database import get_db
from backend.models.domain import User, Profile, Alert, DecisionHistory
from backend.core.auth import get_current_user

router = APIRouter(prefix="/profile", tags=["Profile"])

@router.get("/me")
def get_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found for this user. Please complete onboarding.")
    
    # Return formatted profile for frontend
    return {
        "key": profile.key,
        "label": profile.label,
        "persona": profile.persona,
        "currency": profile.currency or "₹",
        "metrics": profile.metrics,
        "goal": profile.goal,
        "alerts": [{"level": a.level, "text": a.text} for a in profile.alerts],
        "history": [{"title": h.title, "date_str": h.date_str, "outcome": h.outcome, "tag": h.tag} for h in profile.history],
        "decisionTypes": profile.decisionTypes
    }
