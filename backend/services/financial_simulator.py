"""
Shared financial grounding + deterministic scenario math for the twin.

This is the "RAG" layer both Ask Twin and Simulation retrieve from: a single
`build_financial_context()` normalizes whatever shape the user's profile is
in (income/expenses/savings for an individual, revenue/burn/runway for a
startup, treasury/cashflow for an enterprise, custom onboarded metrics...)
into one consistent structure. Simulation additionally runs deterministic
math on top of it — amounts, growth, affordability, timelines — so the LLM
is only ever asked to phrase a recommendation around numbers that were
already computed here, never to invent them.
"""
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# 1. Financial context extraction (the shared grounding step)
# ---------------------------------------------------------------------------

INCOME_KEYS = {"income", "revenue", "m_income", "salary"}
EXPENSE_KEYS = {"expenses", "burn", "m_expenses"}
SAVINGS_KEYS = {"savings", "treasury", "m_savings", "balance"}
LOAN_KEYS = {"loans", "m_loans", "debt"}


@dataclass
class FinancialContext:
    currency: str
    income: float
    expenses: float
    savings: float
    loans: float
    surplus: float
    buffer_months: Optional[float]
    goal_title: Optional[str]
    goal_target: Optional[float]
    goal_progress_pct: Optional[float]
    monthly_savings_rate: Optional[float]


def _find_metric(metrics: List[Dict[str, Any]], ids: set, label_keywords: List[str]) -> Optional[Dict[str, Any]]:
    for m in metrics or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("id") or "").lower()
        label = str(m.get("label") or "").lower()
        if mid in ids or any(k in label for k in label_keywords):
            return m
    return None


def build_financial_context(profile: Any) -> FinancialContext:
    """The single grounding step: turns a Profile row (whatever shape its
    metrics happen to be in) into normalized numbers every downstream
    consumer (Ask Twin, Simulation) can rely on."""
    metrics = profile.metrics or []

    income_m = _find_metric(metrics, INCOME_KEYS, ["income", "revenue", "salary"])
    expense_m = _find_metric(metrics, EXPENSE_KEYS, ["expense", "burn"])
    savings_m = _find_metric(metrics, SAVINGS_KEYS, ["saving", "treasury", "balance"])
    loan_m = _find_metric(metrics, LOAN_KEYS, ["loan", "debt"])

    def val(m):
        try:
            return float(m["value"]) if m and m.get("value") is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    income = val(income_m)
    expenses = val(expense_m)
    savings = val(savings_m)
    loans = val(loan_m)
    surplus = income - expenses
    buffer_months = (savings / expenses) if expenses > 0 else None

    monthly_savings_rate = None
    trend = (savings_m or {}).get("trend") if savings_m else None
    if trend and len(trend) >= 2:
        try:
            delta = float(trend[-1]) - float(trend[-2])
            if delta > 0:
                monthly_savings_rate = delta
        except (TypeError, ValueError):
            pass
    if monthly_savings_rate is None and surplus > 0:
        monthly_savings_rate = surplus

    goal = profile.goal or {}

    return FinancialContext(
        currency=profile.currency or "₹",
        income=income,
        expenses=expenses,
        savings=savings,
        loans=loans,
        surplus=surplus,
        buffer_months=buffer_months,
        goal_title=goal.get("title"),
        goal_target=goal.get("target"),
        goal_progress_pct=goal.get("progress"),
        monthly_savings_rate=monthly_savings_rate,
    )


def ctx_to_dict(ctx: FinancialContext) -> Dict[str, Any]:
    return asdict(ctx)


# ---------------------------------------------------------------------------
# 2. Natural-language scenario parsing (rule-based — numbers must come from
#    the text deterministically, never from an LLM guess)
# ---------------------------------------------------------------------------

_MONEY_UNITS = {"k": 1_000, "thousand": 1_000, "lakh": 100_000, "lac": 100_000, "l": 100_000, "crore": 10_000_000, "cr": 10_000_000}
_TIME_UNIT_PREFIXES = ("year", "yr", "month", "mo", "week", "wk")

