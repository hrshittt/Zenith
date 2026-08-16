"""
Natural-language scenario simulation for the Startup journey (the Simulate
tab). Parsing is regex-based (numbers/percentages must come from the text
deterministically, never guessed by an LLM); every calculator re-derives the
"after" state by calling straight back into `startup_engine.compute_metrics`
on a modified copy of the same `StartupContext` — so a simulated scenario
uses exactly the same formulas (Runway, Financial Health, etc.) as the real
Overview, just fed slightly different inputs. Gemini/Tathya (in
`startup_orchestrator.py`) only phrases a recommendation around the numbers
computed here — it never invents or recalculates them.
"""
import re
from dataclasses import replace
from typing import Any, Dict, List, Optional, Tuple

from backend.services.financial_simulator import extract_tokens, format_months
from backend.services.startup_engine import StartupContext, compute_metrics, compute_goals


_HIRE_COUNT_RE = re.compile(
    r'\bhire\s+(\d+)\b|\b(\d+)\s+(?:people|persons?|engineers?|employees?|hires?|staff|reps?|salespeople|folks)\b',
    re.IGNORECASE,
)
_PCT_RE = re.compile(r'(\d+(?:\.\d+)?)\s*%')
_DECREASE_WORDS = re.compile(r'\b(cut|reduce|decrease|lower|shrink|trim|slash)\b', re.IGNORECASE)
_PER_HIRE_QUALIFIER = re.compile(r'\beach\b|\bper hire\b|/hire|\bper person\b|\bper employee\b', re.IGNORECASE)


# ---------------------------------------------------------------------------
# Classification + parsing
# ---------------------------------------------------------------------------

def classify_scenario(text: str) -> str:
    t = text.lower()
    if re.search(r'\braise\s+(the\s+)?(price|pricing|fees?|subscription)', t):
        return "change_revenue"
    if re.search(r'\bhire[sd]?\b', t) or _HIRE_COUNT_RE.search(t):
        return "hire_people"
    if any(k in t for k in ["raise", "fundrais", "seed round", "series a", "series b", "bridge round", "bridge note", "venture debt"]):
        return "raise_funding"
    if any(k in t for k in ["marketing", "ad spend", "advertising", "expense", "cost", "budget", "spend", "rent", "infra", "infrastructure", "salary", "payroll", "tooling", "tools"]):
        return "change_expense"
    if any(k in t for k in ["price", "pricing", "mrr", "revenue", "subscription", "arpu", "sales"]):
        return "change_revenue"
    return "generic"


def parse_scenario(text: str) -> Tuple[str, Dict[str, Any]]:
    scenario_type = classify_scenario(text)
    amounts, months = extract_tokens(text)
    pct_match = _PCT_RE.search(text)
    pct = float(pct_match.group(1)) if pct_match else None
    decreasing = bool(_DECREASE_WORDS.search(text))

    params: Dict[str, Any] = {
        "amount": amounts[0] if amounts else None,
        "duration_months": months,
        "pct": pct,
        "decreasing": decreasing,
    }

    if scenario_type == "hire_people":
        hm = _HIRE_COUNT_RE.search(text)
        headcount = int(hm.group(1) or hm.group(2)) if hm else None
        params["headcount"] = headcount or 1
        params["headcount_assumed"] = headcount is None
        params["cost_per_hire"] = amounts[0] if (amounts and _PER_HIRE_QUALIFIER.search(text)) else None

    return scenario_type, params


_SCENARIO_MARKERS = re.compile(
    r"\b(what if|what happens if|what would happen if|suppose|imagine if|if i |"
    r"can i afford|how quickly can i|how soon can i|how long (would|will) it take)\b",
    re.IGNORECASE,
)
_INFORMATIONAL_MARKERS = re.compile(
    r"\b(what is my|what'?s my|whats my|how is my|how'?s my|how are my|"
    r"am i on track|what'?s the status of my|how much (do|have) i|how much runway)\b",
    re.IGNORECASE,
)


