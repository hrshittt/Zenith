"""
Deterministic financial engine for the Startup journey.

This is the Startup twin's single source of truth for numbers — completely
separate from `financial_simulator.py` (Individual). Every metric here is
computed by plain Python from the founder's onboarded data + stored metric
history, never invented by an LLM. Each result carries a `status` (one of
`actual | forecast | estimated | assumption | insufficient_data`) and a
`calculation` block (inputs, formula, data source, last-updated) so the
frontend can render a "How is this calculated?" explanation for every
number on the Startup Overview.
"""
import math
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.models.domain import StartupProfile, StartupMetricSnapshot


# ---------------------------------------------------------------------------
# Status ranking — used to propagate the *weakest* status through a chain of
# derived metrics (e.g. Runway inherits the weaker of Cash's and Net Burn's
# status), so a derived number is never labeled more confidently than the
# inputs it was built from.
# ---------------------------------------------------------------------------
STATUS_RANK = {"insufficient_data": 0, "forecast": 1, "assumption": 2, "estimated": 3, "actual": 4}


def combine_status(*statuses: str) -> str:
    valid = [s for s in statuses if s]
    if not valid:
        return "insufficient_data"
    return min(valid, key=lambda s: STATUS_RANK.get(s, 0))


RUNWAY_FLOOR_MONTHS = 6.0  # safety threshold used for hiring capacity + alerts


@dataclass
class StartupContext:
    currency: str
    profile_id: int
    company_name: Optional[str]
    stage: Optional[str]
    updated_at: Optional[datetime]

    is_pre_revenue: bool
    monthly_revenue: Optional[float]
    revenue_streams: List[str]
    revenue_growth_pct_input: Optional[float]
    paying_customers: Optional[int]

    fixed_costs: Optional[float]
    variable_costs: Optional[float]
    monthly_burn_input: Optional[float]

    current_cash: Optional[float]
    business_loans_debt: Optional[float]

    total_funding: Optional[float]
    last_round: Optional[str]
    currently_fundraising: bool
    fundraising_target: Optional[float]

    headcount: Optional[int]
    planned_hires: Optional[int]
    cost_per_hire: Optional[float]

    goals: List[Dict[str, Any]] = field(default_factory=list)
    current_decision: Optional[str] = None


def build_context(sp: StartupProfile) -> StartupContext:
    return StartupContext(
        currency="₹",
        profile_id=sp.profile_id,
        company_name=sp.company_name,
        stage=sp.stage,
        updated_at=sp.updated_at,
        is_pre_revenue=bool(sp.is_pre_revenue),
        monthly_revenue=sp.monthly_revenue,
        revenue_streams=sp.revenue_streams or [],
        revenue_growth_pct_input=sp.revenue_growth_pct_input,
        paying_customers=sp.paying_customers,
        fixed_costs=sp.fixed_costs,
        variable_costs=sp.variable_costs,
        monthly_burn_input=sp.monthly_burn_input,
        current_cash=sp.current_cash,
        business_loans_debt=sp.business_loans_debt,
        total_funding=sp.total_funding,
        last_round=sp.last_round,
        currently_fundraising=bool(sp.currently_fundraising),
        fundraising_target=sp.fundraising_target,
        headcount=sp.headcount,
        planned_hires=sp.planned_hires,
        cost_per_hire=sp.cost_per_hire,
        goals=sp.goals or [],
        current_decision=sp.current_decision,
    )


@dataclass
class MetricResult:
    id: str
    label: str
    value: Optional[float]
    unit: str
    display: str
    status: str  # actual | forecast | estimated | assumption | insufficient_data
    calculation: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "label": self.label, "value": self.value, "unit": self.unit,
            "display": self.display, "status": self.status, "calculation": self.calculation,
        }


def _calc_meta(inputs: Dict[str, Any], formula: str, data_source: str, last_updated: Optional[datetime]) -> Dict[str, Any]:
    return {
        "inputs": inputs,
        "formula": formula,
        "data_source": data_source,
        "last_updated": (last_updated or datetime.utcnow()).isoformat(),
    }


def _money(currency: str, v: Optional[float]) -> str:
    if v is None:
        return "Insufficient data"
    return f"{currency}{v:,.0f}"


def _months(v: Optional[float]) -> str:
    if v is None:
        return "Insufficient data"
    return f"{v:.1f} mo"


def _pct(v: Optional[float]) -> str:
    if v is None:
        return "Insufficient data"
    return f"{v:+.1f}%"


# ---------------------------------------------------------------------------
# Individual metric calculators
# ---------------------------------------------------------------------------

def _gross_burn(ctx: StartupContext) -> MetricResult:
    inputs = {"fixed_costs": ctx.fixed_costs, "variable_costs": ctx.variable_costs, "monthly_burn_input": ctx.monthly_burn_input}
    if ctx.fixed_costs is not None or ctx.variable_costs is not None:
        value = (ctx.fixed_costs or 0) + (ctx.variable_costs or 0)
        return MetricResult("gross_burn", "Gross Burn", round(value, 2), "/mo", f"{_money(ctx.currency, value)}/mo", "actual",
            _calc_meta(inputs, "Gross Burn = Fixed Costs + Variable Costs", "Founder-entered fixed & variable costs", ctx.updated_at))
    if ctx.monthly_burn_input is not None:
        value = ctx.monthly_burn_input
        return MetricResult("gross_burn", "Gross Burn", round(value, 2), "/mo", f"{_money(ctx.currency, value)}/mo", "actual",
            _calc_meta(inputs, "Gross Burn = founder-reported total monthly burn (no fixed/variable breakdown given)", "Founder-entered total monthly burn", ctx.updated_at))
    return MetricResult("gross_burn", "Gross Burn", None, "/mo", "Insufficient data", "insufficient_data",
        _calc_meta(inputs, "Gross Burn = Fixed Costs + Variable Costs", "No expense data provided at onboarding", ctx.updated_at))


