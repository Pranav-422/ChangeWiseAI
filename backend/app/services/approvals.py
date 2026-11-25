"""Planner decisions. Member 3 owns the rules; this module links an approved plan to its proposed actions."""
from member3.services import action_tracker_service, approval_service

from ..core.database import acting, read
from ..core.errors import not_found
from ..integrations.member1_postgres import change_of
from . import planning
from .engines import engines


def listing():
    pending = []
    for row in approval_service.pending_runs():
        result = planning.get(row["run_id"])["result"]
        best = result["recommendations"][0]
        pending.append({**row, "change_id": change_of(row["scenario_id"]), "scenario_id": row["scenario_id"].partition("@")[0],
                        "plan_id": best["plan_id"], "plan_summary": best["summary"],
                        "shortage_units": best["shortage_units"], "secondary_cost": best["secondary_cost"],
                        "robustness": best["robustness"]["display"],
                        "escalations": [e["code"] for e in result["escalations"]]})
    with read() as db:
        decided = db.execute(_SELECT + "ORDER BY a.rowid DESC LIMIT 50").fetchall()
    return {"pending": pending, "decided": [_view(r) for r in decided]}


_SELECT = ("SELECT a.approval_id, a.run_id, a.decision, a.modified, a.comment, a.user_name, a.role, a.created_at, a.closed_at, "
           "a.plan->>'plan_id' AS plan_id, a.plan->>'summary' AS plan_summary, r.scenario_id "
           "FROM approvals a JOIN planning_runs r USING (run_id) ")


def _view(row):
    return {**row, "change_id": change_of(row["scenario_id"]), "scenario_id": row["scenario_id"].partition("@")[0]}


def get(approval_id):
    with read() as db:
        row = db.execute(_SELECT + "WHERE a.approval_id = ?", [approval_id]).fetchone()
    if row is None:
        raise not_found(f"Approval {approval_id}")
    return _view(row)


def evaluate(run_id, actions, user):
    """Member 2's verdict on a planner-modified plan. Nothing is decided."""
    planning.get(run_id)
    with acting(user.user_id):
        return approval_service.evaluate_modification(run_id, actions, engines()[1], user)


def decide(run_id, decision, comment, plan_id, modified_actions, user):
    run = planning.get(run_id)

    def link(db, approval_id, plan):
        """Same transaction as the decision: approved action -> proposed action -> plan -> run."""
        if modified_actions is not None:
            planning.store_plan(db, run, plan, "PLANNER")
        items = db.execute("SELECT action_id FROM action_items WHERE approval_id = ? ORDER BY rowid", [approval_id]).fetchall()
        for position, (item, action) in enumerate(zip(items, plan["actions"], strict=True), 1):
            db.execute("UPDATE action_items SET plan_action_id = ?, due_week = ? WHERE action_id = ?",
                       [planning.plan_action_id(run_id, plan["plan_id"], position),
                        planning.due_week(action, run["dataset"]), item["action_id"]])

    with acting(user.user_id):
        approval_id = approval_service.decide(run_id, decision, user, *engines(), comment, plan_id, modified_actions, link)
    return get(approval_id)


def close(approval_id, user):
    run_id = get(approval_id)["run_id"]
    with acting(user.user_id):
        try:
            action_tracker_service.close_change(run_id, user)
        except LookupError as error:
            raise action_tracker_service.InvalidTransition("Only an approved change can be closed.") from error
    return get(approval_id)
