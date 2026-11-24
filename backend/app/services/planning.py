"""Planning runs and their views. Member 2 decides and ranks; this module stores and presents."""
import json
from functools import lru_cache

from member2.engine.constraints import find
from member2.engine.recommendation import describe_action, describe_plan
from member3.application.access_control import require
from member3.database.repositories import records
from member3.services import planning_service

from ..core.database import acting, read
from ..core.errors import not_found
from ..integrations.member1_postgres import change_of
from . import explanations
from .engines import engines, get_provider

RULES = (
    ("SUPPLIER_QUALIFICATION", "No purchases from blocked or unqualified suppliers"),
    ("REV_B_USE_UP", "No Rev B use after the use-up end week"),
    ("SUPPLIER_LEAD_TIME", "No arrival earlier than the feasible supplier lead time"),
    ("PO_WINDOW", "Order changes only inside their permitted windows and limits"),
    ("PURCHASING_BLOCK", "No new Rev B order after ECN approval"),
    ("PURCHASING_GROUP", "Only authorized purchasing groups may act"),
    ("INPUT_VALIDITY", "Invalid or conflicting data stops planning"),
)


@lru_cache(maxsize=4)  # a run is about 10 MB in memory and the free instance has 512 MB
def _load(run_id):
    return planning_service.get_run(run_id)


def get(run_id):
    """A stored run never changes (the database refuses it), so it is safe to keep in memory."""
    try:
        return _load(run_id)
    except LookupError as error:
        raise not_found(f"Planning run {run_id}") from error


def due_week(action, dataset):
    """The last week the order may still be changed, or the week a changeover action names."""
    if "po_id" in action:
        po = find(dataset["purchase_orders"], "po_id", action["po_id"])
        key = "cancel_deadline_week" if action["action"] in ("CANCEL_REV_B_PO", "ALTERNATE_SUPPLIER") else "change_deadline_week"
        return (po or {}).get(key) or None
    return action.get("to_week") or action.get("through_week")


def store_plan(db, run, plan, source, near_tie=False):
    """One proposed plan and its actions in core.candidate_plans / core.plan_actions."""
    robustness = plan.get("robustness") or {}
    db.execute("INSERT INTO core.candidate_plans (optimization_run_id, plan_id, change_id, scenario_id, source, effective_week, "
               "feasibility, shortage_units, excess_value, action_cost, secondary_cost, plan_rank, near_tie_group, "
               "robustness_numerator, robustness_denominator, rejection_reasons_json, created_at) "
               "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING",
               [run["run_id"], plan["plan_id"], change_of(run["scenario_id"]), run["scenario_id"], source,
                plan.get("effective_week"), plan["feasibility"], plan.get("shortage_units"), plan.get("excess_value"),
                plan.get("action_cost"), plan.get("secondary_cost"), plan.get("rank"),
                run["run_id"] if near_tie else None, robustness.get("numerator"), robustness.get("denominator"),
                json.dumps(plan.get("rejection_reasons", [])), records.now()])
    db.executemany(
        "INSERT INTO core.plan_actions (action_id, optimization_run_id, plan_id, action_type, po_id, supplier_id, quantity, "
        "weeks, target_week) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING",
        [(plan_action_id(run["run_id"], plan["plan_id"], n), run["run_id"], plan["plan_id"], a["action"],
          _known(run, "purchase_orders", "po_id", a), _known(run, "suppliers", "supplier_id", a), a.get("quantity"),
          a.get("weeks"), a.get("to_week") or a.get("through_week")) for n, a in enumerate(plan["actions"], 1)])


def _known(run, table, key, action):
    """Rejected probe plans may name a record that does not exist; the reason is in the rejection."""
    return action.get(key) if find(run["dataset"][table], key, action.get(key)) else None


def plan_action_id(run_id, plan_id, position):
    return f"{run_id}:{plan_id}:A{position}"


def _store(db, run):
    result = run["result"]
    tied = {t[k] for t in result["near_ties"] for k in ("plan_a", "plan_b")}
    for plan in result["recommendations"]:
        store_plan(db, run, plan, "ENGINE", plan["plan_id"] in tied)
    for plan in result["rejected_plans"]:
        store_plan(db, run, plan, plan["source"])
    explanations.store(db, "RUN", run["run_id"], run["explanation"], run["run_id"])


