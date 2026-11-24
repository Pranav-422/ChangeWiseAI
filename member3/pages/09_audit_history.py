import streamlit as st

from member3.application.session_manager import context, page_header
from member3.components import audit_timeline
from member3.services import audit_service, planning_service

ctx = context()
page_header("Audit History", ctx)
broken = audit_service.verify_chain()
if broken is None:
    st.success("✓ Audit chain intact: no event was altered, removed or reordered inside the log.")
else:
    st.error(f"Audit chain broken at event {broken}.")

st.subheader("Replay a planning run")
runs = planning_service.list_runs()
if runs:
    run = st.selectbox("Run", runs, format_func=lambda r: f"{r['run_id']} | {r['scenario_id']} | {r['decision']} | {r['created_at']}")
    if st.button("Replay"):
        outcome = audit_service.replay(run["run_id"], ctx.member2, ctx.user)
        if outcome["matches"]:
            st.success("✓ Replay reproduced the stored result exactly.")
        elif not outcome["snapshot_intact"]:
            st.error("The stored input no longer matches its recorded hash.")
        else:
            st.error("Replay gave a different result: the engine, its settings or the simulator changed.")
else:
    st.info("No planning runs yet.")

st.subheader("Events")
events = audit_service.history()
kinds = sorted({e["event_type"] for e in events})
chosen = st.multiselect("Event type", kinds)
audit_timeline.render([e for e in events if not chosen or e["event_type"] in chosen])