def _net_burn(ctx: StartupContext, gross: MetricResult) -> MetricResult:
    inputs = {"gross_burn": gross.value, "monthly_revenue": ctx.monthly_revenue, "is_pre_revenue": ctx.is_pre_revenue}
    if gross.status == "insufficient_data":
        return MetricResult("net_burn", "Net Burn", None, "/mo", "Insufficient data", "insufficient_data",
            _calc_meta(inputs, "Net Burn = Gross Burn − Monthly Revenue", "Depends on Gross Burn, which is unavailable", ctx.updated_at))
    if ctx.is_pre_revenue:
        return MetricResult("net_burn", "Net Burn", gross.value, "/mo", f"{_money(ctx.currency, gross.value)}/mo", gross.status,
            _calc_meta(inputs, "Net Burn = Gross Burn (pre-revenue, so Monthly Revenue = 0)", "Founder marked company as pre-revenue", ctx.updated_at))
    if ctx.monthly_revenue is None:
        return MetricResult("net_burn", "Net Burn", None, "/mo", "Insufficient data", "insufficient_data",
            _calc_meta(inputs, "Net Burn = Gross Burn − Monthly Revenue", "Monthly revenue not provided — can't distinguish Net from Gross Burn", ctx.updated_at))
    value = gross.value - ctx.monthly_revenue
    return MetricResult("net_burn", "Net Burn", round(value, 2), "/mo", f"{_money(ctx.currency, value)}/mo", gross.status,
        _calc_meta(inputs, "Net Burn = Gross Burn − Monthly Revenue", "Founder-entered expenses & revenue", ctx.updated_at))


def _revenue(ctx: StartupContext) -> MetricResult:
    inputs = {"monthly_revenue": ctx.monthly_revenue, "is_pre_revenue": ctx.is_pre_revenue}
    formula = "Monthly Revenue = founder-reported current monthly revenue (0 while pre-revenue)."
    if ctx.is_pre_revenue:
        return MetricResult("revenue", "Monthly Revenue", 0.0, "/mo", "Pre-revenue", "actual",
            _calc_meta(inputs, formula, "Founder marked the company as pre-revenue at onboarding", ctx.updated_at))
    if ctx.monthly_revenue is None:
        return MetricResult("revenue", "Monthly Revenue", None, "/mo", "Insufficient data", "insufficient_data",
            _calc_meta(inputs, formula, "No revenue figure was provided at onboarding", ctx.updated_at))
    return MetricResult("revenue", "Monthly Revenue", round(ctx.monthly_revenue, 2), "/mo", f"{_money(ctx.currency, ctx.monthly_revenue)}/mo", "actual",
        _calc_meta(inputs, formula, "Founder-entered current monthly revenue", ctx.updated_at))


def _cash_position(ctx: StartupContext) -> MetricResult:
    inputs = {"current_cash": ctx.current_cash}
    if ctx.current_cash is None:
        return MetricResult("cash_position", "Cash Position", None, "", "Insufficient data", "insufficient_data",
            _calc_meta(inputs, "Cash Position = founder-reported current cash balance", "No cash figure provided at onboarding", ctx.updated_at))
    return MetricResult("cash_position", "Cash Position", round(ctx.current_cash, 2), "", _money(ctx.currency, ctx.current_cash), "actual",
        _calc_meta(inputs, "Cash Position = founder-reported current cash balance", "Founder-entered current cash", ctx.updated_at))


def _runway(ctx: StartupContext, cash: MetricResult, net_burn: MetricResult) -> MetricResult:
    inputs = {"cash": cash.value, "net_burn": net_burn.value}
    if cash.status == "insufficient_data" or net_burn.status == "insufficient_data":
        return MetricResult("runway", "Runway", None, " mo", "Insufficient data", "insufficient_data",
            _calc_meta(inputs, "Runway = Available Cash ÷ Average Net Monthly Burn", "Depends on Cash Position and Net Burn, one of which is unavailable", ctx.updated_at))
    status = combine_status(cash.status, net_burn.status)
    if net_burn.value <= 0:
        return MetricResult("runway", "Runway", None, " mo", "Profitable — no cash-out horizon at current burn", status,
            _calc_meta(inputs, "Runway = Available Cash ÷ Average Net Monthly Burn (undefined when Net Burn ≤ 0 — company is cash-flow positive)", "Computed from Cash Position and Net Burn", ctx.updated_at))
    value = cash.value / net_burn.value
    return MetricResult("runway", "Runway", round(value, 1), " mo", _months(value), status,
        _calc_meta(inputs, "Runway = Available Cash ÷ Average Net Monthly Burn", "Computed from Cash Position and Net Burn", ctx.updated_at))


