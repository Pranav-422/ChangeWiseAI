"""Role checks, enforced in the services. The demo has no login: a role is chosen, not proven."""
from typing import NamedTuple

from ..settings import load_settings

ROLES = ("Planner", "Engineering", "Purchasing", "Quality", "Viewer")


class User(NamedTuple):
    name: str
    role: str


class NotAllowed(PermissionError):
    pass


def allowed(user, permission):
    return user.role in load_settings()["permissions"][permission]


def require(user, permission):
    if not user.name.strip():
        raise NotAllowed("A user name is required.")
    if not allowed(user, permission):
        raise NotAllowed(f"{user.role} may not {permission.replace('_', ' ').lower()}.")
