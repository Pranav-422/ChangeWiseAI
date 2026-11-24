"""One call that runs the whole Member 2 engine. This is the interface Member 3 integrates."""
import hashlib
import json
from time import perf_counter

from .action_generator import generate_candidate_plans, make_plan
from .config import load_config, load_simulator
from .constraints import input_errors
from .escalation import (
    create_escalation_record, detect_near_ties, escalation, residual_shortage_record,
)
from .optimizer import mark_redundant, rank_feasible_plans, select_top_plans
from .planner import evaluate_all_candidates, evaluate_candidate_plan
from .recommendation import (
    effective_week_comparison, generate_no_feasible_plan_response, generate_recommendations,
)
from .robustness import check_robustness_escalation, compare_plan_robustness


def snapshot_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _solver_plans(data, menus, config):
    """Plans for spaces too large to enumerate: request optima one by one."""
    from ..solver import first_available  # deferred: the solver package imports this engine
    name, backend = first_available(config["solver"]["backend"])
    actions = backend.solve(data, menus, config["solver"]["max_solutions"],
                            config["solver"]["time_limit_seconds"])
    return name, [make_plan(a, data, "SOLVER") for a in actions]


def _rejected_view(plan):
    return {k: plan[k] for k in ("plan_id", "actions", "source", "feasibility", "rejection_reasons")}


def run_optimization(data, config=None, simulate=None):
    """Full run on one dataset. Returns a JSON-serialisable result (contracts/output_schema.json).

    Everything except `computation_seconds` is a pure function of (data, config, simulator), which
    is what audit replay compares.
    """
    started = perf_counter()
    config = config or load_config()
    simulate = simulate or load_simulator(config)
    result = {
        "engine_version": config["engine_version"],
        "simulator": f"{simulate.__module__}:{simulate.__name__}",
        "scenario_id": data.get("scenario_id"),
        "input_hash": snapshot_hash(data),
        "config_hash": snapshot_hash(config),
        "method": None, "decision": None, "requires_planner_review": True,
        "recommended_plan_id": None, "recommendations": [], "ranked_plans": [],
        "rejected_plans": [], "skipped_actions": [], "near_ties": [], "escalations": [],
        "effective_week_comparison": [],
        "counts": {"combinations": 0, "candidates": 0, "feasible": 0, "rejected": 0},
    }

    def finish(decision):
        result["decision"] = decision
        result["requires_planner_review"] = bool(result["escalations"])
        result["computation_seconds"] = round(perf_counter() - started, 4)
        return result

    errors = input_errors(data)  # rule 7: no plan is generated from bad data
    if errors:
        result["escalations"] = [escalation(
            "INVALID_DATA", "Input records are invalid or conflicting; no plan is recommended.",
            evidence=errors)]
        return finish("INVALID_DATA")

    candidates = generate_candidate_plans(data, config)
    plans = candidates["plans"]
    result["method"] = "ENUMERATION"
    if candidates["truncated"]:
        backend, found = _solver_plans(data, candidates["menus"], config)
        result["method"] = f"SOLVER:{backend}"
        plans = plans + found
    evaluated = evaluate_all_candidates(plans, simulate, data)
    rejected = [_rejected_view(p) for p in evaluated if p["feasibility"] == "REJECTED"]
    ranked = rank_feasible_plans(evaluated)
    if config["ranking"]["skip_redundant_variants"]:
        ranked = mark_redundant(ranked)
    result.update(
        rejected_plans=rejected, skipped_actions=candidates["skipped_actions"],
        ranked_plans=[{k: v for k, v in p.items() if k != "simulation"} for p in ranked],
        counts={"combinations": candidates["combination_count"], "candidates": len(evaluated),
                "feasible": len(ranked), "rejected": len(rejected)})
    if not ranked:
        result["escalations"] = [generate_no_feasible_plan_response(rejected)["escalation"]]
        return finish("NO_FEASIBLE_PLAN")

    top_n = config["ranking"]["top_n"]
    top = select_top_plans(ranked, top_n)
    near_ties = detect_near_ties(ranked, config)
    robustness = compare_plan_robustness(top, data, simulate, config)
    recommendations = generate_recommendations(ranked, top_n, near_ties, robustness)
    for record, plan in zip(recommendations, top):
        record["weekly"] = plan["simulation"]["weekly"]
    weeks = sorted({*config["action_space"]["effective_weeks"],
                    data["engineering_change"]["effective_week"]})
    result.update(near_ties=near_ties, recommendations=recommendations,
                  recommended_plan_id=top[0]["plan_id"],
                  effective_week_comparison=effective_week_comparison(ranked, weeks))

    if top[0]["shortage_units"] > 0:
        result["escalations"].append(residual_shortage_record(top[0]))
    if near_ties:
        rivals = {t["plan_b"] for t in near_ties}
        competing = [top[0]] + [p for p in ranked if p["plan_id"] in rivals]
        result["escalations"].append(create_escalation_record(competing, near_ties))
    fragile = check_robustness_escalation(recommendations, config)
    if fragile:
        result["escalations"].append(fragile)
    return finish("ESCALATED" if result["escalations"] else "RECOMMENDED")


def evaluate_custom_plan(actions, data, config=None, simulate=None):
    """Evaluate a planner-modified plan with the same rules, simulator and costs."""
    config = config or load_config()
    return evaluate_candidate_plan(
        make_plan(actions, data, "PLANNER"), simulate or load_simulator(config), data)


def replay_matches(result, data, config=None, simulate=None):
    """Audit replay: rerun and compare everything except wall-clock time."""
    again = run_optimization(data, config, simulate)
    return {**again, "computation_seconds": 0} == {**result, "computation_seconds": 0}