_TOKEN_RE = re.compile(
    r'(?:₹|rs\.?|inr)?\s*([\d][\d,]*(?:\.\d+)?)\s*'
    r'(k|thousand|lakh|lac|l|crore|cr|years?|yrs?|months?|mo|weeks?|wk)?\b',
    re.IGNORECASE,
)


def extract_tokens(text: str) -> Tuple[List[float], Optional[float]]:
    """Pull monetary amounts and a duration (in months) out of free text."""
    amounts: List[float] = []
    months: Optional[float] = None
    for m in _TOKEN_RE.finditer(text):
        num_str, unit = m.group(1), (m.group(2) or "").lower()
        if not num_str:
            continue
        try:
            val = float(num_str.replace(",", ""))
        except ValueError:
            continue
        if unit in _MONEY_UNITS:
            amounts.append(val * _MONEY_UNITS[unit])
        elif unit.startswith(_TIME_UNIT_PREFIXES):
            if unit.startswith(("year", "yr")):
                months = val * 12
            elif unit.startswith(("week", "wk")):
                months = val / 4.345
            else:
                months = val
        elif val >= 100:
            # A bare number with no unit — only trust it as an amount if
            # it's large enough to plausibly be money, not a stray digit.
            amounts.append(val)
    return amounts, (round(months, 1) if months is not None else None)


_SCENARIO_MARKERS = re.compile(
    r"\b(what if|what happens if|what would happen if|suppose|imagine if|if i |"
    r"can i afford|how quickly can i|how soon can i|how long (would|will) it take)\b",
    re.IGNORECASE,
)
_INFORMATIONAL_MARKERS = re.compile(
    r"\b(what is my|what'?s my|whats my|how is my|how'?s my|how are my|"
    r"am i on track|what'?s the status of my|how much (do|have) i)\b",
    re.IGNORECASE,
)


def classify_intent(text: str) -> str:
    """Route between two fundamentally different jobs:

    - 'informational': a question about the user's CURRENT state ("what is
      my runway?") — answer directly from the same Ask Twin/RAG flow, no
      hypothetical to calculate.
    - 'scenario': a hypothetical change ("what if I invest ₹20k/month?") —
      run the full Understand -> Watch -> Simulate -> Recommend -> Teach ->
      Check pipeline with real calculations and a timeline.
    """
    t = text.strip()
    if _SCENARIO_MARKERS.search(t):
        return "scenario"
    if _INFORMATIONAL_MARKERS.search(t):
        return "informational"

    # Fallback for phrasing that doesn't hit either marker set: a concrete
    # hypothetical scenario type (with an amount/duration behind it) is a
    # scenario; anything else defaults to informational rather than forcing
    # a user into providing numbers for what was really just a question.
    scenario_type = classify_scenario(t)
    if scenario_type in ("invest_monthly", "emi_affordability", "increase_savings", "income_loss"):
        return "scenario"
    amounts, months = extract_tokens(t)
    if amounts or months:
        return "scenario"
    return "informational"


def classify_scenario(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["no income", "lose my job", "lost my job", "without income", "stop earning", "unemployed", "income for"]):
        return "income_loss"
    if any(k in t for k in ["emi", "afford", "loan payment", "mortgage"]):
        return "emi_affordability"
    if any(k in t for k in ["invest", "sip", "mutual fund", "index fund", "stock market"]):
        return "invest_monthly"
    if any(k in t for k in ["increase my savings", "increase savings", "save extra", "save more", "boost my savings", "increase my monthly savings"]):
        return "increase_savings"
    if any(k in t for k in ["reach my goal", "savings goal", "my goal", "how quickly", "how soon", "how long"]):
        return "goal_timeline"
    return "generic"


def format_months(months: float) -> str:
    months = round(months)
    if months <= 0:
        return "0 months"
    if months % 12 == 0 and months >= 12:
        yrs = months // 12
        return f"{yrs} year" + ("s" if yrs != 1 else "")
    return f"{months} month" + ("s" if months != 1 else "")