def optimize(review_id, user):
    """Not repeated on a double click: an undecided run on unchanged inputs and settings is returned as it is."""
    require(user, "RUN_PLANNING")
    member1, member2 = engines()
    with read() as db:
        latest = db.execute("SELECT r.run_id, a.approval_id FROM planning_runs r LEFT JOIN approvals a USING (run_id) "
                            "WHERE r.review_id = ? ORDER BY r.rowid DESC LIMIT 1", [review_id]).fetchone()
    if latest and not latest["approval_id"]:
        run = get(latest["run_id"])
        if run["config"] == member2.config and not planning_service.is_stale(run, member1, member2):
            return run["run_id"]
    with acting(user.user_id):
        try:
            return planning_service.run_planning(review_id, member1, member2, user, get_provider(), _store)
        except LookupError as error:
            raise not_found(f"Review {review_id}") from error


def _hard_rules(result):
    """Per rule: how many rejected plans broke it. The recommended plan broke none, or it would not be feasible."""
    broken = {}
    for plan in result["rejected_plans"]:
        for rule in {r["rule"] for r in plan["rejection_reasons"]}:
            broken[rule] = broken.get(rule, 0) + 1
    if result["decision"] == "INVALID_DATA":
        broken["INPUT_VALIDITY"] = len(result["escalations"][0]["evidence"])
    known = dict(RULES)
    return [{"rule": r, "title": known.get(r, r.replace("_", " ").capitalize()), "violations": broken.get(r, 0)}
            for r in dict.fromkeys([*known, *broken])]


def _approval(run_id):
    with read() as db:
        row = db.execute("SELECT approval_id, decision, modified, comment, user_name, role, created_at, closed_at, "
                         "plan->>'plan_id' AS plan_id, plan->>'summary' AS plan_summary FROM approvals WHERE run_id = ?",
                         [run_id]).fetchone()
    return row


def is_stale(run):
    return planning_service.is_stale(run, *engines())


def is_newest(run):
    with read() as db:
        return db.execute("SELECT run_id FROM planning_runs WHERE scenario_id = ? ORDER BY rowid DESC LIMIT 1",
                          [run["scenario_id"]]).fetchone()["run_id"] == run["run_id"]


def summary(run_id):
    """The run without its snapshots and full ranked list."""
    run = get(run_id)
    result = run["result"]
    return {"run_id": run_id, "review_id": run["review_id"], "change_id": change_of(run["scenario_id"]),
            "scenario_id": run["scenario_id"].partition("@")[0], "input_hash": run["input_hash"],
            "config_hash": result["config_hash"], "engine_version": result["engine_version"],
            "simulator": result["simulator"], "method": result["method"], "decision": result["decision"],
            "requires_planner_review": result["requires_planner_review"],
            "recommended_plan_id": result["recommended_plan_id"], "counts": result["counts"],
            "recommendations": result["recommendations"], "near_ties": result["near_ties"],
            "escalations": result["escalations"], "effective_week_comparison": result["effective_week_comparison"],
            "hard_rules": _hard_rules(result), "computation_seconds": result["computation_seconds"],
            "created_by": run["created_by"], "created_at": run["created_at"],
            "stale": is_stale(run), "newest": is_newest(run), "approval": _approval(run_id),
            "baseline_exceptions": run["context"]["exceptions"]}


def list_runs(limit, offset):
    with read() as db:
        rows = db.execute("SELECT r.run_id, r.scenario_id, r.decision, r.created_by, r.created_at, a.decision AS approval "
                          "FROM planning_runs r LEFT JOIN approvals a USING (run_id) ORDER BY r.rowid DESC LIMIT ? OFFSET ?",
                          [limit, offset]).fetchall()
        total = db.execute("SELECT count(*) AS n FROM planning_runs").fetchone()["n"]
    return {"items": [{**r, "change_id": change_of(r["scenario_id"]), "scenario_id": r["scenario_id"].partition("@")[0]}
                      for r in rows], "total": total}


def ranked_plans(run_id, limit, offset):
    plans = get(run_id)["result"]["ranked_plans"]
    return {"items": [{**p, "summary": describe_plan(p)} for p in plans[offset:offset + limit]], "total": len(plans)}


def rejected_plans(run_id):
    plans = get(run_id)["result"]["rejected_plans"]
    return {"items": [{**p, "summary": describe_plan(p)} for p in plans], "total": len(plans)}


def robustness(run_id):
    return [{"plan_id": p["plan_id"], "rank": p["rank"], "summary": p["summary"], **p["robustness"]}
            for p in get(run_id)["result"]["recommendations"]]


def comparison(run_id):
    """Baseline A, Baseline B and the recommended plan on the run's own snapshot."""
    run = get(run_id)
    return engines()[1].compare(run["dataset"], run["result"])


def menus(run_id):
    """Eligible options per decision, for a planner's modified plan."""
    options = engines()[1].menus(get(run_id)["dataset"])
    return [{"name": name, "options": [{"label": "; ".join(describe_action(a) for a in o) or "Leave as is", "actions": o}
                                       for o in choices]} for name, choices in options.items() if choices]
