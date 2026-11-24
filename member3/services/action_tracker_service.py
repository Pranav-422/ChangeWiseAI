"""Approved actions with an owner role and a status: OPEN -> IN_PROGRESS -> DONE."""
from member2.engine.recommendation import describe_action

from ..application.access_control import NotAllowed, require
from ..database.connection import transaction
from ..database.repositories import records
from ..settings import load_settings
from . import audit_service

NEXT = {"OPEN": "IN_PROGRESS", "IN_PROGRESS": "DONE", "DONE": None}


class InvalidTransition(ValueError):
    pass


def create_items(db, approval_id, run_id, plan, user):
    for action in plan["actions"]:
        action_id, stamp = records.new_id("ACT"), records.now()
        owner = load_settings()["owners"][action["action"]]
        records.insert(db, "action_items", action_id=action_id, approval_id=approval_id, run_id=run_id,
                       summary=describe_action(action), action=action, owner_role=owner, status="OPEN",
                       created_at=stamp, updated_at=stamp)
        audit_service.append(db, "ACTION_CREATED", action_id, user, {
            "run_id": run_id, "summary": describe_action(action), "owner_role": owner})


def list_items(run_id=None):
    with transaction() as db:
        return records.select(db, "action_items", **({"run_id": run_id} if run_id else {}))


def can_update(item, user):
    return user.role in (item["owner_role"], "Planner")


def advance(action_id, user):
    """Move one step forward. The owner role or the planner may do it."""
    if not user.name.strip():
        raise NotAllowed("A user name is required.")
    with transaction() as db:
        item = records.get(db, "action_items", action_id=action_id)
        if not can_update(item, user):
            raise NotAllowed(f"{user.role} does not own this action.")
        status = NEXT[item["status"]]
        if status is None:
            raise InvalidTransition("The action is already done.")
        records.update(db, "action_items", "action_id", action_id, status=status, updated_at=records.now())
        audit_service.append(db, "ACTION_STATUS", action_id, user, {"from": item["status"], "to": status})
    return status


def close_change(run_id, user):
    require(user, "CLOSE_CHANGE")
    with transaction() as db:
        approval = records.get(db, "approvals", run_id=run_id, decision="APPROVED")
        if approval["closed_at"]:
            raise InvalidTransition("The change is already closed.")
        if any(i["status"] != "DONE" for i in records.select(db, "action_items", run_id=run_id)):
            raise InvalidTransition("Every action must be done before closing.")
        records.update(db, "approvals", "approval_id", approval["approval_id"], closed_at=records.now())
        audit_service.append(db, "CHANGE_CLOSED", run_id, user)
