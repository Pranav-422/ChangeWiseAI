"""Shared test data. Plans are built with the engine, never hand-typed results."""
from copy import deepcopy

from member2.engine.action_generator import make_plan
from member2.engine.config import load_config
from member2.engine.planner import evaluate_candidate_plan
from member2.reference.scenarios import SCENARIOS, base, find_po
from member2.reference.simulator import simulate_inventory

CONFIG = load_config()
REDUCE_200 = {"action": "REDUCE_REV_B_PO", "po_id": "PO-001", "quantity": 200}
REDUCE_50 = {"action": "REDUCE_REV_B_PO", "po_id": "PO-001", "quantity": 50}
CANCEL = {"action": "CANCEL_REV_B_PO", "po_id": "PO-001"}
EXPEDITE = {"action": "EXPEDITE_REV_C_PO", "po_id": "PO-003", "weeks": 1}
TO_W5 = {"action": "SHIFT_EFFECTIVE_WEEK", "from_week": 6, "to_week": 5}
RUN_OUT = {"action": "CONTINUE_REV_B", "through_week": 7}


def config(**sections):
    """Config copy with keys inside named sections overridden."""
    copy = deepcopy(CONFIG)
    for section, values in sections.items():
        copy[section].update(values)
    return copy


def evaluate(actions, data=None):
    data = data or base()
    return evaluate_candidate_plan(make_plan(actions, data), simulate_inventory, data)


def codes(record):
    return {r["code"] for r in record["rejection_reasons"]}


def plan(plan_id, shortage, cost, actions=()):
    """Minimal evaluated plan for ranking and tie tests."""
    return {"plan_id": plan_id, "shortage_units": shortage, "secondary_cost": cost,
            "actions": list(actions), "feasibility": "FEASIBLE"}