def _growth_pct(ctx: StartupContext, snapshots: List[StartupMetricSnapshot], field_name: str, metric_id: str,
                 label: str, manual_input: Optional[float], insufficient_note: str) -> MetricResult:
    inputs = {"snapshots_used": 0, "manual_estimate": manual_input}
    pts = [(s.snapshot_date, getattr(s, field_name)) for s in snapshots if getattr(s, field_name) is not None]
    pts.sort(key=lambda p: p[0])
    if len(pts) >= 2:
        prev_v, latest_v = pts[-2][1], pts[-1][1]
        inputs["snapshots_used"] = len(pts)
        inputs["previous_value"] = prev_v
        inputs["latest_value"] = latest_v
        if prev_v == 0:
            return MetricResult(metric_id, label, None, "%", "Insufficient data (previous value was zero)", "insufficient_data",
                _calc_meta(inputs, f"{label} = (Latest − Previous) ÷ Previous × 100, from stored daily snapshots", "Startup metric snapshot history", ctx.updated_at))
        value = (latest_v - prev_v) / prev_v * 100
        return MetricResult(metric_id, label, round(value, 1), "%", _pct(value), "actual",
            _calc_meta(inputs, f"{label} = (Latest − Previous) ÷ Previous × 100, from stored daily snapshots", "Startup metric snapshot history", ctx.updated_at))
    if manual_input is not None:
        return MetricResult(metric_id, label, round(manual_input, 1), "%", _pct(manual_input), "assumption",
            _calc_meta(inputs, f"{label} = founder-provided estimate (not enough snapshot history yet to compute an actual trend)", "Founder-entered estimate at onboarding", ctx.updated_at))
    return MetricResult(metric_id, label, None, "%", insufficient_note, "insufficient_data",
        _calc_meta(inputs, f"{label} = (Latest − Previous) ÷ Previous × 100, from stored daily snapshots", "Not enough history yet — needs at least 2 days of tracking, or a founder estimate", ctx.updated_at))


def _cash_projection(ctx: StartupContext, cash: MetricResult, gross: MetricResult, net_burn: MetricResult,
                      revenue_growth: MetricResult, months: int = 12) -> Dict[str, Any]:
    if cash.status == "insufficient_data" or gross.status == "insufficient_data" or net_burn.status == "insufficient_data":
        return {"status": "insufficient_data", "series": [], "cash_out_month": None,
                "calculation": _calc_meta({}, "Projected Cash[m] = Cash[m-1] − Net Burn[m]", "Depends on Cash Position / Gross Burn / Net Burn, one of which is unavailable", ctx.updated_at)}

    has_growth = revenue_growth.status in ("actual", "assumption") and revenue_growth.value is not None
    g = (revenue_growth.value / 100) if has_growth else 0.0
    revenue = ctx.monthly_revenue or 0.0
    gross_burn_flat = gross.value
    running_cash = cash.value
    series = []
    cash_out_month = None
    for m in range(1, months + 1):
        revenue = revenue * (1 + g) if has_growth else revenue
        net_burn_m = gross_burn_flat - revenue
        running_cash = running_cash - net_burn_m
        clipped = max(running_cash, 0.0)
        if cash_out_month is None and running_cash <= 0:
            cash_out_month = m
        series.append({"month": m, "projected_cash": round(clipped, 2), "projected_net_burn": round(net_burn_m, 2)})

    assumptions = ["Gross Burn is held flat across the projection window."]
    assumptions.append(
        f"Revenue is compounded monthly at the {'observed' if revenue_growth.status == 'actual' else 'founder-estimated'} growth rate of {revenue_growth.value:.1f}%/mo."
        if has_growth else "No revenue growth rate is available yet, so revenue is held flat across the projection window."
    )
    return {
        "status": "forecast", "series": series, "cash_out_month": cash_out_month, "assumptions": assumptions,
        "calculation": _calc_meta(
            {"starting_cash": cash.value, "gross_burn": gross.value, "revenue_growth_pct": revenue_growth.value if has_growth else None},
            "Projected Cash[m] = Cash[m-1] − (Gross Burn − Projected Revenue[m]); Revenue[m] = Revenue[m-1] × (1 + growth rate)",
            "Computed from current Cash Position, Gross Burn, and Revenue Growth", ctx.updated_at,
        ),
    }


def _funding_dependency(ctx: StartupContext, net_burn: MetricResult, runway: MetricResult, gross: MetricResult) -> MetricResult:
    inputs = {"net_burn": net_burn.value, "runway": runway.value, "monthly_revenue": ctx.monthly_revenue, "gross_burn": gross.value}
    formula = ("Self-sustaining if Net Burn ≤ 0. Otherwise: Low if Runway ≥ 12mo and Revenue covers ≥50% of Gross Burn; "
               "Medium if Runway ≥ 6mo; High if Runway ≥ 3mo; Critical if Runway < 3mo.")
    if net_burn.status == "insufficient_data":
        return MetricResult("funding_dependency", "Funding Dependency", None, "", "Insufficient data", "insufficient_data",
            _calc_meta(inputs, formula, "Depends on Net Burn, which is unavailable", ctx.updated_at))
    if net_burn.value <= 0:
        return MetricResult("funding_dependency", "Funding Dependency", None, "", "Self-sustaining", "actual",
            _calc_meta(inputs, formula, "Computed from Net Burn", ctx.updated_at))
    if runway.status == "insufficient_data":
        return MetricResult("funding_dependency", "Funding Dependency", None, "", "Insufficient data", "insufficient_data",
            _calc_meta(inputs, formula, "Depends on Runway, which is unavailable", ctx.updated_at))
    revenue_ratio = (ctx.monthly_revenue or 0) / gross.value if gross.value else 0
    r = runway.value
    if r >= 12 and revenue_ratio >= 0.5:
        label = "Low"
    elif r >= 6:
        label = "Medium"
    elif r >= 3:
        label = "High"
    else:
        label = "Critical"
    return MetricResult("funding_dependency", "Funding Dependency", None, "", label, "estimated",
        _calc_meta(inputs, formula, "Rule-based classification computed from Runway and Revenue/Gross Burn ratio", ctx.updated_at))


