from typing import Annotated, Optional

from fastapi import APIRouter, Query

from ...schemas import api
from ...security.auth import Principal, needs
from ...services import audit_queries as service

router = APIRouter(prefix="/audit", tags=["audit"])
Reader = Annotated[Principal, needs("VIEW_AUDIT")]


@router.get("", response_model=api.AuditPage)
def page(user: Reader, limit: Annotated[int, Query(ge=1, le=100)] = 50, offset: Annotated[int, Query(ge=0)] = 0,
         event_type: Optional[str] = None, entity_id: Optional[str] = None,
         search: Annotated[Optional[str], Query(max_length=100)] = None):
    return service.page(limit, offset, event_type, entity_id, search)


@router.get("/chain", response_model=api.Chain)
def chain(user: Reader):
    return service.chain()


@router.get("/replay", response_model=list[api.Replay])
def replays(user: Reader):
    return service.replays()


@router.post("/replay", response_model=api.Replay)
def replay(body: api.ReplayRequest, user: Annotated[Principal, needs("REPLAY_RUN")]):
    return service.replay(body.run_id, user)


@router.get("/replay/{replay_id}", response_model=api.Replay)
def get_replay(replay_id: str, user: Reader):
    return service.get_replay(replay_id)


@router.get("/{event_id}", response_model=api.AuditEvent)
def event(event_id: int, user: Reader):
    return service.get(event_id)