def parse_scenario(text: str) -> Tuple[str, Dict[str, Any]]:
    scenario_type = classify_scenario(text)
    amounts, months = extract_tokens(text)
    params: Dict[str, Any] = {
        "amount": amounts[0] if amounts else None,
        "duration_months": months,
        "all_amounts_detected": amounts,
    }
    if scenario_type == "invest_monthly" and params["duration_months"] is None:
        params["duration_months"] = 36
        params["duration_assumed"] = True
    if scenario_type == "income_loss" and params["duration_months"] is None:
        params["duration_months"] = 6
        params["duration_assumed"] = True
    return scenario_type, params


def describe_understanding(scenario_type: str, params: Dict[str, Any], currency: str) -> str:
    label = scenario_type.replace("_", " ")
    parts = []
    if params.get("amount") is not None:
        parts.append(f"amount ≈ {currency}{params['amount']:,.0f}")
    if params.get("duration_months") is not None:
        suffix = " (assumed)" if params.get("duration_assumed") else ""
        parts.append(f"duration ≈ {format_months(params['duration_months'])}{suffix}")
    detail = ("Detected " + ", ".join(parts) + ".") if parts else \
        "No specific amount or duration detected in the text — falling back to your current profile trends for a qualitative read."
    return f"Classified as a ‘{label}’ scenario. {detail}"


# ---------------------------------------------------------------------------
# 3. Deterministic calculators — one per scenario type
# ---------------------------------------------------------------------------

ASSUMED_ANNUAL_RETURN = 0.10
MILESTONE_CANDIDATES = [3, 6, 12, 24, 36]


def pick_milestones(total_months: float) -> List[int]:
    total_months = max(1, round(total_months))
    milestones = sorted(set([m for m in MILESTONE_CANDIDATES if m <= total_months] + [total_months]))
    return milestones


def sip_future_value(monthly_amount: float, months: int, annual_rate: float = ASSUMED_ANNUAL_RETURN) -> float:
    r = annual_rate / 12
    if monthly_amount <= 0 or months <= 0:
        return 0.0
    if r == 0:
        return monthly_amount * months
    return monthly_amount * (((1 + r) ** months - 1) / r) * (1 + r)


def calc_invest_monthly(ctx: FinancialContext, amount: float, months: float):
    amount = amount or 0
    months_i = round(months or 36)
    new_surplus = ctx.surplus - amount

    timeline = []
    running_savings = ctx.savings
    prev = 0
    for m in pick_milestones(months_i):
        running_savings += new_surplus * (m - prev)
        prev = m
        buffer = (running_savings / ctx.expenses) if ctx.expenses > 0 else None
        fv = sip_future_value(amount, m)
        invested = amount * m
        timeline.append({
            "label": format_months(m), "months": m,
            "invested_total": round(invested, 2),
            "projected_value": round(fv, 2),
            "estimated_gain": round(fv - invested, 2),
            "emergency_buffer_months": round(buffer, 1) if buffer is not None else None,
        })

    goal_progress_after_pct = None
    if ctx.goal_target:
        saved_so_far = ctx.goal_target * ((ctx.goal_progress_pct or 0) / 100)
        saved_after = min(saved_so_far + max(new_surplus, 0) * months_i, ctx.goal_target)
        goal_progress_after_pct = round((saved_after / ctx.goal_target) * 100, 1)

    impact = {
        "monthly_surplus_before": round(ctx.surplus, 2),
        "monthly_surplus_after": round(new_surplus, 2),
        "savings_impact": f"Liquid savings are untouched — {ctx.currency}{amount:,.0f}/month is redirected into a new investment instead.",
        "emergency_buffer_before_months": round(ctx.buffer_months, 1) if ctx.buffer_months is not None else None,
        "emergency_buffer_after_months": timeline[-1]["emergency_buffer_months"] if timeline else None,
        "goal_progress_before_pct": ctx.goal_progress_pct,
        "goal_progress_after_pct": goal_progress_after_pct,
        "investment_contribution": round(amount, 2),
    }
    assumptions = [
        f"Assumes an average annual return of {ASSUMED_ANNUAL_RETURN*100:.0f}% (typical for a diversified equity/index fund), compounded monthly.",
        "Assumes the monthly contribution stays constant for the full period, and doesn't factor in taxes or fund fees.",
    ]
    risks = []
    if new_surplus < 0:
        risks.append(f"This commitment is larger than your current monthly surplus of {ctx.currency}{ctx.surplus:,.0f} — you'd be investing more than you currently have left over each month.")
    elif ctx.buffer_months is not None and ctx.buffer_months < 3:
        risks.append(f"Your emergency buffer is already thin ({ctx.buffer_months:.1f} months) — consider building that up before committing new money to investments.")
    return impact, timeline, assumptions, risks


