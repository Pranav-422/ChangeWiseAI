"""Approvals and the action tracker."""
from typing import Annotated, Optional

from fastapi import APIRouter

from ...schemas import api
from ...security.auth import Principal, needs
from ...services import action_service, approvals

router = APIRouter(tags=["workflow"])
Viewer = Annotated[Principal, needs("VIEW")]
Planner = Annotated[Principal, needs("DECIDE_PLAN")]


def _plain(actions):
    return None if actions is None else [a.model_dump(exclude_none=True) for a in actions]


@router.get("/approvals", response_model=api.ApprovalList)
def listing(user: Viewer):
    return approvals.listing()


@router.get("/approvals/{approval_id}", response_model=api.Approval)
def approval(approval_id: str, user: Viewer):
    return approvals.get(approval_id)


@router.post("/approvals/{run_id}/modification", response_model=api.EvaluatedPlan)
def modification(run_id: str, body: api.Modification, user: Planner):
    """The engine's verdict on a planner-modified plan. Nothing is decided."""
    return approvals.evaluate(run_id, _plain(body.actions), user)


@router.post("/approvals/{run_id}/decision", response_model=api.Approval, status_code=201)
def decision(run_id: str, body: api.DecisionRequest, user: Planner):
    """One final decision per run. A repeated request gets 409 and changes nothing."""
    return approvals.decide(run_id, body.decision, body.comment, body.plan_id, _plain(body.modified_actions), user)


@router.post("/approvals/{approval_id}/close", response_model=api.Approval)
def close(approval_id: str, user: Annotated[Principal, needs("CLOSE_CHANGE")]):
    return approvals.close(approval_id, user)


@router.get("/actions", response_model=list[api.ActionItem])
def actions(user: Viewer, run_id: Optional[str] = None):
    return action_service.list_items(run_id)


@router.get("/actions/{action_id}", response_model=api.ActionItem)
def action(action_id: str, user: Viewer):
    return action_service.get(action_id)


@router.patch("/actions/{action_id}", response_model=api.ActionItem)
def update_action(action_id: str, body: api.ActionUpdate, user: Annotated[Principal, needs("UPDATE_ACTION")]):
    return action_service.update(action_id, body.status, body.assignee, user)


@router.get("/actions/{action_id}/history", response_model=list[api.StatusChange])
def action_history(action_id: str, user: Viewer):
    return action_service.history(action_id)
