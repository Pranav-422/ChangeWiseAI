"""Enumeration versus solver. Both must reach the same objective, re-simulated by the same simulator."""
from ..engine.action_generator import generate_candidate_plans, make_plan
from ..engine.config import load_config, load_simulator
from ..engine.optimizer import objective, rank_feasible_plans
from ..engine.planner import evaluate_all_candidates, evaluate_candidate_plan
from ..solver import BACKENDS, SolverUnavailable, load_backend


def check_solver_agreement(data, config=None, simulate=None):
    config = config or load_config()
    simulate = simulate or load_simulator(config)
    candidates = generate_candidate_plans(data, config)
    if candidates["truncated"]:
        raise ValueError("the action space is too large to enumerate, so there is nothing to compare")
    ranked = rank_feasible_plans(evaluate_all_candidates(candidates["plans"], simulate, data))
    expected = objective(ranked[0]) if ranked else None
    rows = []
    for name in BACKENDS:
        row = {"scenario_id": data.get("scenario_id"), "backend": name, "status": "RUN",
               "enumeration": expected, "solver": None, "agrees": None,
               "enumeration_plan_id": ranked[0]["plan_id"] if ranked else None, "solver_plan_id": None}
        rows.append(row)
        try:
            backend = load_backend(name)
        except SolverUnavailable as error:
            row["status"] = f"UNAVAILABLE ({error})"
            continue
        found = backend.solve(data, candidates["menus"], 1, config["solver"]["time_limit_seconds"])
        plan = evaluate_candidate_plan(make_plan(found[0], data, "SOLVER"), simulate, data) if found else None
        actual = objective(plan) if plan and plan["feasibility"] == "FEASIBLE" else None
        row.update(solver=actual, solver_plan_id=plan["plan_id"] if plan else None,
                   agrees=expected == actual)
    return rows
