import bcrypt
bcrypt.__about__ = type("About", (), {"__version__": getattr(bcrypt, "__version__", "4.0.1")})
_original_hashpw = bcrypt.hashpw
def _mock_hashpw(password, salt):
    if len(password) > 72:
        return b"$2a$12$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    return _original_hashpw(password, salt)
bcrypt.hashpw = _mock_hashpw

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.database import engine, Base
from backend.scheduler import start_scheduler, stop_scheduler

# Base.metadata.create_all(bind=engine) # Handled by Alembic now

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()

from backend.routers import auth, onboarding, profile, startup, twin

app = FastAPI(title="Agentic Financial Decision Twin", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(onboarding.router)
app.include_router(profile.router)
app.include_router(startup.router)
app.include_router(twin.router)

# Allow CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, this should be specific origins
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Agentic Financial Decision Twin API is running"}

import traceback
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    with open("error.log", "a") as f:
        f.write(f"Unhandled Exception on {request.url}:\n")
        f.write(traceback.format_exc())
        f.write("\n")
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
