from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.core.auth import get_current_user
from backend.models.domain import User, Profile, StartupMetricSnapshot, StartupTransaction, StartupDecisionLog
from backend.schemas.startup_models import (
    StartupOverviewResponse, TransactionCreate, TransactionUpdate, TransactionResponse, HisaabSummaryResponse, WeeklyReportResponse,
    WeeklySpendReportResponse, WeeklySpendReportListItem,
)
from backend.models.domain import StartupWeeklyReport
from backend.schemas.api_models import ScenarioSimulateResponse, GenericResponse
from backend.services.startup_engine import (
    build_context, compute_metrics, compute_goals, generate_alerts, capture_snapshot_if_needed,
    build_daily_brief, build_weekly_report, MetricResult,
    build_health_indicators, build_expense_breakdown, build_revenue_breakdown, metric_history,
    build_weekly_category_spend, flag_category_concerns,
)

router = APIRouter(prefix="/startup", tags=["Startup"])


def _get_startup_profile(current_user: User, db: Session) -> Profile:
    profile = db.query(Profile).filter(Profile.user_id == current_user.id, Profile.key == "startup").first()
    if not profile or not profile.startup_profile:
        raise HTTPException(status_code=404, detail="Startup profile not found. Please complete Startup onboarding first.")
    return profile


def _decision_outcome_text(d: StartupDecisionLog) -> str:
    rs = d.result_summary or {}
    parts = []
    rb, ra = rs.get("runway_before"), rs.get("runway_after")
    if rb is not None and ra is not None:
        parts.append(f"Runway {rb:.1f} → {ra:.1f} mo")
    hb, ha = rs.get("financial_health_before"), rs.get("financial_health_after")
    if hb is not None and ha is not None:
        parts.append(f"Health {hb:.0f} → {ha:.0f}")
    if not parts:
        cb, ca = rs.get("cash_before"), rs.get("cash_after")
        if cb is not None and ca is not None:
            parts.append(f"Cash {cb:,.0f} → {ca:,.0f}")
    return "; ".join(parts) if parts else (rs.get("note") or "Logged")


def _decision_predicted_actual(d: StartupDecisionLog, current_runway: float, current_health: float) -> tuple:
    """Compares what a past decision predicted vs. where the twin actually
    stands today — deterministic, no re-simulation, just a direct comparison
    of stored predicted values against the current live metrics."""
    rs = d.result_summary or {}
    predicted = {
        "runway_after": rs.get("runway_after"), "financial_health_after": rs.get("financial_health_after"),
        "cash_after": rs.get("cash_after"), "net_burn_after": rs.get("net_burn_after"),
    }
    actual_now = {"runway": current_runway, "financial_health": current_health}

    ra = rs.get("runway_after")
    if ra is None or current_runway is None:
        status = "unknown"
    elif current_runway >= ra * 0.9:
        status = "on_track"
    else:
        status = "diverged"
    return predicted, actual_now, status


def build_overview_payload(db: Session, profile: Profile) -> dict:
    """Shared by GET /startup/overview and POST /onboard/startup (the initial twin build)."""
    sp = profile.startup_profile
    ctx = build_context(sp)
    snapshots = (db.query(StartupMetricSnapshot)
                 .filter(StartupMetricSnapshot.profile_id == profile.id)
                 .order_by(StartupMetricSnapshot.snapshot_date).all())
    metrics = compute_metrics(ctx, snapshots)
    capture_snapshot_if_needed(db, profile.id, ctx, metrics)

    goals = compute_goals(ctx, metrics)
    alerts = generate_alerts(ctx, metrics, goals)
    health_indicators = build_health_indicators(ctx, metrics, goals)

    transactions = db.query(StartupTransaction).filter(StartupTransaction.profile_id == profile.id).all()
    expense_breakdown = build_expense_breakdown(ctx, [t for t in transactions if t.type == "out"])
    revenue_breakdown = build_revenue_breakdown(ctx, [t for t in transactions if t.type == "in"])

    decisions = (db.query(StartupDecisionLog)
                 .filter(StartupDecisionLog.profile_id == profile.id)
                 .order_by(StartupDecisionLog.created_at.desc()).limit(5).all())
    current_runway = metrics["runway"].value
    current_health = metrics["financial_health"].value
    recent_decisions = []
    for d in decisions:
        predicted, actual_now, status = _decision_predicted_actual(d, current_runway, current_health)
        recent_decisions.append({
            "title": d.title, "decision_type": d.decision_type, "outcome": _decision_outcome_text(d),
            "tag": d.tag, "created_at": d.created_at.isoformat(),
            "predicted": predicted, "actual_now": actual_now, "decision_status": status,
        })

    daily_brief = build_daily_brief(ctx, metrics, snapshots)

    return {
        "currency": ctx.currency,
        "company": {
            "company_name": sp.company_name, "industry": sp.industry, "business_model": sp.business_model,
            "founded_year": sp.founded_year, "stage": sp.stage, "location": sp.location, "website": sp.website,
            "headcount": sp.headcount, "founder_name": sp.founder_name, "preferred_language": sp.preferred_language,
        },
        "metrics": {k: v.to_dict() for k, v in metrics.items() if isinstance(v, MetricResult)},
        "cash_projection": metrics["cash_projection"],
        "hiring_capacity": metrics["hiring_capacity"],
        "goals": goals,
        "alerts": alerts,
        "recent_decisions": recent_decisions,
        "daily_brief": daily_brief,
        "health_indicators": health_indicators,
        "history": metric_history(snapshots),
        "expense_breakdown": expense_breakdown,
        "revenue_breakdown": revenue_breakdown,
    }


