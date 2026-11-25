"""Engineering changes: list, overview, BOM impact, inventory, simulation, exceptions."""
from typing import Annotated

from fastapi import APIRouter

from ...schemas import api
from ...security.auth import Principal, needs
from ...services import change_service as service

router = APIRouter(tags=["changes"])
Viewer = Annotated[Principal, needs("VIEW")]


@router.get("/changes", response_model=list[api.ChangeRow])
def list_changes(user: Viewer):
    return service.list_changes()


@router.get("/changes/{change_id}/overview", response_model=api.Overview)
def overview(change_id: str, user: Viewer, scenario: str = "base"):
    return service.overview(change_id, scenario, user)


@router.get("/changes/{change_id}/bom-impact", response_model=api.BomImpact)
def bom_impact(change_id: str, user: Viewer, scenario: str = "base"):
    return service.bom_impact(change_id, scenario)


@router.get("/changes/{change_id}/inventory", response_model=api.Inventory)
def inventory(change_id: str, user: Viewer, scenario: str = "base"):
    return service.inventory(change_id, scenario)


@router.post("/changes/{change_id}/simulate", response_model=api.Inventory)
def simulate(change_id: str, user: Annotated[Principal, needs("RUN_SIMULATION")], scenario: str = "base"):
    return service.simulate(change_id, scenario, user)


@router.get("/changes/{change_id}/exceptions", response_model=api.ExceptionList)
def exceptions(change_id: str, user: Viewer, scenario: str = "base"):
    return service.exceptions(change_id, scenario)


@router.patch("/exceptions/{exception_id}", response_model=api.ExceptionItem)
def update_exception(exception_id: str, body: api.ExceptionUpdate, user: Annotated[Principal, needs("UPDATE_EXCEPTION")]):
    return service.update_exception(body.change_id, body.scenario, exception_id, body.status, user)
