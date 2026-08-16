from pydantic import BaseModel
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Onboarding request
# ---------------------------------------------------------------------------

class FounderInfo(BaseModel):
    name: str
    email: str
    mobile: Optional[str] = None
    preferred_language: Optional[str] = None


class CompanyInfo(BaseModel):
    name: str
    industry: Optional[str] = None
    business_model: Optional[str] = None
    founded_year: Optional[int] = None
    stage: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    headcount: Optional[int] = None


class RevenueInfo(BaseModel):
    is_pre_revenue: bool = False
    monthly_revenue: Optional[float] = None
    revenue_streams: List[str] = []
    revenue_growth_pct: Optional[float] = None
    paying_customers: Optional[int] = None


class ExpensesInfo(BaseModel):
    fixed_costs: Optional[float] = None
    variable_costs: Optional[float] = None


class CashInfo(BaseModel):
    current_cash: Optional[float] = None
    monthly_burn: Optional[float] = None  # fallback if fixed/variable costs weren't itemized


class DebtInfo(BaseModel):
    business_loans_debt: Optional[float] = None


class FundingInfo(BaseModel):
    total_funding: Optional[float] = None
    last_round: Optional[str] = None
    currently_fundraising: bool = False
    fundraising_target: Optional[float] = None


class TeamInfo(BaseModel):
    planned_hires: Optional[int] = None
    cost_per_hire: Optional[float] = None


class GoalInput(BaseModel):
    type: str  # extend_runway | revenue_milestone | fundraise | profitability | custom
    label: str
    target_value: Optional[float] = None
    target_unit: Optional[str] = None
    target_date: Optional[str] = None


class StartupOnboardingRequest(BaseModel):
    founder: FounderInfo
    company: CompanyInfo
    revenue: RevenueInfo
    expenses: ExpensesInfo
    cash: CashInfo
    debt: DebtInfo
    funding: FundingInfo
    team: TeamInfo
    goals: List[GoalInput] = []
    current_decision: Optional[str] = None


# ---------------------------------------------------------------------------
# Computed / response models
# ---------------------------------------------------------------------------

class MetricResultModel(BaseModel):
    id: str
    label: str
    value: Optional[float]
    unit: str
    display: str
    status: str
    calculation: Dict[str, Any]


class GoalProgressModel(BaseModel):
    type: str
    label: str
    target_value: Optional[float] = None
    target_unit: Optional[str] = None
    target_date: Optional[str] = None
    current_value: Optional[float] = None
    progress_pct: Optional[float] = None
    status: str
    note: Optional[str] = None
    expected_completion_date: Optional[str] = None
    projection_note: Optional[str] = None


class AlertItemModel(BaseModel):
    category: str
    level: str
    severity: str  # critical | high | medium | low
    metric: Optional[str] = None
    text: str


class DecisionLogItemModel(BaseModel):
    title: str
    decision_type: Optional[str] = None
    outcome: Optional[str] = None
    tag: str
    created_at: str
    predicted: Optional[Dict[str, Any]] = None
    actual_now: Optional[Dict[str, Any]] = None
    decision_status: Optional[str] = None  # on_track | diverged | pending | unknown


class HealthIndicatorModel(BaseModel):
    id: str
    label: str
    status: str  # good | warning | serious | critical | insufficient_data
    display: str
    detail: str


class CompanyProfileModel(BaseModel):
    company_name: Optional[str]
    industry: Optional[str]
    business_model: Optional[str]
    founded_year: Optional[int]
    stage: Optional[str]
    location: Optional[str]
    website: Optional[str]
    headcount: Optional[int]
    founder_name: Optional[str]
    preferred_language: Optional[str]


class StartupOverviewResponse(BaseModel):
    currency: str
    company: CompanyProfileModel
    metrics: Dict[str, MetricResultModel]
    cash_projection: Dict[str, Any]
    hiring_capacity: Dict[str, Any]
    goals: List[GoalProgressModel]
    alerts: List[AlertItemModel]
    recent_decisions: List[DecisionLogItemModel]
    daily_brief: Dict[str, Any]
    health_indicators: List[HealthIndicatorModel]
    history: List[Dict[str, Any]]
    expense_breakdown: Dict[str, Any]
    revenue_breakdown: Dict[str, Any]


# ---------------------------------------------------------------------------
# Hisaab
# ---------------------------------------------------------------------------

class TransactionCreate(BaseModel):
    type: str  # 'in' | 'out'
    category: str
    amount: float
    description: Optional[str] = None
    txn_date: Optional[str] = None


class TransactionResponse(BaseModel):
    id: int
    type: str
    category: str
    amount: float
    description: Optional[str]
    txn_date: str
    created_at: str


class HisaabSummaryResponse(BaseModel):
    currency: str
    money_in: float
    money_out: float
    net: float
    by_category: List[Dict[str, Any]]
    transactions: List[TransactionResponse]


class WeeklyReportResponse(BaseModel):
    status: str
    window_days: int
    days_present: int
    points: List[Dict[str, Any]]
    note: Optional[str] = None
    health_delta: Optional[float] = None
    cash_delta: Optional[float] = None
    runway_delta: Optional[float] = None
