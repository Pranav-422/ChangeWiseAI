"""Execution tasks of approved plans. Proposed actions (core.plan_actions) are never shown as tasks."""
from member3.database.repositories import records
from member3.services import action_tracker_service, audit_service

from ..core.database import acting, read, transaction
from ..core.errors import not_found
from ..security.permissions import require

_SELECT = ("SELECT i.action_id, i.approval_id, i.run_id, i.summary, i.action, i.owner_role, i.status, i.created_at, i.updated_at, "
           "i.plan_action_id, i.assignee, i.due_week, a.plan->>'plan_id' AS plan_id, a.closed_at, r.scenario_id "
           "FROM action_items i JOIN approvals a USING (approval_id) JOIN planning_runs r ON r.run_id = i.run_id ")


def _view(row):
    return {**records._decode(row), "scenario_id": row["scenario_id"].partition("@")[0],
            "next_status": action_tracker_service.NEXT[row["status"]]}


def list_items(run_id=None):
    with read() as db:
        rows = db.execute(_SELECT + ("WHERE i.run_id = ? " if run_id else "") + "ORDER BY i.rowid DESC LIMIT 200",
                          [run_id] if run_id else []).fetchall()
    return [_view(r) for r in rows]


def get(action_id):
    with read() as db:
        row = db.execute(_SELECT + "WHERE i.action_id = ?", [action_id]).fetchone()
    if row is None:
        raise not_found(f"Action {action_id}")
    return _view(row)


def update(action_id, status, assignee, user):
    """One step forward (Member 3's rule), a named assignee, or both."""
    require(user, "UPDATE_ACTION")
    item = get(action_id)
    if not action_tracker_service.can_update(item, user):
        raise action_tracker_service.NotAllowed(f"{user.role} does not own this action.")
    if status is not None and status != item["next_status"]:
        raise action_tracker_service.InvalidTransition(
            f"An action that is {item['status'].replace('_', ' ').lower()} cannot become {status.replace('_', ' ').lower()}.")
    with acting(user.user_id):
        if assignee is not None and assignee != item["assignee"]:
            with transaction() as db:
                records.update(db, "action_items", "action_id", action_id, assignee=assignee, updated_at=records.now())
                audit_service.append(db, "ACTION_ASSIGNED", action_id, user, {"from": item["assignee"], "to": assignee})
        if status is not None:
            action_tracker_service.advance(action_id, user)
    return get(action_id)


def history(action_id):
    get(action_id)
    with read() as db:
        return db.execute("SELECT h.from_status, h.to_status, h.changed_at, coalesce(nullif(p.full_name, ''), p.email) AS "
                          "changed_by FROM action_status_history h LEFT JOIN user_profiles p ON p.user_id = h.changed_by "
                          "WHERE action_id = ? ORDER BY history_id", [action_id]).fetchall()
