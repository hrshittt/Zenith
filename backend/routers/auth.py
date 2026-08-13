from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import timedelta

from backend.database import get_db
from backend.models.domain import User, Profile
from backend.core.auth import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter(prefix="/auth", tags=["Auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    
    if not user:
        # Auto-signup for seamless onboarding
        hashed_password = pwd_context.hash(req.password)
        user = User(username=req.username, hashed_password=hashed_password)
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Check password format (handle transition from sha256 to bcrypt if needed)
        try:
            if not pwd_context.verify(req.password, user.hashed_password):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        except ValueError:
            # If they had an old sha256 password, just update it for them silently
            import hashlib
            if user.hashed_password == hashlib.sha256(req.password.encode()).hexdigest():
                user.hashed_password = pwd_context.hash(req.password)
                db.commit()
            else:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username,
        "profile_key": profile.key if profile else None
    }