def _hiring_capacity(ctx: StartupContext, cash: MetricResult, net_burn: MetricResult) -> Dict[str, Any]:
    inputs = {"cash": cash.value, "net_burn": net_burn.value, "cost_per_hire": ctx.cost_per_hire, "runway_floor_months": RUNWAY_FLOOR_MONTHS}
    formula = f"Max sustainable hires = floor((Cash ÷ {RUNWAY_FLOOR_MONTHS:.0f} − Net Burn) ÷ Cost per Hire), floored at 0; Runway lost/hire compares Runway before vs. after adding one hire's cost to Net Burn."
    if cash.status == "insufficient_data" or net_burn.status == "insufficient_data" or ctx.cost_per_hire is None:
        missing = "Cost per Hire" if ctx.cost_per_hire is None else "Cash Position / Net Burn"
        return {"status": "insufficient_data", "max_sustainable_hires": None, "runway_lost_per_hire": None,
                "calculation": _calc_meta(inputs, formula, f"{missing} not available", ctx.updated_at)}

    base_burn = max(net_burn.value, 0.0)
    cur_runway = (cash.value / base_burn) if base_burn > 0 else None
    new_burn = base_burn + ctx.cost_per_hire
    new_runway = cash.value / new_burn if new_burn > 0 else None
    runway_lost = (cur_runway - new_runway) if (cur_runway is not None and new_runway is not None) else None

    max_hires = math.floor((cash.value / RUNWAY_FLOOR_MONTHS - base_burn) / ctx.cost_per_hire) if ctx.cost_per_hire > 0 else 0
    max_hires = max(max_hires, 0)
    return {
        "status": "estimated", "max_sustainable_hires": max_hires,
        "runway_lost_per_hire": round(runway_lost, 2) if runway_lost is not None else None,
        "calculation": _calc_meta(inputs, formula, "Computed from Cash Position, Net Burn, and Cost per Hire", ctx.updated_at),
    }


def _breakeven(ctx: StartupContext, gross: MetricResult, revenue_growth: MetricResult) -> MetricResult:
    inputs = {"monthly_revenue": ctx.monthly_revenue, "gross_burn": gross.value, "revenue_growth_pct": revenue_growth.value}
    formula = "Break-even month t solves Revenue × (1 + growth rate)^t = Gross Burn (assumes Gross Burn stays flat)."
    if gross.status == "insufficient_data":
        return MetricResult("breakeven", "Break-even Estimate", None, " mo", "Insufficient data", "insufficient_data",
            _calc_meta(inputs, formula, "Gross Burn is unavailable", ctx.updated_at))
    revenue = ctx.monthly_revenue or 0.0
    if revenue >= gross.value and gross.value > 0:
        return MetricResult("breakeven", "Break-even Estimate", 0, " mo", "Already at or above break-even", "actual",
            _calc_meta(inputs, formula, "Revenue already covers Gross Burn", ctx.updated_at))
    if revenue_growth.status in ("actual", "assumption") and revenue_growth.value and revenue_growth.value > 0 and revenue > 0:
        g = revenue_growth.value / 100
        t = math.log(gross.value / revenue) / math.log(1 + g)
        status = "forecast" if revenue_growth.status == "actual" else "estimated"
        return MetricResult("breakeven", "Break-even Estimate", round(t, 1), " mo", _months(t), status,
            _calc_meta(inputs, formula, f"Projected from current Revenue, Gross Burn, and a {revenue_growth.status} growth rate", ctx.updated_at))
    return MetricResult("breakeven", "Break-even Estimate", None, " mo", "Insufficient data — no revenue growth trend to project from", "insufficient_data",
        _calc_meta(inputs, formula, "No positive revenue growth rate is available (needs snapshot history or a founder estimate)", ctx.updated_at))


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------

def _date_after_months(months: float) -> str:
    days = max(0, int(round(months * 30.44)))
    return (date.today() + timedelta(days=days)).isoformat()


def compute_goals(ctx: StartupContext, metrics: Dict[str, MetricResult]) -> List[Dict[str, Any]]:
    out = []
    runway = metrics["runway"]
    gross = metrics["gross_burn"]
    revenue_growth = metrics.get("revenue_growth")
    breakeven = metrics.get("breakeven")
    for g in ctx.goals or []:
        gtype = g.get("type")
        label = g.get("label") or gtype
        target = g.get("target_value")
        unit = g.get("target_unit", "")
        progress = None
        current_value = None
        status = "insufficient_data"
        note = None
        expected_date = None
        projection_note = None

        if gtype == "extend_runway" and target:
            if runway.status == "insufficient_data":
                note = "Runway is unavailable — can't compute progress."
            elif runway.value is None:  # profitable / infinite runway
                progress, current_value, status = 100.0, None, "actual"
            else:
                current_value = runway.value
                progress = round(min(100.0, current_value / target * 100), 1)
                status = runway.status
            projection_note = "Runway doesn't extend on its own — it changes when you act on a decision (e.g. cut costs or raise funds). Try the Simulate tab."
        elif gtype == "revenue_milestone" and target:
            current_value = ctx.monthly_revenue or 0.0
            progress = round(min(100.0, current_value / target * 100), 1)
            status = "actual" if ctx.monthly_revenue is not None else "estimated"
            if current_value >= target:
                expected_date = date.today().isoformat()
            elif revenue_growth is not None and revenue_growth.status in ("actual", "assumption") and revenue_growth.value and revenue_growth.value > 0 and current_value > 0:
                months = math.log(target / current_value) / math.log(1 + revenue_growth.value / 100)
                expected_date = _date_after_months(months)
            else:
                projection_note = "No positive revenue growth trend yet to project a completion date from."
        elif gtype == "fundraise" and target:
            current_value = ctx.total_funding or 0.0
            progress = round(min(100.0, current_value / target * 100), 1)
            status = "actual"
            note = "Tracks lifetime funding raised against the target, not just the round in progress."
            projection_note = "Fundraising progress depends on discrete rounds closing, not a continuous trend — no projected date available."
        elif gtype == "profitability":
            if gross.status == "insufficient_data" or gross.value in (None, 0):
                note = "Gross Burn is unavailable — can't compute progress toward profitability."
            else:
                current_value = ctx.monthly_revenue or 0.0
                progress = round(min(100.0, current_value / gross.value * 100), 1)
                status = "actual" if ctx.monthly_revenue is not None else "estimated"
                note = "Progress = Revenue ÷ Gross Burn — how much of current spend is already covered by revenue."
                if breakeven is not None and breakeven.status in ("actual", "forecast", "estimated") and breakeven.value is not None:
                    expected_date = _date_after_months(breakeven.value)
                else:
                    projection_note = "No positive revenue growth trend yet to project a break-even date from."
        else:
            note = "Custom goal — no numeric target/current metric to compute automatic progress from."
            projection_note = "Custom goals aren't automatically projected."

        out.append({
            "type": gtype, "label": label, "target_value": target, "target_unit": unit,
            "target_date": g.get("target_date"), "current_value": current_value,
            "progress_pct": progress, "status": status, "note": note,
            "expected_completion_date": expected_date, "projection_note": projection_note,
        })
    return out