def calc_emi_affordability(ctx: FinancialContext, emi_amount: float):
    emi_amount = emi_amount or 0
    new_surplus = ctx.surplus - emi_amount
    foir = (emi_amount / ctx.income) if ctx.income > 0 else None

    timeline = []
    running_savings = ctx.savings
    prev = 0
    for m in pick_milestones(36):
        running_savings += new_surplus * (m - prev)
        prev = m
        buffer = (running_savings / ctx.expenses) if ctx.expenses > 0 else None
        timeline.append({
            "label": format_months(m), "months": m,
            "projected_savings": round(running_savings, 2),
            "emergency_buffer_months": round(buffer, 1) if buffer is not None else None,
        })

    goal_progress_after_pct = None
    if ctx.goal_target:
        saved_so_far = ctx.goal_target * ((ctx.goal_progress_pct or 0) / 100)
        saved_after = min(saved_so_far + max(new_surplus, 0) * 36, ctx.goal_target)
        goal_progress_after_pct = round((saved_after / ctx.goal_target) * 100, 1)

    if new_surplus < 0:
        verdict = "not recommended"
    elif foir is not None and foir > 0.4:
        verdict = "tight"
    else:
        verdict = "affordable"

    impact = {
        "monthly_surplus_before": round(ctx.surplus, 2),
        "monthly_surplus_after": round(new_surplus, 2),
        "savings_impact": f"Monthly savings capacity changes by {ctx.currency}{emi_amount:,.0f} once this EMI starts.",
        "emergency_buffer_before_months": round(ctx.buffer_months, 1) if ctx.buffer_months is not None else None,
        "emergency_buffer_after_months": timeline[-1]["emergency_buffer_months"] if timeline else None,
        "goal_progress_before_pct": ctx.goal_progress_pct,
        "goal_progress_after_pct": goal_progress_after_pct,
        "foir_pct": round(foir * 100, 1) if foir is not None else None,
        "affordability_verdict": verdict,
    }
    assumptions = [
        "Uses the standard lending guideline that fixed obligations should stay under ~40% of gross monthly income (FOIR).",
        "Assumes income and expenses stay constant over the projection window.",
    ]
    risks = []
    if new_surplus < 0:
        risks.append(f"This EMI is larger than your current monthly surplus of {ctx.currency}{ctx.surplus:,.0f} — you'd run a monthly deficit.")
    if foir is not None and foir > 0.4:
        risks.append(f"This EMI alone is {foir*100:.0f}% of your income, above the commonly recommended 40% fixed-obligation ceiling.")
    return impact, timeline, assumptions, risks