def log_startup_decision(db: Session, profile: Profile, scenario_text: str, response: ScenarioSimulateResponse) -> None:
    """Persists a Simulate-tab run (or the onboarding decision) as a Recent Decision entry."""
    if response.mode != "scenario":
        return
    impact = response.financial_impact or {}
    tag = "neutral"
    ra, rb = impact.get("runway_after"), impact.get("runway_before")
    if ra is not None and rb is not None:
        tag = "good" if ra >= rb else "warn"
    elif response.risks and response.risks != ["No material risks identified from the available data."]:
        tag = "warn"
    log = StartupDecisionLog(
        profile_id=profile.id, title=scenario_text[:120], decision_type=response.scenario_type,
        scenario_text=scenario_text, result_summary=impact, tag=tag,
    )
    db.add(log)
    db.commit()


@router.get("/overview", response_model=StartupOverviewResponse)
def get_overview(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _get_startup_profile(current_user, db)
    return build_overview_payload(db, profile)


# ---------------------------------------------------------------------------
# Hisaab — money in / money out ledger, categorized
# ---------------------------------------------------------------------------

@router.get("/hisaab", response_model=HisaabSummaryResponse)
def get_hisaab(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _get_startup_profile(current_user, db)
    txns = (db.query(StartupTransaction).filter(StartupTransaction.profile_id == profile.id)
            .order_by(StartupTransaction.txn_date.desc(), StartupTransaction.created_at.desc()).all())

    money_in = sum(t.amount for t in txns if t.type == "in")
    money_out = sum(t.amount for t in txns if t.type == "out")

    by_cat: dict = {}
    for t in txns:
        key = (t.type, t.category or "Uncategorized")
        by_cat[key] = by_cat.get(key, 0) + t.amount
    by_category = [{"type": k[0], "category": k[1], "amount": round(v, 2)} for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1])]

    return {
        "currency": "₹", "money_in": round(money_in, 2), "money_out": round(money_out, 2), "net": round(money_in - money_out, 2),
        "by_category": by_category,
        "transactions": [_txn_to_dict(t) for t in txns],
    }


def _txn_to_dict(txn: StartupTransaction) -> dict:
    return {
        "id": txn.id, "type": txn.type, "category": txn.category, "amount": txn.amount, "description": txn.description,
        "txn_date": txn.txn_date.isoformat(), "source": txn.source or "manual",
        "created_at": txn.created_at.isoformat(),
        "updated_at": txn.updated_at.isoformat() if txn.updated_at else None,
    }


