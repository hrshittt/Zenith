"""Orchestrator for the Startup journey's Ask Twin and Simulate flows.

Structurally mirrors `backend/agents/orchestrator.py`, but is a fully
separate class grounded in the Startup twin (`startup_engine.py` /
`startup_scenario.py`) instead of the Individual's `financial_simulator.py`.
Reuses genuinely persona-agnostic infrastructure only: the generic `Agent`
class and its `risk_agent`/`compliance_agent` instances from `sub_agents.py`,
and `gemini_service`.
"""
import datetime
from typing import Any, Dict, List, Optional, Tuple

from backend.agents.sub_agents import Agent, risk_agent, compliance_agent
from backend.agents.startup_prompts import (
    STARTUP_EXPLAINER_SYSTEM_PROMPT, STARTUP_RECOMMEND_SYSTEM_PROMPT, STARTUP_TEACH_SYSTEM_PROMPT,
)
from backend.schemas.api_models import ChatResponse, ScenarioSimulateResponse, StageTrace
from backend.services.gemini_service import gemini_service
from backend.services.startup_engine import (
    StartupContext, MetricResult, build_context, compute_metrics, compute_goals, generate_alerts,
    metric_history, build_expense_breakdown,
)
from backend.services.startup_scenario import (
    classify_intent, parse_scenario, describe_understanding, run_calculator, validate_result,
    generate_comparison_variants,
)

startup_explainer_agent = Agent(
    name="Tathya",
    description="Converts Startup Financial Twin data + simulation output into the final structured, human-readable response.",
    system_prompt_override=STARTUP_EXPLAINER_SYSTEM_PROMPT,
)

# Deterministic keyword routing for Ask Twin's "show a relevant chart" behavior
# — never an LLM judgment call. Only numeric/trend-shaped questions get a
# visualization; small talk and qualitative questions don't force one.
_RUNWAY_VISUAL_KEYWORDS = ("runway", "cash out", "cash left", "how much cash", "how much money", "money left")
_BURN_VISUAL_KEYWORDS = ("burn", "expense", "expenses", "spending", "spend", "cost", "costs")
_REVENUE_GOAL_VISUAL_KEYWORDS = ("revenue", "arr", "mrr", "goal", "on track", "growth", "customer", "grew", "growing")


def _classify_visual_intent(text: str) -> Optional[str]:
    t = text.lower()
    if any(k in t for k in _RUNWAY_VISUAL_KEYWORDS):
        return "runway"
    if any(k in t for k in _BURN_VISUAL_KEYWORDS):
        return "burn"
    if any(k in t for k in _REVENUE_GOAL_VISUAL_KEYWORDS):
        return "revenue_goal"
    return None


def _build_visualization(visual_intent: str, ctx: StartupContext, metrics: Dict[str, Any], goals: List[Dict[str, Any]], profile: Any) -> Optional[Dict[str, Any]]:
    history = metric_history(list(profile.startup_snapshots))
    if visual_intent == "runway":
        return {
            "type": "cash_runway", "history": history,
            "projection": metrics["cash_projection"],
            "runway": metrics["runway"].to_dict(), "cash_position": metrics["cash_position"].to_dict(),
        }
    if visual_intent == "burn":
        out_txns = [t for t in profile.startup_transactions if t.type == "out"]
        return {
            "type": "expense_breakdown", "history": history,
            "breakdown": build_expense_breakdown(ctx, out_txns),
            "gross_burn": metrics["gross_burn"].to_dict(), "expense_growth": metrics["expense_growth"].to_dict(),
        }
    if visual_intent == "revenue_goal":
        return {
            "type": "revenue_goals", "history": history, "goals": goals,
            "revenue": metrics["revenue"].to_dict(), "revenue_growth": metrics["revenue_growth"].to_dict(),
        }
    return None


def _ctx_and_metrics(profile: Any) -> Tuple[StartupContext, Dict[str, Any], list]:
    ctx = build_context(profile.startup_profile)
    snapshots = list(profile.startup_snapshots)
    metrics = compute_metrics(ctx, snapshots)
    return ctx, metrics, snapshots


def _metrics_to_dict(metrics: Dict[str, Any]) -> Dict[str, Any]:
    return {k: (v.to_dict() if isinstance(v, MetricResult) else v) for k, v in metrics.items()}


