import streamlit as st

from member2.engine.recommendation import describe_plan

from ..application.access_control import NotAllowed, allowed
from ..application.session_manager import flash
from ..services import approval_service


def _submit(ctx, decision, comment, **choice):
    try:
        approval_service.decide(ctx.run["run_id"], decision, ctx.user, ctx.member1, ctx.member2, comment, **choice)
    except (approval_service.DecisionRefused, NotAllowed) as error:
        st.error(str(error))
        return
    st.session_state.pop("modified", None)
    flash(f"Plan {decision.lower()}. The decision is in the audit log.")
    st.rerun()


def _option_label(option):
    return describe_plan({"actions": option}) if option else "Leave as is"


def render_modify(ctx):
    """Choose one eligible option per decision; Member 2 evaluates the result before it can be approved."""
    run = ctx.run
    recommended = next((p["actions"] for p in run["result"]["recommendations"]), [])
    picks = []
    with st.form("modify"):
        for name, options in ctx.member2.menus(run["dataset"]).items():
            if not options:
                continue
            start = next((i for i, o in enumerate(options) if o and all(a in recommended for a in o)
                          and (name == "Changeover" or len(o) == sum(a.get("po_id") == name for a in recommended))), 0)
            picks.append(st.selectbox(name, options, index=start, format_func=_option_label, key=f"mod-{name}"))
        if st.form_submit_button("Evaluate modified plan"):
            actions = [a for option in picks for a in option]
            st.session_state.modified = {
                "run_id": run["run_id"], "actions": actions,
                "plan": approval_service.evaluate_modification(run["run_id"], actions, ctx.member2, ctx.user)}
    modified = st.session_state.get("modified")
    if not modified or modified["run_id"] != run["run_id"]:
        return
    plan = modified["plan"]
    st.markdown(f"**{plan['plan_id']}**: {plan['summary']}")
    if plan["feasibility"] != "FEASIBLE":
        for item in plan["rejection_reasons"]:
            st.error(f"{item['code']}: {item['description']}")
        return
    st.markdown(f"Shortage {plan['shortage_units']:g} units, excess ₹{plan['excess_value']:,.0f}, action cost "
                f"₹{plan['action_cost']:,.0f}, robustness {plan['robustness']['display']}.")
    comment = st.text_input("Why this modification?", key="modified-comment")
    if st.button("Approve modified plan"):
        _submit(ctx, "APPROVED", comment, modified_actions=modified["actions"])


def render(ctx):
    result = ctx.run["result"]
    if ctx.approval:
        done = ctx.approval
        (st.success if done["decision"] == "APPROVED" else st.error)(
            f"{done['decision'].title()} by {done['user_name']} ({done['role']}) at {done['created_at']}")
        if done["plan"]:
            st.markdown(f"**{done['plan']['plan_id']}**: {done['plan']['summary']}" + (" (modified)" if done["modified"] else ""))
        if done["comment"]:
            st.text(f"Comment: {done['comment']}")
        return
    if not allowed(ctx.user, "DECIDE_PLAN"):
        st.info(f"{ctx.user.role} can view this case. Only the Planner can decide.")
        return
    for record in result["escalations"]:
        st.warning(f"**{record['code']}**: {record['message']}")
    if not result["recommendations"]:
        st.error("There is no plan to approve.")
    else:
        choice = st.radio("Plan", result["recommendations"], format_func=lambda p: (
            f"#{p['rank']} {p['summary']} (shortage {p['shortage_units']:g}, E + C ₹{p['secondary_cost']:,.0f}, "
            f"robust {p['robustness']['display']})"))
    comment = st.text_area("Comment (required for escalated cases, other ranks, modifications and rejections)")
    approve, reject = st.columns(2)
    if result["recommendations"] and approve.button("Approve plan", type="primary"):
        _submit(ctx, "APPROVED", comment, plan_id=choice["plan_id"])
    if reject.button("Reject"):
        _submit(ctx, "REJECTED", comment)
    if result["decision"] != "INVALID_DATA":
        with st.expander("Modify the plan", expanded="modified" in st.session_state):
            render_modify(ctx)
