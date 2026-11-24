"""Planning runs: confirmed ECN -> Member 1 data -> Member 2 engine -> explanation -> stored run."""
from ..ai.claim_verifier import build_verified_facts
from ..ai.explanation_generator import generate_explanation
from ..application.access_control import require
from ..database.connection import transaction
from ..database.repositories import records
from ..settings import load_settings
from . import audit_service
from .ecn_service import NotReady


def _context(member1, dataset):
    baseline = member1.baseline(dataset)
    return {"baseline": baseline, "exceptions": member1.exceptions(dataset, baseline),
            "bom": member1.bom_impact(dataset["engineering_change"]["old_material_id"])}


def facts_for(run, approved=False):
    return build_verified_facts({"run_id": run["run_id"], "dataset": run["dataset"], "result": run["result"],
                                 "owners": load_settings()["owners"], "approved": approved, **run["context"]})


def run_planning(review_id, member1, member2, user, provider=None):
    require(user, "RUN_PLANNING")
    with transaction() as db:
        review = records.get(db, "ecn_reviews", review_id=review_id)
    if review["status"] != "CONFIRMED":
        raise NotReady("The ECN must be confirmed before planning.")
    dataset = member1.load_dataset(review["scenario_id"])
    stale = member1.validate_ecn(review["fields"], dataset)
    if stale:
        raise NotReady("Member 1's records changed after confirmation: " + stale[0]["message"])
    result = member2.optimize(dataset)
    run = {"run_id": records.new_id("RUN"), "review_id": review_id, "scenario_id": review["scenario_id"],
           "input_hash": result["input_hash"], "decision": result["decision"], "dataset": dataset,
           "config": member2.config, "result": result, "context": _context(member1, dataset)}
    run["explanation"] = generate_explanation(facts_for(run), provider)
    with transaction() as db:
        records.insert(db, "planning_runs", **run, created_by=user.name, created_at=records.now())
        audit_service.append(db, "PLAN_GENERATED", run["run_id"], user, {
            "review_id": review_id, "input_hash": run["input_hash"], "config_hash": result["config_hash"],
            "engine_version": result["engine_version"], "simulator": result["simulator"],
            "decision": run["decision"], "recommended_plan_id": result["recommended_plan_id"],
            "escalations": [e["code"] for e in result["escalations"]],
            "explanation": run["explanation"]["label"],
            "verification": run["explanation"]["verification"]})
    return run["run_id"]


def get_run(run_id):
    with transaction() as db:
        return records.get(db, "planning_runs", run_id=run_id)


def latest_run(scenario_id):
    with transaction() as db:
        return records.find(db, "planning_runs", scenario_id=scenario_id)


def list_runs():
    with transaction() as db:
        return records.select(db, "planning_runs", order="rowid DESC",
                              columns="run_id, scenario_id, decision, created_by, created_at")


def is_stale(run, member1, member2):
    """Member 1's data has changed since the run was made."""
    return member2.hash(member1.load_dataset(run["scenario_id"])) != run["input_hash"]


STAGES = ("ECN received", "Validated", "Plan approved", "Actions done", "Closed")


def change_stage(scenario_id):
    """Number of completed lifecycle stages for the scenario's newest ECN (0 to 5)."""
    with transaction() as db:
        review = records.find(db, "ecn_reviews", scenario_id=scenario_id)
        if not review:
            return 0
        if review["status"] != "CONFIRMED":
            return 1
        run = records.find(db, "planning_runs", review_id=review["review_id"])
        approval = records.find(db, "approvals", run_id=run["run_id"], decision="APPROVED") if run else None
        if not approval:
            return 2
        items = records.select(db, "action_items", approval_id=approval["approval_id"])
        if any(i["status"] != "DONE" for i in items):
            return 3
        return 5 if approval["closed_at"] else 4