def classify_intent(text: str) -> str:
    """Routes between an informational question about current state (answer
    directly from the twin, no hypothetical) and an actual scenario to run
    through the deterministic calculators."""
    t = text.strip()
    if _SCENARIO_MARKERS.search(t):
        return "scenario"
    if _INFORMATIONAL_MARKERS.search(t):
        return "informational"
    scenario_type = classify_scenario(t)
    if scenario_type in ("hire_people", "raise_funding", "change_expense", "change_revenue"):
        return "scenario"
    amounts, months = extract_tokens(t)
    if amounts or months:
        return "scenario"
    return "informational"


def describe_understanding(scenario_type: str, params: Dict[str, Any], currency: str) -> str:
    label = scenario_type.replace("_", " ")
    parts = []
    if scenario_type == "hire_people":
        parts.append(f"headcount change ≈ {params['headcount']}" + (" (assumed)" if params.get("headcount_assumed") else ""))
        if params.get("cost_per_hire"):
            parts.append(f"cost per hire ≈ {currency}{params['cost_per_hire']:,.0f}/mo")
    else:
        if params.get("amount") is not None:
            parts.append(f"amount ≈ {currency}{params['amount']:,.0f}")
        if params.get("pct") is not None:
            parts.append(f"percentage change ≈ {params['pct']:.0f}%")
    detail = ("Detected " + ", ".join(parts) + ".") if parts else \
        "No specific amount or percentage was detected in the text — showing your current baseline only."
    return f"Classified as a '{label}' scenario. {detail}"


# ---------------------------------------------------------------------------
# Helpers — apply a hypothetical delta to a copy of the context, then
# recompute metrics through the exact same engine used for the real Overview.
# ---------------------------------------------------------------------------

def _apply_expense_delta(ctx: StartupContext, delta: float) -> StartupContext:
    if ctx.fixed_costs is not None or ctx.variable_costs is not None:
        return replace(ctx, variable_costs=(ctx.variable_costs or 0) + delta)
    if ctx.monthly_burn_input is not None:
        return replace(ctx, monthly_burn_input=ctx.monthly_burn_input + delta)
    # No baseline expense figure at all — still surface the delta as a new variable cost.
    return replace(ctx, variable_costs=max(delta, 0))


def _apply_revenue_delta(ctx: StartupContext, delta: float) -> StartupContext:
    new_revenue = (ctx.monthly_revenue or 0) + delta
    new_revenue = max(new_revenue, 0)
    return replace(ctx, monthly_revenue=new_revenue, is_pre_revenue=(ctx.is_pre_revenue and new_revenue == 0))


