from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.database import engine, Base
from backend.scheduler import start_scheduler, stop_scheduler

# Create tables (we will move this or handle it properly later)
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()

from backend.routers import profile, twin, onboarding, auth

app = FastAPI(title="Agentic Financial Decision Twin", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(twin.router)
app.include_router(onboarding.router)

# Allow CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, this should be specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Agentic Financial Decision Twin API is running"}