# ---------------------------------------------------------------------------
# Financial Health Score
# ---------------------------------------------------------------------------

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _health_score(ctx: StartupContext, metrics: Dict[str, Any]) -> MetricResult:
    runway = metrics["runway"]
    expense_growth = metrics["expense_growth"]
    revenue_growth = metrics["revenue_growth"]
    funding_dep = metrics["funding_dependency"]
    cash = metrics["cash_position"]

    components: List[Tuple[str, float, float]] = []  # (name, weight, score)
    excluded: List[str] = []

    if cash.status == "insufficient_data" and metrics["gross_burn"].status == "insufficient_data":
        return MetricResult("financial_health", "Financial Health Score", None, "", "Insufficient data", "insufficient_data",
            _calc_meta({}, "Weighted composite of Runway, Burn trend, Revenue growth, Funding dependency, and Debt sub-scores",
                       "Both Cash Position and Gross Burn are unavailable — can't responsibly score", ctx.updated_at))

    if runway.status != "insufficient_data":
        score = 100.0 if runway.value is None else _clamp(runway.value / 18 * 100, 0, 100)
        components.append(("runway", 0.35, score))
    else:
        excluded.append("runway")

    if expense_growth.status != "insufficient_data":
        g = expense_growth.value
        score = 100.0 if g <= 0 else _clamp(100 - g * 4, 0, 100)
        components.append(("burn_trend", 0.20, score))
    else:
        excluded.append("burn_trend")

    if revenue_growth.status != "insufficient_data":
        score = _clamp(50 + revenue_growth.value * 5, 0, 100)
        components.append(("revenue_growth", 0.20, score))
    else:
        excluded.append("revenue_growth")

    if funding_dep.status != "insufficient_data":
        fmap = {"Self-sustaining": 100, "Low": 100, "Medium": 65, "High": 35, "Critical": 10}
        score = fmap.get(funding_dep.display, 50)
        components.append(("funding_dependency", 0.15, score))
    else:
        excluded.append("funding_dependency")

    if ctx.business_loans_debt is not None and cash.status != "insufficient_data" and cash.value is not None:
        debt = ctx.business_loans_debt
        score = 100.0 if debt <= 0 else (0.0 if cash.value <= 0 else _clamp(100 * (1 - min(1.0, debt / cash.value)), 0, 100))
        components.append(("debt", 0.10, score))
    else:
        excluded.append("debt")

    if not components:
        return MetricResult("financial_health", "Financial Health Score", None, "", "Insufficient data", "insufficient_data",
            _calc_meta({}, "Weighted composite of Runway, Burn trend, Revenue growth, Funding dependency, and Debt sub-scores",
                       "None of the required sub-metrics are available yet", ctx.updated_at))

    total_weight = sum(w for _, w, _ in components)
    composite = sum(w * s for _, w, s in components) / total_weight
    note = f"Included: {', '.join(n for n, _, _ in components)}." + (f" Excluded (insufficient data): {', '.join(excluded)}." if excluded else "")
    return MetricResult("financial_health", "Financial Health Score", round(composite, 1), "/100", f"{composite:.0f}/100", "estimated",
        _calc_meta(
            {"components": {n: round(s, 1) for n, _, s in components}, "excluded": excluded},
            "Weighted composite: Runway 35% + Burn trend 20% + Revenue growth 20% + Funding dependency 15% + Debt 10% "
            "(weights renormalized over whichever sub-scores have data). " + note,
            "Computed from Runway, Expense Growth, Revenue Growth, Funding Dependency, and Debt", ctx.updated_at,
        ))


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def compute_metrics(ctx: StartupContext, snapshots: List[StartupMetricSnapshot]) -> Dict[str, Any]:
    """snapshots: this profile's StartupMetricSnapshot rows, most-recent-last not required (sorted internally)."""
    revenue = _revenue(ctx)
    gross = _gross_burn(ctx)
    net_burn = _net_burn(ctx, gross)
    cash = _cash_position(ctx)
    runway = _runway(ctx, cash, net_burn)
    revenue_growth = _growth_pct(ctx, snapshots, "revenue", "revenue_growth", "Revenue Growth", ctx.revenue_growth_pct_input,
                                  "Not applicable — pre-revenue" if ctx.is_pre_revenue else "Insufficient data")
    expense_growth = _growth_pct(ctx, snapshots, "gross_burn", "expense_growth", "Expense Growth", None, "Insufficient data")
    cash_projection = _cash_projection(ctx, cash, gross, net_burn, revenue_growth)
    funding_dependency = _funding_dependency(ctx, net_burn, runway, gross)
    hiring_capacity = _hiring_capacity(ctx, cash, net_burn)
    breakeven = _breakeven(ctx, gross, revenue_growth)

    metrics: Dict[str, Any] = {
        "cash_position": cash, "gross_burn": gross, "net_burn": net_burn, "runway": runway,
        "revenue": revenue, "revenue_growth": revenue_growth, "expense_growth": expense_growth,
        "funding_dependency": funding_dependency, "breakeven": breakeven,
    }
    health = _health_score(ctx, metrics)
    metrics["financial_health"] = health
    metrics["cash_projection"] = cash_projection
    metrics["hiring_capacity"] = hiring_capacity
    return metrics