def calc_increase_savings(ctx: FinancialContext, amount: float):
    amount = amount or 0
    rate_before = ctx.monthly_savings_rate or max(ctx.surplus, 0)
    rate_after = rate_before + amount

    goal_remaining = None
    if ctx.goal_target and ctx.goal_progress_pct is not None:
        goal_remaining = ctx.goal_target * (1 - ctx.goal_progress_pct / 100)

    timeline = []
    savings_before = ctx.savings
    savings_after = ctx.savings
    prev = 0
    for m in pick_milestones(36):
        span = m - prev
        savings_before += rate_before * span
        savings_after += rate_after * span
        prev = m
        entry = {
            "label": format_months(m), "months": m,
            "savings_before": round(savings_before, 2),
            "savings_after": round(savings_after, 2),
            "extra_saved": round(savings_after - savings_before, 2),
        }
        timeline.append(entry)

    months_to_goal_before = (goal_remaining / rate_before) if goal_remaining and rate_before > 0 else None
    months_to_goal_after = (goal_remaining / rate_after) if goal_remaining and rate_after > 0 else None

    impact = {
        "monthly_surplus_before": round(ctx.surplus, 2),
        "monthly_surplus_after": round(ctx.surplus - amount, 2),
        "savings_impact": f"Monthly savings rate rises from {ctx.currency}{rate_before:,.0f} to {ctx.currency}{rate_after:,.0f}.",
        "emergency_buffer_before_months": round(ctx.buffer_months, 1) if ctx.buffer_months is not None else None,
        "emergency_buffer_after_months": round(ctx.buffer_months, 1) if ctx.buffer_months is not None else None,
        "goal_progress_before_pct": ctx.goal_progress_pct,
        "goal_months_remaining_before": round(months_to_goal_before, 1) if months_to_goal_before else None,
        "goal_months_remaining_after": round(months_to_goal_after, 1) if months_to_goal_after else None,
        "investment_contribution": round(amount, 2),
    }
    assumptions = [
        f"Assumes the extra {ctx.currency}{amount:,.0f}/month comes from reducing discretionary spending rather than new income.",
        "Goal timeline assumes your current savings trend continues at a constant monthly rate.",
    ]
    risks = []
    if amount > ctx.surplus:
        risks.append(f"This commitment is larger than your current monthly surplus of {ctx.currency}{ctx.surplus:,.0f} — you'd be committing more extra savings than you currently have left over each month.")
    if ctx.expenses and amount > ctx.expenses * 0.5:
        risks.append("This is a large cut relative to your current monthly expenses — double check it's realistic before committing.")
    return impact, timeline, assumptions, risks


def calc_goal_timeline(ctx: FinancialContext):
    if not ctx.goal_target:
        impact = {
            "goal_title": ctx.goal_title,
            "monthly_contribution_rate": round(ctx.monthly_savings_rate, 2) if ctx.monthly_savings_rate else None,
            "note": "No savings goal with a target amount was found on your profile.",
        }
        return impact, [], ["No savings goal is set on your profile, so a precise timeline can't be computed."], \
            ["Add a goal with a target amount to your profile to get a precise timeline."]

    saved_so_far = ctx.goal_target * ((ctx.goal_progress_pct or 0) / 100)
    remaining = max(ctx.goal_target - saved_so_far, 0)
    rate = ctx.monthly_savings_rate or 0
    months_to_goal = (remaining / rate) if rate > 0 else None
    horizon = min(months_to_goal, 60) if months_to_goal else 36

    timeline = []
    for m in pick_milestones(horizon):
        saved = min(saved_so_far + rate * m, ctx.goal_target)
        pct = (saved / ctx.goal_target) * 100
        timeline.append({
            "label": format_months(m), "months": m,
            "goal_progress_pct": round(pct, 1),
            "amount_saved": round(saved, 2),
        })

    impact = {
        "goal_title": ctx.goal_title,
        "goal_target": ctx.goal_target,
        "goal_progress_before_pct": ctx.goal_progress_pct,
        "monthly_contribution_rate": round(rate, 2),
        "months_to_goal": round(months_to_goal, 1) if months_to_goal else None,
    }
    assumptions = ["Assumes your savings continue growing at the recently observed monthly rate."]
    risks = []
    if rate <= 0:
        risks.append("Your current surplus/savings rate is zero or negative — the goal won't progress without a change in income, expenses, or contributions.")
    return impact, timeline, assumptions, risks