@router.post("/hisaab/transactions", response_model=TransactionResponse)
def add_transaction(req: TransactionCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _get_startup_profile(current_user, db)
    if req.type not in ("in", "out"):
        raise HTTPException(status_code=400, detail="type must be 'in' or 'out'")
    if req.amount is None or req.amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be a positive number")

    txn_date = date.fromisoformat(req.txn_date) if req.txn_date else date.today()
    txn = StartupTransaction(profile_id=profile.id, type=req.type, category=req.category or "Uncategorized",
                              amount=req.amount, description=req.description, txn_date=txn_date,
                              source=req.source or "manual")
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return _txn_to_dict(txn)


@router.put("/hisaab/transactions/{txn_id}", response_model=TransactionResponse)
def update_transaction(txn_id: int, req: TransactionUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _get_startup_profile(current_user, db)
    txn = db.query(StartupTransaction).filter(StartupTransaction.id == txn_id, StartupTransaction.profile_id == profile.id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if req.type is not None:
        if req.type not in ("in", "out"):
            raise HTTPException(status_code=400, detail="type must be 'in' or 'out'")
        txn.type = req.type
    if req.category is not None:
        txn.category = req.category or "Uncategorized"
    if req.amount is not None:
        if req.amount <= 0:
            raise HTTPException(status_code=400, detail="amount must be a positive number")
        txn.amount = req.amount
    if req.description is not None:
        txn.description = req.description
    if req.txn_date is not None:
        txn.txn_date = date.fromisoformat(req.txn_date)

    db.commit()
    db.refresh(txn)
    return _txn_to_dict(txn)


@router.delete("/hisaab/transactions/{txn_id}", response_model=GenericResponse)
def delete_transaction(txn_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _get_startup_profile(current_user, db)
    txn = db.query(StartupTransaction).filter(StartupTransaction.id == txn_id, StartupTransaction.profile_id == profile.id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    db.delete(txn)
    db.commit()
    return {"success": True, "message": "Transaction deleted"}


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@router.get("/reports/weekly", response_model=WeeklyReportResponse)
def get_weekly_report(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _get_startup_profile(current_user, db)
    sp = profile.startup_profile
    ctx = build_context(sp)
    snapshots = (db.query(StartupMetricSnapshot)
                 .filter(StartupMetricSnapshot.profile_id == profile.id)
                 .order_by(StartupMetricSnapshot.snapshot_date).all())
    metrics = compute_metrics(ctx, snapshots)
    return build_weekly_report(ctx, metrics, snapshots)


def _weekly_report_to_dict(r: StartupWeeklyReport) -> dict:
    return {
        "id": r.id, "week_start": r.week_start.isoformat(), "week_end": r.week_end.isoformat(),
        "currency": r.currency or "₹", "category_spend": r.category_spend or {},
        "flags": r.flags or [], "suggestions": r.suggestions or [],
        "created_at": r.created_at.isoformat(),
    }


@router.get("/reports/weekly-suggestions", response_model=WeeklySpendReportResponse)
def get_weekly_suggestions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Generates (or returns the already-saved) report for the CURRENT
    Mon-Sun calendar week. Idempotent: calling this repeatedly within the
    same week regenerates the numbers fresh (since new transactions may have
    been logged) but always overwrites the same row rather than creating
    duplicates, keyed on (profile_id, week_start)."""
    profile = _get_startup_profile(current_user, db)
    sp = profile.startup_profile
    ctx = build_context(sp)
    snapshots = (db.query(StartupMetricSnapshot)
                 .filter(StartupMetricSnapshot.profile_id == profile.id)
                 .order_by(StartupMetricSnapshot.snapshot_date).all())
    metrics = compute_metrics(ctx, snapshots)

    transactions = db.query(StartupTransaction).filter(StartupTransaction.profile_id == profile.id).all()
    category_spend = build_weekly_category_spend(transactions)
    flags = flag_category_concerns(category_spend, ctx, metrics)

    from backend.agents.startup_orchestrator import startup_orchestrator
    suggestions = startup_orchestrator.generate_weekly_suggestions(category_spend, flags, ctx, metrics)

    week_start = date.fromisoformat(category_spend["week_range"]["start"])
    week_end = date.fromisoformat(category_spend["week_range"]["end"])

    existing = db.query(StartupWeeklyReport).filter(
        StartupWeeklyReport.profile_id == profile.id, StartupWeeklyReport.week_start == week_start
    ).first()
    if existing:
        existing.week_end = week_end
        existing.currency = ctx.currency
        existing.category_spend = category_spend
        existing.flags = flags
        existing.suggestions = suggestions
        report = existing
    else:
        report = StartupWeeklyReport(
            profile_id=profile.id, week_start=week_start, week_end=week_end, currency=ctx.currency,
            category_spend=category_spend, flags=flags, suggestions=suggestions,
        )
        db.add(report)
    db.commit()
    db.refresh(report)
    return _weekly_report_to_dict(report)


@router.get("/reports/weekly-suggestions/history", response_model=List[WeeklySpendReportListItem])
def list_weekly_suggestions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Past saved weekly reports, most recent first — for a 'view previous weeks' list."""
    profile = _get_startup_profile(current_user, db)
    reports = (db.query(StartupWeeklyReport).filter(StartupWeeklyReport.profile_id == profile.id)
               .order_by(StartupWeeklyReport.week_start.desc()).limit(26).all())
    return [{
        "id": r.id, "week_start": r.week_start.isoformat(), "week_end": r.week_end.isoformat(),
        "this_week_total": (r.category_spend or {}).get("this_week_total"),
        "created_at": r.created_at.isoformat(),
    } for r in reports]


@router.get("/reports/weekly-suggestions/{report_id}", response_model=WeeklySpendReportResponse)
def get_saved_weekly_report(report_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Fetch one specific past week's saved report by id, e.g. for re-downloading its PDF."""
    profile = _get_startup_profile(current_user, db)
    report = db.query(StartupWeeklyReport).filter(
        StartupWeeklyReport.id == report_id, StartupWeeklyReport.profile_id == profile.id
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return _weekly_report_to_dict(report)
