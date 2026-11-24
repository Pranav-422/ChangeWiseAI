"""Planner decisions. Decisions are recorded, never executed: no ERP or PLM record is touched."""
import sqlite3

from ..application.access_control import require
from ..database.connection import transaction
from ..database.repositories import records
from . import action_tracker_service, audit_service
from .planning_service import is_stale


class DecisionRefused(ValueError):
    pass


def get_decision(run_id):
    with transaction() as db:
        return records.find(db, "approvals", run_id=run_id)


def pending_runs():
    """Newest run of each scenario that has a plan and no decision yet."""
    with transaction() as db:
        newest = {r["scenario_id"]: r for r in records.select(
            db, "planning_runs", columns="run_id, scenario_id, decision, created_at")}
        decided = {a["run_id"] for a in records.select(db, "approvals", columns="run_id")}
    return [r for r in newest.values() if r["run_id"] not in decided
            and r["decision"] in ("RECOMMENDED", "ESCALATED")]


def evaluate_modification(run_id, actions, member2, user):
    """Member 2's verdict on a planner-modified plan. Recorded, but decides nothing."""
    require(user, "DECIDE_PLAN")
    with transaction() as db:
        run = records.get(db, "planning_runs", run_id=run_id)
    plan = member2.evaluate(actions, run["dataset"])
    with transaction() as db:
        audit_service.append(db, "PLAN_MODIFIED", run_id, user, {
            "plan_id": plan["plan_id"], "actions": actions, "feasibility": plan["feasibility"],
            "rejection_reasons": plan["rejection_reasons"]})
    return plan


def _comment_needed(run, plan_id, modified):
    if modified:
        return "a modified plan"
    if plan_id != run["result"]["recommended_plan_id"]:
        return "a plan other than the recommended one"
    if run["result"]["requires_planner_review"]:
        return "an escalated case"
    return None


def decide(run_id, decision, user, member1, member2, comment="", plan_id=None, modified_actions=None):
    """APPROVED needs a plan_id from the top plans or modified_actions; REJECTED needs a comment."""
    require(user, "DECIDE_PLAN")
    comment = comment.strip()
    with transaction() as db:
        run = records.get(db, "planning_runs", run_id=run_id)
        newest = records.find(db, "planning_runs", scenario_id=run["scenario_id"])
    if decision not in ("APPROVED", "REJECTED"):
        raise DecisionRefused(f"Unknown decision {decision}.")
    plan = None
    if decision == "REJECTED":
        if not comment:
            raise DecisionRefused("A rejection needs a comment.")
    else:
        if newest["run_id"] != run_id:
            raise DecisionRefused("A newer planning run exists; decide on that one.")
        if is_stale(run, member1, member2):
            raise DecisionRefused("The planning data changed after this run; run planning again.")
        if modified_actions is not None:
            plan = member2.evaluate(modified_actions, run["dataset"])
            if plan["feasibility"] != "FEASIBLE":
                raise DecisionRefused("The modified plan breaks a hard rule: "
                                      + plan["rejection_reasons"][0]["description"])
            plan_id = plan["plan_id"]
        else:
            plan = next((p for p in run["result"]["recommendations"] if p["plan_id"] == plan_id), None)
            if plan is None:
                raise DecisionRefused("Only a recommended or a planner-modified plan can be approved.")
        needed = _comment_needed(run, plan_id, modified_actions is not None)
        if needed and not comment:
            raise DecisionRefused(f"Approving {needed} needs a comment.")
    approval_id = records.new_id("APR")
    try:
        with transaction() as db:
            records.insert(db, "approvals", approval_id=approval_id, run_id=run_id, decision=decision,
                           modified=int(modified_actions is not None), plan=plan, comment=comment,
                           user_name=user.name, role=user.role, created_at=records.now())
            audit_service.append(db, f"PLAN_{decision}", run_id, user, {
                "approval_id": approval_id, "plan_id": plan and plan["plan_id"],
                "modified": modified_actions is not None, "comment": comment})
            if plan:
                action_tracker_service.create_items(db, approval_id, run_id, plan, user)
    except sqlite3.IntegrityError as error:
        raise DecisionRefused("This run already has a final decision.") from error
    return approval_id