def calc_income_loss(ctx: FinancialContext, months: float):
    months_i = round(months or 6)
    timeline = []
    for m in pick_milestones(months_i):
        remaining = ctx.savings - ctx.expenses * m
        buffer = (max(remaining, 0) / ctx.expenses) if ctx.expenses > 0 else None
        timeline.append({
            "label": format_months(m), "months": m,
            "remaining_savings": round(max(remaining, 0), 2),
            "shortfall": round(max(-remaining, 0), 2),
            "emergency_buffer_months": round(buffer, 1) if buffer is not None else None,
        })

    coverage = ctx.buffer_months
    impact = {
        "monthly_surplus_before": round(ctx.surplus, 2),
        "monthly_surplus_after": round(-ctx.expenses, 2),
        "savings_impact": f"Savings deplete by {ctx.currency}{ctx.expenses:,.0f}/month with no income coming in.",
        "emergency_buffer_before_months": round(coverage, 1) if coverage is not None else None,
        "emergency_buffer_after_months": timeline[-1]["emergency_buffer_months"] if timeline else None,
        "coverage_months": round(coverage, 1) if coverage is not None else None,
        "requested_months": months_i,
        "goal_progress_before_pct": ctx.goal_progress_pct,
    }
    assumptions = [
        "Assumes monthly expenses stay constant with zero income during the period.",
        "Assumes no other income sources, insurance payouts, severance, or borrowing kick in.",
    ]
    risks = []
    if coverage is not None and months_i > coverage:
        shortfall_total = ctx.expenses * (months_i - coverage)
        risks.append(f"Your emergency fund only covers about {coverage:.1f} months — you'd fall short by roughly {ctx.currency}{shortfall_total:,.0f} over the full {months_i}-month period.")
    elif coverage is None:
        risks.append("No expense figure was found on your profile, so coverage couldn't be estimated.")
    return impact, timeline, assumptions, risks


def calc_generic(ctx: FinancialContext, amount: Optional[float], months: Optional[float]):
    months_i = round(months) if months else 12
    timeline = []
    if amount:
        # Treat an unclassified amount as a recurring monthly effect on surplus,
        # the most conservative and broadly-applicable reading.
        new_surplus = ctx.surplus - amount
        running_savings = ctx.savings
        prev = 0
        for m in pick_milestones(months_i):
            running_savings += new_surplus * (m - prev)
            prev = m
            timeline.append({
                "label": format_months(m), "months": m,
                "projected_savings": round(running_savings, 2),
            })
        impact = {
            "monthly_surplus_before": round(ctx.surplus, 2),
            "monthly_surplus_after": round(new_surplus, 2),
            "emergency_buffer_before_months": round(ctx.buffer_months, 1) if ctx.buffer_months is not None else None,
            "goal_progress_before_pct": ctx.goal_progress_pct,
        }
        assumptions = [f"Treated {ctx.currency}{amount:,.0f} as a recurring monthly amount since the scenario didn't map to a specific known pattern."]
    else:
        impact = {
            "monthly_surplus_before": round(ctx.surplus, 2),
            "emergency_buffer_before_months": round(ctx.buffer_months, 1) if ctx.buffer_months is not None else None,
            "goal_progress_before_pct": ctx.goal_progress_pct,
            "note": "No specific amount or duration was detected in this scenario.",
        }
        assumptions = ["No numeric amount was detected in the scenario text, so this shows your current baseline only."]
    risks = []
    if not amount:
        risks.append("Try including a number and time frame (e.g. ‘₹20,000/month for 2 years’) for a precise, calculated answer instead of a qualitative one.")
    return impact, timeline, assumptions, risks


def run_calculator(scenario_type: str, ctx: FinancialContext, params: Dict[str, Any]):
    amount = params.get("amount")
    months = params.get("duration_months")
    if scenario_type == "invest_monthly":
        return calc_invest_monthly(ctx, amount or 0, months or 36)
    if scenario_type == "emi_affordability":
        return calc_emi_affordability(ctx, amount or 0)
    if scenario_type == "increase_savings":
        return calc_increase_savings(ctx, amount or 0)
    if scenario_type == "goal_timeline":
        return calc_goal_timeline(ctx)
    if scenario_type == "income_loss":
        return calc_income_loss(ctx, months or 6)
    return calc_generic(ctx, amount, months)


def validate_result(ctx: FinancialContext, scenario_type: str, params: Dict[str, Any]) -> List[str]:
    """The Check stage: deterministic sanity checks on the inputs that fed
    the calculation, surfaced as risk notes."""
    notes = []
    if ctx.income == 0:
        notes.append("No income figure was found on your profile — results involving surplus may be unreliable.")
    if ctx.expenses == 0:
        notes.append("No expense figure was found on your profile — buffer/runway figures may be unreliable.")
    if scenario_type in ("invest_monthly", "emi_affordability", "increase_savings") and params.get("amount") is None:
        notes.append("No amount was detected in the scenario text — the numbers shown fall back to defaults rather than your specific figure.")
    return notes