# ---------------------------------------------------------------------------
# Alerts — deterministic, threshold-based, computed live (never persisted,
# so they're always consistent with the latest numbers).
# ---------------------------------------------------------------------------

def generate_alerts(ctx: StartupContext, metrics: Dict[str, Any], goals: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Deterministic, threshold-based. `severity` (critical/high/medium/low) is
    the visual ranking used by the Alerts UI; `level` (warn/info) is kept for
    backward compatibility with the plain alert-dot styling; `metric` names
    the affected metric id so the UI can link back to its card."""
    alerts: List[Dict[str, str]] = []
    runway = metrics["runway"]
    expense_growth = metrics["expense_growth"]
    revenue_growth = metrics["revenue_growth"]
    hiring = metrics["hiring_capacity"]

    if runway.status != "insufficient_data" and runway.value is not None:
        if runway.value < 3:
            alerts.append({"category": "runway", "level": "warn", "severity": "critical", "metric": "runway",
                            "text": f"Runway is critically low at {runway.value:.1f} months — under 3 months of cash left."})
        elif runway.value < 6:
            alerts.append({"category": "runway", "level": "warn", "severity": "high", "metric": "runway",
                            "text": f"Runway is {runway.value:.1f} months — under the commonly-used 6-month safety threshold."})

    if expense_growth.status == "actual" and expense_growth.value is not None and expense_growth.value > 10:
        severity = "high" if expense_growth.value > 20 else "medium"
        alerts.append({"category": "burn", "level": "warn", "severity": severity, "metric": "expense_growth",
                        "text": f"Monthly burn grew {expense_growth.value:.1f}% versus last tracked period — costs are accelerating."})

    if revenue_growth.status == "actual" and revenue_growth.value is not None and revenue_growth.value < 0:
        severity = "high" if revenue_growth.value < -20 else "medium"
        alerts.append({"category": "revenue", "level": "warn", "severity": severity, "metric": "revenue_growth",
                        "text": f"Revenue declined {abs(revenue_growth.value):.1f}% versus last tracked period."})
    elif ctx.is_pre_revenue:
        alerts.append({"category": "revenue", "level": "info", "severity": "low", "metric": "revenue",
                        "text": "Still pre-revenue — no revenue is being tracked yet."})

    if ctx.planned_hires and ctx.cost_per_hire and metrics["cash_position"].status != "insufficient_data" and metrics["net_burn"].status != "insufficient_data":
        cash_v = metrics["cash_position"].value
        planned_burn = max(metrics["net_burn"].value, 0) + ctx.planned_hires * ctx.cost_per_hire
        planned_runway = (cash_v / planned_burn) if planned_burn > 0 else None
        if planned_runway is not None and planned_runway < RUNWAY_FLOOR_MONTHS:
            severity = "critical" if planned_runway < 3 else "high"
            alerts.append({"category": "hiring", "level": "warn", "severity": severity, "metric": "hiring_capacity",
                            "text": f"Your planned hiring ({ctx.planned_hires} hire(s)) would cut runway to {planned_runway:.1f} months — below the {RUNWAY_FLOOR_MONTHS:.0f}-month safety threshold."})
    elif hiring["status"] == "estimated" and hiring["max_sustainable_hires"] == 0:
        alerts.append({"category": "hiring", "level": "warn", "severity": "medium", "metric": "hiring_capacity",
                        "text": "At current cash and burn, no additional hires are sustainable while keeping a 6-month runway buffer."})

    if runway.status != "insufficient_data" and runway.value is not None and runway.value < 6 and not ctx.currently_fundraising:
        has_fundraise_goal = any(g.get("type") == "fundraise" for g in goals)
        if has_fundraise_goal or runway.value < 4:
            severity = "high" if runway.value < 4 else "medium"
            alerts.append({"category": "goal", "level": "warn", "severity": severity, "metric": "runway",
                            "text": "Runway is under 6 months and you're not currently fundraising — consider starting the process soon."})

    for g in goals:
        if g.get("progress_pct") is not None and g["progress_pct"] < 25 and g.get("type") != "fundraise":
            alerts.append({"category": "goal", "level": "info", "severity": "low", "metric": "goals",
                            "text": f"Goal “{g['label']}” is only {g['progress_pct']:.0f}% complete."})

    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    alerts.sort(key=lambda a: severity_rank.get(a["severity"], 4))
    return alerts[:8]


# ---------------------------------------------------------------------------
# Health indicators — a purely-derived, at-a-glance status per Overview
# domain (Runway / Cash Flow / Revenue / Expenses / Goals). These do NOT
# change or replace the weighted Financial Health Score composite above —
# they're an additional deterministic presentation layer over the same
# already-computed metrics.
# ---------------------------------------------------------------------------

def _status_from_bands(value: Optional[float], good_if: str, warn_at: float, critical_at: float) -> str:
    """good_if='low' -> lower value is better (e.g. burn growth); good_if='high' -> higher is better."""
    if value is None:
        return "insufficient_data"
    if good_if == "low":
        if value >= critical_at:
            return "critical"
        if value >= warn_at:
            return "warning"
        return "good"
    if value <= critical_at:
        return "critical"
    if value <= warn_at:
        return "warning"
    return "good"


def build_health_indicators(ctx: StartupContext, metrics: Dict[str, Any], goals: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    runway = metrics["runway"]
    expense_growth = metrics["expense_growth"]
    revenue_growth = metrics["revenue_growth"]
    funding_dependency = metrics["funding_dependency"]

    indicators = []

    if runway.status == "insufficient_data":
        indicators.append({"id": "runway", "label": "Runway", "status": "insufficient_data", "display": "Insufficient data", "detail": "No cash or burn figure on file yet."})
    elif runway.value is None:
        indicators.append({"id": "runway", "label": "Runway", "status": "good", "display": "Profitable", "detail": "Net burn is at or below zero — no cash-out horizon."})
    else:
        status = _status_from_bands(runway.value, "high", warn_at=6, critical_at=3)
        indicators.append({"id": "runway", "label": "Runway", "status": status, "display": f"{runway.value:.1f} mo", "detail": f"{runway.value:.1f} months of cash left at the current burn rate."})

    if funding_dependency.status == "insufficient_data":
        indicators.append({"id": "cash_flow", "label": "Cash Flow", "status": "insufficient_data", "display": "Insufficient data", "detail": "Not enough data to classify funding dependency."})
    else:
        fmap = {"Self-sustaining": "good", "Low": "good", "Medium": "warning", "High": "serious", "Critical": "critical"}
        indicators.append({"id": "cash_flow", "label": "Cash Flow", "status": fmap.get(funding_dependency.display, "warning"),
                            "display": funding_dependency.display, "detail": f"Funding dependency classification: {funding_dependency.display}."})

    if ctx.is_pre_revenue:
        indicators.append({"id": "revenue", "label": "Revenue", "status": "warning", "display": "Pre-revenue", "detail": "No revenue is being tracked yet."})
    elif revenue_growth.status not in ("actual", "assumption") or revenue_growth.value is None:
        indicators.append({"id": "revenue", "label": "Revenue", "status": "insufficient_data", "display": "Insufficient data", "detail": "Not enough history to assess a revenue trend."})
    else:
        status = _status_from_bands(revenue_growth.value, "high", warn_at=0, critical_at=-10)
        indicators.append({"id": "revenue", "label": "Revenue", "status": status, "display": f"{revenue_growth.value:+.1f}%/mo",
                            "detail": f"Revenue is trending {'up' if revenue_growth.value > 0 else ('flat' if revenue_growth.value == 0 else 'down')} {abs(revenue_growth.value):.1f}%/mo."})

    if expense_growth.status != "actual" or expense_growth.value is None:
        indicators.append({"id": "expenses", "label": "Expenses", "status": "insufficient_data", "display": "Insufficient data", "detail": "Not enough history to assess an expense trend yet."})
    else:
        status = _status_from_bands(expense_growth.value, "low", warn_at=10, critical_at=20)
        indicators.append({"id": "expenses", "label": "Expenses", "status": status, "display": f"{expense_growth.value:+.1f}%/mo",
                            "detail": f"Monthly expenses are changing {expense_growth.value:+.1f}%/mo."})

    if not goals:
        indicators.append({"id": "goals", "label": "Goals", "status": "insufficient_data", "display": "No goals set", "detail": "No goals were set at onboarding."})
    else:
        scored = [g["progress_pct"] for g in goals if g.get("progress_pct") is not None]
        if not scored:
            indicators.append({"id": "goals", "label": "Goals", "status": "insufficient_data", "display": "Not quantifiable", "detail": "None of your current goals have a computable numeric progress."})
        else:
            avg = sum(scored) / len(scored)
            status = _status_from_bands(avg, "high", warn_at=40, critical_at=20)
            indicators.append({"id": "goals", "label": "Goals", "status": status, "display": f"{avg:.0f}% avg progress",
                                "detail": f"Average progress across {len(scored)} quantifiable goal(s) is {avg:.0f}%."})

    return indicators


# ---------------------------------------------------------------------------
# Expense / revenue breakdowns — sourced from the Hisaab ledger when
# transactions exist (Actual, categorized by the founder); falls back to the
# onboarded Fixed/Variable cost split when there's no ledger history yet.
# Never fabricates a category split that wasn't actually entered.
# ---------------------------------------------------------------------------

def build_expense_breakdown(ctx: StartupContext, out_transactions: List[Any]) -> Dict[str, Any]:
    if out_transactions:
        buckets: Dict[str, float] = {}
        for t in out_transactions:
            buckets[t.category or "Uncategorized"] = buckets.get(t.category or "Uncategorized", 0) + t.amount
        items = [{"category": k, "amount": round(v, 2)} for k, v in sorted(buckets.items(), key=lambda kv: -kv[1])]
        return {"status": "actual", "items": items, "data_source": "Categorized Hisaab money-out transactions", "total": round(sum(buckets.values()), 2)}

    items = []
    if ctx.fixed_costs is not None:
        items.append({"category": "Fixed costs", "amount": round(ctx.fixed_costs, 2)})
    if ctx.variable_costs is not None:
        items.append({"category": "Variable costs", "amount": round(ctx.variable_costs, 2)})
    if items:
        return {"status": "actual", "items": items, "data_source": "Founder-entered Fixed/Variable cost split at onboarding (no Hisaab transactions logged yet)", "total": round(sum(i["amount"] for i in items), 2)}
    return {"status": "insufficient_data", "items": [], "data_source": "No expense data available", "total": None}


def build_revenue_breakdown(ctx: StartupContext, in_transactions: List[Any]) -> Dict[str, Any]:
    if in_transactions:
        buckets: Dict[str, float] = {}
        for t in in_transactions:
            buckets[t.category or "Uncategorized"] = buckets.get(t.category or "Uncategorized", 0) + t.amount
        items = [{"category": k, "amount": round(v, 2)} for k, v in sorted(buckets.items(), key=lambda kv: -kv[1])]
        return {"status": "actual", "items": items, "streams": ctx.revenue_streams,
                "data_source": "Categorized Hisaab money-in transactions", "total": round(sum(buckets.values()), 2)}
    return {"status": "insufficient_data", "items": [], "streams": ctx.revenue_streams,
            "data_source": "No Hisaab money-in transactions logged yet", "total": None}


def metric_history(snapshots: List[StartupMetricSnapshot], limit: int = 30) -> List[Dict[str, Any]]:
    ordered = sorted(snapshots, key=lambda s: s.snapshot_date)[-limit:]
    return [{
        "date": s.snapshot_date.isoformat(), "cash": s.cash, "gross_burn": s.gross_burn, "net_burn": s.net_burn,
        "revenue": s.revenue, "runway_months": s.runway_months, "financial_health_score": s.financial_health_score,
    } for s in ordered]


# ---------------------------------------------------------------------------
# Snapshot capture — idempotent, at most one row per profile per day.
# ---------------------------------------------------------------------------

def capture_snapshot_if_needed(db: Session, profile_id: int, ctx: StartupContext, metrics: Dict[str, Any]) -> Optional[StartupMetricSnapshot]:
    today = date.today()
    existing = db.query(StartupMetricSnapshot).filter(
        StartupMetricSnapshot.profile_id == profile_id, StartupMetricSnapshot.snapshot_date == today
    ).first()
    if existing:
        return existing

    snap = StartupMetricSnapshot(
        profile_id=profile_id, snapshot_date=today,
        cash=metrics["cash_position"].value, gross_burn=metrics["gross_burn"].value,
        net_burn=metrics["net_burn"].value, revenue=ctx.monthly_revenue,
        runway_months=metrics["runway"].value, financial_health_score=metrics["financial_health"].value,
        raw={k: (v.to_dict() if isinstance(v, MetricResult) else v) for k, v in metrics.items()},
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def build_daily_brief(ctx: StartupContext, metrics: Dict[str, Any], snapshots: List[StartupMetricSnapshot]) -> Dict[str, Any]:
    today = date.today()
    prior = [s for s in snapshots if s.snapshot_date < today]
    prior.sort(key=lambda s: s.snapshot_date)
    if not prior:
        return {"status": "insufficient_data", "as_of": today.isoformat(), "bullets":
                ["First day of tracking — today's snapshot is now your baseline. Day-over-day comparisons will appear from tomorrow."]}

    prev = prior[-1]
    bullets = []

    def delta_bullet(label, cur, prev_v, currency=False, months=False):
        if cur is None or prev_v is None:
            return f"{label}: {'Insufficient data'}"
        d = cur - prev_v
        arrow = "↑" if d > 0 else ("↓" if d < 0 else "→")
        cur_s = _money(ctx.currency, cur) if currency else (f"{cur:.1f} mo" if months else f"{cur:.1f}")
        d_s = (_money(ctx.currency, abs(d)) if currency else (f"{abs(d):.1f} mo" if months else f"{abs(d):.1f}"))
        return f"{label}: {cur_s} ({arrow} {d_s} vs. yesterday)"

    bullets.append(delta_bullet("Cash", metrics["cash_position"].value, prev.cash, currency=True))
    bullets.append(delta_bullet("Net Burn", metrics["net_burn"].value, prev.net_burn, currency=True))
    bullets.append(delta_bullet("Runway", metrics["runway"].value, prev.runway_months, months=True))
    if metrics["financial_health"].value is not None:
        bullets.append(delta_bullet("Financial Health", metrics["financial_health"].value, prev.financial_health_score))

    return {"status": "actual", "as_of": today.isoformat(), "compared_to": prev.snapshot_date.isoformat(), "bullets": bullets}


def build_weekly_report(ctx: StartupContext, metrics: Dict[str, Any], snapshots: List[StartupMetricSnapshot]) -> Dict[str, Any]:
    today = date.today()
    window_start = today - timedelta(days=6)
    window = sorted([s for s in snapshots if s.snapshot_date >= window_start], key=lambda s: s.snapshot_date)
    days_present = len(window)

    if days_present == 0:
        return {"status": "insufficient_data", "window_days": 7, "days_present": 0,
                "note": "No tracking history yet for this week — check back after a few days of usage.", "points": []}

    points = [{
        "date": s.snapshot_date.isoformat(), "cash": s.cash, "net_burn": s.net_burn,
        "runway_months": s.runway_months, "financial_health_score": s.financial_health_score,
    } for s in window]

    result: Dict[str, Any] = {
        "status": "actual" if days_present >= 2 else "insufficient_data",
        "window_days": 7, "days_present": days_present, "points": points,
    }
    if days_present < 7:
        result["note"] = f"Only {days_present} of the last 7 days have tracked data — trend is based on what's available so far."
    if days_present >= 2:
        first, last = window[0], window[-1]
        result["health_delta"] = (round(last.financial_health_score - first.financial_health_score, 1)
                                   if (last.financial_health_score is not None and first.financial_health_score is not None) else None)
        result["cash_delta"] = round(last.cash - first.cash, 2) if (last.cash is not None and first.cash is not None) else None
        result["runway_delta"] = (round(last.runway_months - first.runway_months, 1)
                                   if (last.runway_months is not None and first.runway_months is not None) else None)
    return result
