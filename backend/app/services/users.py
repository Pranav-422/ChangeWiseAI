"""Access administration. A role changes only here, by an administrator, and the change is audited."""
from member3.services import audit_service

from ..core.database import acting, read, transaction
from ..core.errors import ApiError, not_found
from ..security.permissions import require

_COLUMNS = "user_id, email, full_name, role, is_active, created_at, updated_at"


def list_users(user):
    require(user, "MANAGE_USERS")
    with read() as db:
        return db.execute(f"SELECT {_COLUMNS} FROM user_profiles WHERE email <> '' ORDER BY created_at, email").fetchall()


def update(user_id, role, is_active, user):
    require(user, "MANAGE_USERS")
    with acting(user.user_id), transaction() as db:
        # no e-mail: a guest session, which cannot be given a role
        before = db.execute(f"SELECT {_COLUMNS} FROM user_profiles WHERE user_id::text = ? AND email <> ''",
                            [user_id]).fetchone()
        if before is None:
            raise not_found("User")
        after = {"role": role or before["role"], "is_active": before["is_active"] if is_active is None else is_active}
        if user_id == user.user_id and (after["role"] != "ADMIN" or not after["is_active"]):
            raise ApiError(409, "LAST_ADMIN", "An administrator cannot remove their own access.")
        db.execute("UPDATE user_profiles SET role = ?, is_active = ?, updated_at = now() WHERE user_id::text = ?",
                   [after["role"], after["is_active"], user_id])
        audit_service.append(db, "ACCESS_CHANGED", user_id, user, {
            "from": {k: before[k] for k in after}, "to": after})
        return db.execute(f"SELECT {_COLUMNS} FROM user_profiles WHERE user_id::text = ?", [user_id]).fetchone()


def update_own_name(full_name, user):
    with acting(user.user_id), transaction() as db:
        db.execute("UPDATE user_profiles SET full_name = ?, updated_at = now() WHERE user_id::text = ?", [full_name, user.user_id])
