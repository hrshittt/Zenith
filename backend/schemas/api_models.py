from pydantic import BaseModel
from typing import List, Optional, Any, Dict

class Metric(BaseModel):
    id: str
    label: str
    value: float
    unit: str
    trend: List[float]
    isPercent: Optional[bool] = False

class Goal(BaseModel):
    title: str
    progress: float
    target: float

class Alert(BaseModel):
    level: str
    text: str

class DecisionHistory(BaseModel):
    title: str
    date: str
    outcome: str
    tag: str

class DecisionType(BaseModel):
    id: str
    label: str
    primaryLabel: str
    primaryUnit: str
    primaryStart: float
    impactRate: float
    goodDirection: str
    secondaryLabel: str
    secondaryUnit: str
    secondaryStart: float
    secondaryImpactRate: float
    inactionNote: str

class ProfileResponse(BaseModel):
    key: str
    label: str
    persona: str
    currency: str
    metrics: List[Metric]
    goal: Goal
    alerts: List[Alert]
    history: List[DecisionHistory]
    decisionTypes: List[DecisionType]

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatMessageModel(BaseModel):
    role: str
    content: str
    
class ChatSessionResponse(BaseModel):
    id: str
    title: str
    created_at: str

class ChatSessionDetail(ChatSessionResponse):
    messages: List[ChatMessageModel]

class ChatRenameRequest(BaseModel):
    title: str

class GenericResponse(BaseModel):
    success: bool
    message: Optional[str] = None

class ChatResponse(BaseModel):
    session_id: str
    answer: str
    confidence: str
    sources: List[Dict[str, str]]
    reasoning_trace: List[Dict[str, str]]
    disclaimer: str
    # Optional structured chart data for numeric/trend questions (Startup's Ask
    # Twin only, for now — always built from already-computed Financial Twin
    # metrics, never invented by the LLM). Individual leaves this unset.
    visualization: Optional[Dict[str, Any]] = None

class SimulateRequest(BaseModel):
    decision_id: str
    commitment_pct: int

class Outcome(BaseModel):
    label: str
    pct: int
    score: float
    primary_outcome: float
    secondary_outcome: float
    is_best: bool

class SimulateResponse(BaseModel):
    outcomes: List[Outcome]
    explanation: str

class ScenarioSimulateRequest(BaseModel):
    scenario: str

class StageTrace(BaseModel):
    agent: str
    status: str
    summary: str

class ScenarioSimulateResponse(BaseModel):
    scenario: str
    scenario_type: str
    mode: str = "scenario"  # "scenario" (Understand->Check pipeline) or "informational" (direct Ask Twin answer)
    parsed_params: Dict[str, Any]
    stages: List[StageTrace]
    financial_impact: Dict[str, Any]
    timeline: List[Dict[str, Any]]
    recommendation: str
    why: str
    risks: List[str]
    assumptions: List[str]
    teaching: str
    disclaimer: str
    # Optional — Startup only. Full-resolution baseline-vs-scenario cash series
    # for the Scenario Projection chart, and deterministic alternative-option
    # comparisons (e.g. "Don't hire" / "Hire 3" / "Hire 5"). Individual leaves
    # these unset; both are built entirely from startup_engine/startup_scenario,
    # never from the LLM.
    timeline_series: Optional[Dict[str, Any]] = None
    comparison_variants: Optional[List[Dict[str, Any]]] = None
