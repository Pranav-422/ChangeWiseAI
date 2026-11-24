"""What-if: the AI reads the question, the planner confirms, Member 2 calculates on an isolated copy."""
from member3.ai.what_if_parser import OK, parse_what_if_request
from member3.application.access_control import require
from member3.database.repositories import records
from member3.services import what_if_service

from ..core.database import acting, read, transaction
from ..core.errors import ApiError, not_found
from . import explanations, planning
from .engines import engines, get_provider


def parse(run_id, question, user):
    require(user, "RUN_WHAT_IF")
    return {"run_id": run_id, "question": question,
            **parse_what_if_request(question, planning.get(run_id)["dataset"], get_provider())}


def confirm(run_id, question, parameters, user):
    require(user, "RUN_WHAT_IF")
    run, (_, member2) = planning.get(run_id), engines()
    with acting(user.user_id):
        outcome = what_if_service.submit_scenario_to_optimizer(parameters, run, member2, user, question)
        if outcome["status"] != OK:
            raise ApiError(422, outcome["status"], outcome["message"])
        if not outcome["constrained"]:
            data = what_if_service.apply_parameters(run["dataset"], outcome["parameters"], member2)
            explanation = explanations.for_what_if(outcome, run, data)
            with transaction() as db:
                explanations.store(db, "WHAT_IF", outcome["parameters"]["scenario_id"], explanation, user.name)
    return get(outcome["parameters"]["scenario_id"])


def get(request_id):
    with read() as db:
        row = records.find(db, "what_if_requests", request_id=request_id)
    if row is None:
        raise not_found(f"Scenario {request_id}")
    run, outcome = planning.get(row["run_id"]), row["result"]
    result, base = outcome["result"], run["result"]
    plan = outcome["plan"]
    best = base["recommendations"][0] if base["recommendations"] else None
    known = {(e["type"], e["week"]) for e in run["context"]["exceptions"]}
    return {"scenario_id": request_id, "run_id": row["run_id"], "question": row["question"],
            "parameters": row["parameters"], "constrained": outcome["constrained"],
            "decision": result["decision"], "comparison": outcome["comparison"],
            "description": what_if_service.describe_comparison(outcome["comparison"]),
            "escalations": [] if outcome["constrained"] else result["escalations"],
            "base_plan": best, "alternative_plan": plan,
            "counts": result["counts"], "new_exceptions": [
                e for e in _exceptions(run, row["parameters"]) if (e["type"], e["week"]) not in known],
            "explanation": explanations.latest("WHAT_IF", request_id),
            "created_by": row["created_by"], "created_at": row["created_at"]}


def _exceptions(run, parameters):
    """Member 1's exceptions for the changed inputs, before any corrective action."""
    member1, member2 = engines()
    data = what_if_service.apply_parameters(run["dataset"], parameters, member2)
    return member1.exceptions(data, member1.baseline(data))


def list_for_run(run_id):
    with read() as db:
        return db.execute("SELECT request_id AS scenario_id, question, created_by, created_at FROM what_if_requests "
                          "WHERE run_id = ? ORDER BY rowid DESC LIMIT 20", [run_id]).fetchall()