def _build_impact(ctx: StartupContext, before: Dict[str, Any], new_ctx: StartupContext, after: Dict[str, Any],
                   extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    impact = {
        "cash_before": before["cash_position"].value, "cash_after": after["cash_position"].value,
        "gross_burn_before": before["gross_burn"].value, "gross_burn_after": after["gross_burn"].value,
        "net_burn_before": before["net_burn"].value, "net_burn_after": after["net_burn"].value,
        "runway_before": before["runway"].value, "runway_after": after["runway"].value,
        "revenue_before": ctx.monthly_revenue, "revenue_after": new_ctx.monthly_revenue,
        "financial_health_before": before["financial_health"].value, "financial_health_after": after["financial_health"].value,
    }
    if extra:
        impact.update(extra)
    return impact


def _build_timeline(after: Dict[str, Any]) -> List[Dict[str, Any]]:
    series = (after.get("cash_projection") or {}).get("series", [])
    if not series:
        return []
    milestones = [m for m in (3, 6, 12, 24) if m <= len(series)] or [len(series)]
    out = []
    for m in milestones:
        row = series[m - 1]
        out.append({"label": format_months(m), "months": m, "projected_cash": row["projected_cash"], "projected_net_burn": row["projected_net_burn"]})
    return out


def _goal_impact(ctx: StartupContext, before: Dict[str, Any], new_ctx: StartupContext, after: Dict[str, Any]) -> List[Dict[str, Any]]:
    before_goals = compute_goals(ctx, before)
    after_goals = compute_goals(new_ctx, after)
    out = []
    for b, a in zip(before_goals, after_goals):
        if b.get("progress_pct") is not None or a.get("progress_pct") is not None:
            out.append({"label": b["label"], "progress_before_pct": b.get("progress_pct"), "progress_after_pct": a.get("progress_pct")})
    return out


def _risks_from_after(after: Dict[str, Any]) -> List[str]:
    risks = []
    runway = after["runway"]
    if runway.status != "insufficient_data" and runway.value is not None:
        if runway.value < 3:
            risks.append(f"This would drop runway to {runway.value:.1f} months — critically low.")
        elif runway.value < 6:
            risks.append(f"This would drop runway to {runway.value:.1f} months — below the commonly-used 6-month safety threshold.")
    return risks


# ---------------------------------------------------------------------------
# Calculators
# ---------------------------------------------------------------------------

def calc_hire(ctx: StartupContext, before: Dict[str, Any], snapshots, headcount: int, cost_per_hire: Optional[float]):
    cost_per_hire = cost_per_hire or ctx.cost_per_hire
    if cost_per_hire is None:
        impact = {"headcount_added": headcount, "note": "Cost per hire isn't available — add e.g. '₹1,50,000/hire' to the scenario, or set it on your profile, for a precise projection."}
        return impact, [], ["Assumed no changes besides headcount, but no cost figure was available to project cash/burn/runway impact."], \
            ["Cost per hire is unknown — cash, burn, and runway impact couldn't be computed precisely."], None

    delta = headcount * cost_per_hire
    new_ctx = _apply_expense_delta(ctx, delta)
    after = compute_metrics(new_ctx, snapshots)
    impact = _build_impact(ctx, before, new_ctx, after, extra={"headcount_added": headcount, "added_monthly_cost": round(delta, 2), "goal_impact": _goal_impact(ctx, before, new_ctx, after)})
    assumptions = [
        f"Assumes each new hire costs {ctx.currency}{cost_per_hire:,.0f}/month fully loaded (salary, benefits, overhead), effective immediately.",
        "Assumes revenue and all other costs stay unchanged.",
    ]
    return impact, _build_timeline(after), assumptions, _risks_from_after(after), after


def calc_raise_funding(ctx: StartupContext, before: Dict[str, Any], snapshots, amount: Optional[float]):
    if not amount:
        impact = {"note": "No funding amount was detected in the scenario text (e.g. 'raise ₹2 Cr')."}
        return impact, [], [], ["Include an amount (e.g. '₹2 Cr' or '₹50L') to get a precise projection."], None

    new_ctx = replace(ctx, current_cash=(ctx.current_cash or 0) + amount, total_funding=(ctx.total_funding or 0) + amount, currently_fundraising=False)
    after = compute_metrics(new_ctx, snapshots)
    impact = _build_impact(ctx, before, new_ctx, after, extra={"funding_raised": amount, "goal_impact": _goal_impact(ctx, before, new_ctx, after)})
    assumptions = [
        f"Assumes the full {ctx.currency}{amount:,.0f} lands in cash immediately, with no drawdown schedule.",
        "Assumes monthly burn and revenue are otherwise unchanged.",
    ]
    risks = _risks_from_after(after)
    risks.append("Dilution and cap-table impact aren't modeled here — factor those in separately before deciding on round size or terms.")
    return impact, _build_timeline(after), assumptions, risks, after


def calc_change_expense(ctx: StartupContext, before: Dict[str, Any], snapshots, amount: Optional[float], pct: Optional[float], decreasing: bool):
    gross_before = before["gross_burn"].value
    if amount is None and pct is None:
        impact = {"note": "No amount or percentage was detected in the scenario text."}
        return impact, [], [], ["Include an amount (e.g. '₹50,000/mo') or a percentage (e.g. '20%') for a precise projection."], None

    if pct is not None and gross_before:
        delta = gross_before * (pct / 100)
    else:
        delta = amount or 0
    if decreasing:
        delta = -delta

    new_ctx = _apply_expense_delta(ctx, delta)
    after = compute_metrics(new_ctx, snapshots)
    impact = _build_impact(ctx, before, new_ctx, after, extra={"expense_change": round(delta, 2), "goal_impact": _goal_impact(ctx, before, new_ctx, after)})
    assumptions = [f"Treats this as a recurring monthly {'decrease' if delta < 0 else 'increase'} to expenses starting immediately."]
    if gross_before is None:
        assumptions.append("No baseline Gross Burn was on your profile — this change is shown as a new standalone variable cost.")
    return impact, _build_timeline(after), assumptions, _risks_from_after(after), after


def calc_change_revenue(ctx: StartupContext, before: Dict[str, Any], snapshots, amount: Optional[float], pct: Optional[float], decreasing: bool):
    revenue_before = ctx.monthly_revenue or 0
    if amount is None and pct is None:
        impact = {"note": "No amount or percentage was detected in the scenario text."}
        return impact, [], [], ["Include an amount (e.g. '₹1,00,000/mo more MRR') or a percentage (e.g. '10% price increase') for a precise projection."], None

    if pct is not None:
        delta = revenue_before * (pct / 100)
    else:
        delta = amount or 0
    if decreasing:
        delta = -delta

    new_ctx = _apply_revenue_delta(ctx, delta)
    after = compute_metrics(new_ctx, snapshots)
    impact = _build_impact(ctx, before, new_ctx, after, extra={"revenue_change": round(delta, 2), "goal_impact": _goal_impact(ctx, before, new_ctx, after)})
    assumptions = [f"Treats this as a recurring monthly {'decrease' if delta < 0 else 'increase'} to revenue starting immediately, with costs unchanged."]
    if revenue_before == 0:
        assumptions.append("No baseline revenue was on your profile — this change is modeled starting from ₹0.")
    return impact, _build_timeline(after), assumptions, _risks_from_after(after), after


def calc_generic(ctx: StartupContext, before: Dict[str, Any], snapshots, amount: Optional[float]):
    if not amount:
        impact = {"cash_before": before["cash_position"].value, "runway_before": before["runway"].value,
                   "note": "No specific amount was detected in this scenario."}
        return impact, [], ["No numeric amount was detected, so this shows your current baseline only."], \
            ["Try including a number (e.g. '₹50,000/month') for a precise, calculated answer instead of a qualitative one."], None

    # Most conservative, broadly-applicable reading of an unclassified amount: a new recurring monthly cost.
    new_ctx = _apply_expense_delta(ctx, amount)
    after = compute_metrics(new_ctx, snapshots)
    impact = _build_impact(ctx, before, new_ctx, after, extra={"goal_impact": _goal_impact(ctx, before, new_ctx, after)})
    assumptions = [f"Treated {ctx.currency}{amount:,.0f} as a new recurring monthly cost since the scenario didn't map to a specific known pattern."]
    return impact, _build_timeline(after), assumptions, _risks_from_after(after), after


def run_calculator(scenario_type: str, ctx: StartupContext, before: Dict[str, Any], snapshots, params: Dict[str, Any]):
    """Returns (impact, timeline, assumptions, risks, after_metrics). `after_metrics`
    is the full raw metrics dict for the scenario's post-change state (None when
    nothing concrete enough was detected to compute a change) — used to build
    the Scenario Projection chart and comparison variants without recomputing."""
    if scenario_type == "hire_people":
        return calc_hire(ctx, before, snapshots, params.get("headcount") or 1, params.get("cost_per_hire"))
    if scenario_type == "raise_funding":
        return calc_raise_funding(ctx, before, snapshots, params.get("amount"))
    if scenario_type == "change_expense":
        return calc_change_expense(ctx, before, snapshots, params.get("amount"), params.get("pct"), params.get("decreasing", False))
    if scenario_type == "change_revenue":
        return calc_change_revenue(ctx, before, snapshots, params.get("amount"), params.get("pct"), params.get("decreasing", False))
    return calc_generic(ctx, before, snapshots, params.get("amount"))


# ---------------------------------------------------------------------------
# Comparison variants — "Don't hire / Hire 3 / Hire 5"-style alternatives,
# built by re-running the same deterministic calculator at different
# amounts/headcounts. Only produced for scenario types with a concrete
# detected amount/headcount to vary; None otherwise (frontend hides the
# comparison section rather than showing meaningless 0/0/0 variants).
# ---------------------------------------------------------------------------

def _variant_summary(label: str, impact: Dict[str, Any], risks: List[str]) -> Dict[str, Any]:
    goal_impact = impact.get("goal_impact") or []
    goal_scores = [g["progress_after_pct"] for g in goal_impact if g.get("progress_after_pct") is not None]
    return {
        "label": label,
        "cash_after": impact.get("cash_after"),
        "net_burn_after": impact.get("net_burn_after"),
        "runway_after": impact.get("runway_after"),
        "revenue_after": impact.get("revenue_after"),
        "financial_health_after": impact.get("financial_health_after"),
        "goal_progress_avg_after": round(sum(goal_scores) / len(goal_scores), 1) if goal_scores else None,
        "risk_count": len(risks),
        "is_recommended": False,
    }


def _pick_recommended(variants: List[Dict[str, Any]]) -> None:
    """Deterministic pick — mirrors the same 'prefer the option that clears the
    runway safety floor with the best financial health' logic used elsewhere,
    never an LLM judgment call."""
    if not variants:
        return
    safe = [v for v in variants if v["runway_after"] is None or v["runway_after"] >= 6]
    pool = safe if safe else variants
    best = max(pool, key=lambda v: (v["financial_health_after"] if v["financial_health_after"] is not None else -1))
    best["is_recommended"] = True


def generate_comparison_variants(scenario_type: str, ctx: StartupContext, before: Dict[str, Any], snapshots, params: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    if scenario_type == "hire_people":
        headcount = params.get("headcount") or 1
        cost_per_hire = params.get("cost_per_hire") or ctx.cost_per_hire
        if headcount < 1 or cost_per_hire is None:
            return None
        half = max(1, round(headcount / 2)) if headcount > 1 else headcount
        levels = sorted(set([0, half, headcount]))
        variants = []
        for n in levels:
            label = "Don't hire" if n == 0 else f"Hire {n}"
            if n > 0:
                impact, _t, _a, risks, _after = calc_hire(ctx, before, snapshots, n, cost_per_hire)
            else:
                impact = _build_impact(ctx, before, ctx, before, extra={"headcount_added": 0, "goal_impact": _goal_impact(ctx, before, ctx, before)})
                risks = []
            variants.append(_variant_summary(label, impact, risks))
        _pick_recommended(variants)
        return variants

    if scenario_type == "raise_funding":
        amount = params.get("amount")
        if not amount:
            return None
        levels = [("Don't raise", 0), ("Raise half", amount / 2), ("Raise full amount", amount)]
        variants = []
        for label, amt in levels:
            if amt == 0:
                zero_impact = _build_impact(ctx, before, ctx, before, extra={"goal_impact": _goal_impact(ctx, before, ctx, before)})
                variants.append(_variant_summary(label, zero_impact, []))
            else:
                impact, _t, _a, risks, _after = calc_raise_funding(ctx, before, snapshots, amt)
                variants.append(_variant_summary(label, impact, risks))
        _pick_recommended(variants)
        return variants

    if scenario_type in ("change_expense", "change_revenue"):
        amount = params.get("amount")
        pct = params.get("pct")
        decreasing = params.get("decreasing", False)
        if amount is None and pct is None:
            return None
        calc_fn = calc_change_expense if scenario_type == "change_expense" else calc_change_revenue
        levels = [("No change", 0, None), ("Half", (amount / 2 if amount else None), (pct / 2 if pct else None)), ("Full", amount, pct)]
        variants = []
        for label, amt, p in levels:
            if amt in (None, 0) and p in (None, 0):
                zero_impact = _build_impact(ctx, before, ctx, before, extra={"goal_impact": _goal_impact(ctx, before, ctx, before)})
                variants.append(_variant_summary(label, zero_impact, []))
            else:
                impact, _t, _a, risks, _after = calc_fn(ctx, before, snapshots, amt, p, decreasing)
                variants.append(_variant_summary(label, impact, risks))
        _pick_recommended(variants)
        return variants

    return None


def validate_result(ctx: StartupContext, scenario_type: str, params: Dict[str, Any]) -> List[str]:
    """The Check stage: deterministic sanity checks on the inputs that fed the calculation."""
    notes = []
    if ctx.current_cash is None:
        notes.append("No current cash figure is on your profile — cash/runway results may be unreliable.")
    if ctx.fixed_costs is None and ctx.variable_costs is None and ctx.monthly_burn_input is None:
        notes.append("No expense figure is on your profile — burn/runway results may be unreliable.")
    if scenario_type == "hire_people" and params.get("cost_per_hire") is None and ctx.cost_per_hire is None:
        notes.append("Cost per hire isn't set on your profile or in the scenario text — headcount's impact on burn couldn't be computed.")
    return notes
