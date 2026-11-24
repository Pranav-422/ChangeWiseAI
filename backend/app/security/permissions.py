"""Roles and permissions. Member 3's matrix (member3/config/settings.yaml) stays the source for its five actions."""
from member3.application.access_control import NotAllowed
from member3.settings import load_settings

# Stored role -> the role name Member 3's rules use.
ROLE_NAMES = {"ADMIN": "Admin", "ENGINEERING": "Engineering", "PURCHASING": "Purchasing",
              "PRODUCTION_PLANNER": "Planner", "QUALITY": "Quality", "VIEWER": "Viewer"}

_EVERYONE = list(ROLE_NAMES.values())
_ENGINEERING_READERS = ["Admin", "Engineering", "Planner", "Quality"]
_BACKEND = {
    "VIEW": _EVERYONE,
    "VIEW_DOCUMENTS": _ENGINEERING_READERS,
    "VIEW_AUDIT": _ENGINEERING_READERS,
    "RUN_SIMULATION": ["Planner", "Engineering"],
    "UPDATE_EXCEPTION": ["Planner", "Engineering", "Purchasing", "Quality"],
    "UPDATE_ACTION": ["Planner", "Engineering", "Purchasing", "Quality"],  # and only for an action of one's own role
    "REPLAY_RUN": ["Admin", "Planner"],
    "MANAGE_USERS": ["Admin"],
}


def matrix():
    return {**load_settings()["permissions"], **_BACKEND}


def granted(role):
    return sorted(p for p, roles in matrix().items() if role in roles)


def require(user, permission):
    if user.role not in matrix()[permission]:
        raise NotAllowed(f"{user.role} may not {permission.replace('_', ' ').lower()}.")