class StartupOrchestrator:
    def process_query(self, profile: Any, query: str, chat_history: List[Dict[str, str]] = None) -> ChatResponse:
        trace = []
        ctx, metrics, _snapshots = _ctx_and_metrics(profile)
        goals = compute_goals(ctx, metrics)
        alerts = generate_alerts(ctx, metrics, goals)

        data_ctx = {
            "currency": ctx.currency,
            "company": {"name": ctx.company_name, "stage": ctx.stage},
            "metrics": _metrics_to_dict(metrics),
            "goals": goals,
            "alerts": alerts[:3],
        }
        data_res = str(data_ctx)
        trace.append({"agent": "Data", "action": "Fetched Startup Financial Twin metrics, goals, and alerts", "output": data_res})

        risk_res = risk_agent.process({"data": data_res}, f"Simulate financial impact for query: {query}")
        trace.append({"agent": "Risk", "action": "Simulated potential outcomes", "output": risk_res})

        comp_res = compliance_agent.process({"simulation": risk_res}, f"Check for unlicensed advice flags in this context: {query}")
        trace.append({"agent": "Compliance", "action": "Checked against guardrails", "output": comp_res})

        exp_res = startup_explainer_agent.process(
            {"data": data_res, "simulation": risk_res, "compliance": comp_res},
            f"Format response for query: {query}", chat_history=chat_history,
        )
        trace.append({"agent": "Tathya", "action": "Formatted final structured output", "output": exp_res})

        # Numeric/trend-shaped questions get a matching chart, built entirely
        # from the metrics already computed above — never from the LLM. Simple
        # questions (greetings, qualitative asks) get none.
        visual_intent = _classify_visual_intent(query)
        visualization = _build_visualization(visual_intent, ctx, metrics, goals, profile) if visual_intent else None
        if visualization:
            trace.append({"agent": "Data", "action": f"Attached a '{visualization['type']}' visualization", "output": str({"type": visualization["type"]})})

        return ChatResponse(
            session_id="",
            answer=exp_res,
            confidence="high",
            sources=[{"source": "Startup Financial Twin", "timestamp": datetime.datetime.utcnow().isoformat()}],
            reasoning_trace=trace,
            disclaimer="This is an AI-generated simulation and does not constitute financial advice. " + comp_res,
            visualization=visualization,
        )

    def run_scenario_simulation(self, profile: Any, scenario_text: str) -> ScenarioSimulateResponse:
        if classify_intent(scenario_text) == "informational":
            return self._answer_informational(profile, scenario_text)
        return self._run_scenario_pipeline(profile, scenario_text)

    def _answer_informational(self, profile: Any, query_text: str) -> ScenarioSimulateResponse:
        stages: List[Dict[str, str]] = [{
            "agent": "Understand", "status": "done",
            "summary": "Classified as an informational question about your current startup finances — routed to the same grounded flow Ask Twin uses, rather than a hypothetical simulation.",
        }]
        ctx, metrics, _snapshots = _ctx_and_metrics(profile)
        stages.append({
            "agent": "Watch", "status": "done",
            "summary": f"Retrieved your Startup Financial Twin — cash {metrics['cash_position'].display}, gross burn {metrics['gross_burn'].display}, net burn {metrics['net_burn'].display}, runway {metrics['runway'].display}.",
        })

        chat_response = self.process_query(profile, query_text)

        stages.append({"agent": "Check", "status": "done", "summary": "Answered directly from your stored Startup Financial Twin data — no hypothetical numbers or projections were introduced."})

        financial_impact = {k: v.value for k, v in metrics.items() if isinstance(v, MetricResult)}
        return ScenarioSimulateResponse(
            scenario=query_text, scenario_type="informational", mode="informational", parsed_params={},
            stages=[StageTrace(**s) for s in stages], financial_impact=financial_impact, timeline=[],
            recommendation=chat_response.answer, why="", risks=[], assumptions=[], teaching="",
            disclaimer=chat_response.disclaimer,
        )

    def _run_scenario_pipeline(self, profile: Any, scenario_text: str) -> ScenarioSimulateResponse:
        stages: List[Dict[str, str]] = []

        scenario_type, params = parse_scenario(scenario_text)
        stages.append({"agent": "Understand", "status": "done", "summary": describe_understanding(scenario_type, params, "₹")})

        ctx, metrics, snapshots = _ctx_and_metrics(profile)
        stages.append({
            "agent": "Watch", "status": "done",
            "summary": f"Retrieved your Startup Financial Twin — cash {metrics['cash_position'].display}, gross burn {metrics['gross_burn'].display}, net burn {metrics['net_burn'].display}, runway {metrics['runway'].display}.",
        })

        impact, timeline, assumptions, calc_risks, after_metrics = run_calculator(scenario_type, ctx, metrics, snapshots, params)
        stages.append({"agent": "Simulate", "status": "done", "summary": f"Ran deterministic financial projections across {len(timeline)} milestone(s)."})

        timeline_series = None
        baseline_series = (metrics.get("cash_projection") or {}).get("series")
        scenario_series = (after_metrics.get("cash_projection") or {}).get("series") if after_metrics else None
        if baseline_series or scenario_series:
            timeline_series = {
                "unit": "INR", "horizon_months": 12,
                "baseline": baseline_series or [], "scenario": scenario_series or [],
            }

        comparison_variants = generate_comparison_variants(scenario_type, ctx, metrics, snapshots, params)

        recommendation, why = self._recommend(scenario_text, ctx, scenario_type, impact, calc_risks)
        stages.append({"agent": "Recommend", "status": "done", "summary": "Generated a personalized recommendation grounded in the computed numbers."})

        teaching = self._teach(scenario_text, scenario_type, ctx)
        stages.append({"agent": "Teach", "status": "done", "summary": "Explained the financial concept behind this scenario."})

        check_notes = validate_result(ctx, scenario_type, params)
        risks = list(calc_risks) + check_notes
        stages.append({"agent": "Check", "status": "done", "summary": f"Validated calculation inputs — flagged {len(risks)} risk(s)." if risks else "Validated calculation inputs — no red flags found."})

        return ScenarioSimulateResponse(
            scenario=scenario_text, scenario_type=scenario_type, mode="scenario",
            parsed_params={k: v for k, v in params.items() if v is not None},
            stages=[StageTrace(**s) for s in stages],
            financial_impact=impact, timeline=timeline,
            recommendation=recommendation, why=why,
            risks=risks if risks else ["No material risks identified from the available data."],
            assumptions=assumptions, teaching=teaching,
            disclaimer="This simulation is educational and based on your current Startup Financial Twin. Consider consulting your board or a financial advisor before making major financial decisions.",
            timeline_series=timeline_series, comparison_variants=comparison_variants,
        )

    def _recommend(self, scenario_text, ctx: StartupContext, scenario_type, impact, calc_risks):
        if gemini_service.available():
            prompt = (
                f"Scenario: {scenario_text}\n"
                f"Scenario type: {scenario_type}\n"
                f"Company: {ctx.company_name or 'Unnamed'} ({ctx.stage or 'stage unknown'})\n"
                f"Already-computed financial impact: {impact}\n"
                f"Already-flagged risks: {calc_risks}\n"
            )
            data = gemini_service.generate_json(prompt, system_instruction=STARTUP_RECOMMEND_SYSTEM_PROMPT, temperature=0.4)
            if data and data.get("recommendation"):
                return data.get("recommendation", ""), data.get("why", "")
        return self._fallback_recommendation(impact, calc_risks, ctx)

    def _teach(self, scenario_text, scenario_type, ctx: StartupContext):
        if gemini_service.available():
            prompt = f"Scenario: {scenario_text}\nScenario type: {scenario_type}\nCompany stage: {ctx.stage}"
            try:
                return gemini_service.generate(prompt, system_instruction=STARTUP_TEACH_SYSTEM_PROMPT, temperature=0.5, max_output_tokens=512)
            except Exception:
                pass
        return self._fallback_teaching(scenario_type)

    @staticmethod
    def _fallback_recommendation(impact, calc_risks, ctx: StartupContext):
        if calc_risks:
            return ("Hold off before committing to this exactly as described.", calc_risks[0])
        runway_after = impact.get("runway_after")
        if runway_after is not None and runway_after < 3:
            return (
                "This isn't advisable as described — it would push runway to a critically low level.",
                f"Projected runway after this change is {runway_after:.1f} months, under the 3-month critical threshold.",
            )
        return (
            "This looks workable based on your current numbers — proceed, but keep watching runway and burn.",
            "Projected runway stays above the critical threshold given your current cash and burn trajectory.",
        )

    @staticmethod
    def _fallback_teaching(scenario_type):
        concepts = {
            "hire_people": "Every hire adds fully-loaded monthly cost (salary, benefits, overhead) to your burn — the real question isn't just 'can I afford this month' but 'how many months of runway does this cost me', since that's what determines how much time you have left to hit your next milestone.",
            "raise_funding": "Raising capital extends runway but doesn't fix an unsustainable burn rate on its own — money bought with equity is the most expensive kind, since it's permanently diluting your ownership, so it's worth pairing a raise with a real plan to improve burn multiple or reach break-even.",
            "change_expense": "Every recurring cost change compounds monthly — a small increase in fixed costs today keeps costing you every month going forward, which is why it shows up as a runway change, not just a one-time hit.",
            "change_revenue": "Revenue growth is the only lever that improves your runway without diluting equity or cutting into your team — which is why founders track 'burn multiple' (burn ÷ net new revenue) as closely as burn itself.",
        }
        return concepts.get(scenario_type, "Every startup financial decision trades off runway (time left to operate), growth (revenue/traction), and dilution (equity given up to buy more time). Weighing a scenario means checking it against all three, not just the immediate cost or benefit.")


startup_orchestrator = StartupOrchestrator()
