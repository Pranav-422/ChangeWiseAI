"""Planning runs, what-if scenarios and explanations."""
from typing import Annotated

from fastapi import APIRouter, Query, Request

from ...schemas import api
from ...security.auth import Principal, needs
from ...services import explanations, planning, what_if

router = APIRouter(tags=["planning"])
Viewer = Annotated[Principal, needs("VIEW")]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.post("/planning/optimize", response_model=api.Run)
def optimize(body: api.OptimizeRequest, request: Request, user: Annotated[Principal, needs("RUN_PLANNING")]):
    run_id = planning.optimize(body.review_id, user)
    request.state.run_id = run_id
    return planning.summary(run_id)


@router.get("/planning/runs", response_model=api.RunList)
def runs(user: Viewer, limit: Limit = 25, offset: Offset = 0):
    return planning.list_runs(limit, offset)


@router.get("/planning/runs/{run_id}", response_model=api.Run)
def run(run_id: str, user: Viewer):
    return planning.summary(run_id)


@router.get("/planning/runs/{run_id}/plans", response_model=api.RankedPlans)
def plans(run_id: str, user: Viewer, limit: Limit = 25, offset: Offset = 0):
    return planning.ranked_plans(run_id, limit, offset)


@router.get("/planning/runs/{run_id}/rejected-plans", response_model=api.RejectedPlans)
def rejected(run_id: str, user: Viewer):
    return planning.rejected_plans(run_id)


@router.get("/planning/runs/{run_id}/robustness", response_model=list[api.PlanRobustness])
def robustness(run_id: str, user: Viewer):
    return planning.robustness(run_id)


@router.get("/planning/runs/{run_id}/comparison", response_model=list[api.Configuration])
def comparison(run_id: str, user: Viewer):
    return planning.comparison(run_id)


@router.get("/planning/runs/{run_id}/menus", response_model=list[api.Menu])
def menus(run_id: str, user: Annotated[Principal, needs("DECIDE_PLAN")]):
    return planning.menus(run_id)


@router.get("/planning/runs/{run_id}/what-if", response_model=list[api.WhatIfRow])
def scenarios(run_id: str, user: Viewer):
    return what_if.list_for_run(run_id)


@router.post("/planning/what-if/parse", response_model=api.WhatIfParsed)
def parse(body: api.WhatIfParse, user: Annotated[Principal, needs("RUN_WHAT_IF")]):
    return what_if.parse(body.run_id, body.question, user)


@router.post("/planning/what-if/confirm", response_model=api.WhatIfResult)
def confirm(body: api.WhatIfConfirm, user: Annotated[Principal, needs("RUN_WHAT_IF")]):
    return what_if.confirm(body.run_id, body.question, body.parameters.model_dump(), user)


@router.get("/planning/what-if/{scenario_id}", response_model=api.WhatIfResult)
def scenario(scenario_id: str, user: Viewer):
    return what_if.get(scenario_id)


@router.post("/explanations/generate", response_model=api.Explanation)
def generate(body: api.ExplanationRequest, user: Annotated[Principal, needs("RUN_PLANNING")]):
    return explanations.generate(planning.get(body.run_id), user)


@router.get("/planning/runs/{run_id}/explanation", response_model=api.Explanation | None)
def run_explanation(run_id: str, user: Viewer):
    planning.get(run_id)
    return explanations.latest("RUN", run_id)


@router.get("/explanations/{explanation_id}", response_model=api.Explanation)
def explanation(explanation_id: str, user: Viewer):
    return explanations.get(explanation_id)
