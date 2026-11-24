import streamlit as st

from member3.application.access_control import NotAllowed, allowed
from member3.application.session_manager import context, flash, page_header, require_run
from member3.components import stage_bar
from member3.services import action_tracker_service as tracker
from member3.services import planning_service

ctx = context()
page_header("Action Tracker", ctx)
run = require_run(ctx)
stage_bar.render(planning_service.change_stage(ctx.scenario))
items = tracker.list_items(run["run_id"])
if not ctx.approval or ctx.approval["decision"] != "APPROVED":
    st.info("Actions appear here once the planner approves a plan.")
    st.stop()
if not items:
    st.info("The approved plan has no actions: the original changeover stands.")
else:
    done = sum(i["status"] == "DONE" for i in items)
    st.progress(done / len(items), f"{done} of {len(items)} actions done")
_BADGE = {"OPEN": ":red-badge[Open]", "IN_PROGRESS": ":orange-badge[In progress]", "DONE": ":green-badge[✓ Done]"}
for item in items:
    with st.container(border=True):
        text, owner, status, button = st.columns([4, 2, 2, 2])
        text.markdown(f"**{item['summary']}**")
        text.caption(f"{item['action_id']} | updated {item['updated_at']} UTC")
        owner.markdown(item["owner_role"])
        status.markdown(_BADGE[item["status"]])
        following = tracker.NEXT[item["status"]]
        if following and tracker.can_update(item, ctx.user) and button.button(
                "Start" if following == "IN_PROGRESS" else "Mark done", key=item["action_id"]):
            tracker.advance(item["action_id"], ctx.user)
            st.rerun()
if ctx.approval["closed_at"]:
    st.success(f"Change closed at {ctx.approval['closed_at']} UTC.")
elif all(i["status"] == "DONE" for i in items) and allowed(ctx.user, "CLOSE_CHANGE"):
    if st.button("Close change", type="primary"):
        try:
            tracker.close_change(run["run_id"], ctx.user)
            flash("Change closed.")
            st.rerun()
        except (NotAllowed, tracker.InvalidTransition) as error:
            st.error(str(error))
