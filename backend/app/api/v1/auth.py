from typing import Annotated

from fastapi import APIRouter, Depends

from ...schemas import api
from ...security.auth import Principal, current_user, needs
from ...security.permissions import granted, matrix
from ...services import users

router = APIRouter(tags=["auth"])
User = Annotated[Principal, Depends(current_user)]


@router.get("/auth/me", response_model=api.Me)
def me(user: User):
    return {"user_id": user.user_id, "email": user.email, "name": user.name, "role": user.stored_role,
            "permissions": granted(user.role)}


@router.patch("/auth/me", status_code=204)
def rename(body: api.ProfileUpdate, user: User):
    users.update_own_name(body.full_name, user)


@router.get("/auth/permissions", response_model=api.Permissions)
def permissions(user: User):
    return {"role": user.stored_role, "granted": granted(user.role), "matrix": matrix()}


@router.get("/admin/users", response_model=list[api.UserRow])
def list_users(user: Annotated[Principal, needs("MANAGE_USERS")]):
    return users.list_users(user)


@router.patch("/admin/users/{user_id}", response_model=api.UserRow)
def update_user(user_id: str, body: api.UserUpdate, user: Annotated[Principal, needs("MANAGE_USERS")]):
    return users.update(user_id, body.role, body.is_active, user)
