import pandas as pd
import streamlit as st

from member3.ai.what_if_parser import OK, parse_what_if_request
from member3.application.access_control import NotAllowed
from member3.application.session_manager import context, page_header, require_run
from member3.services import what_if_service

ctx = context()
page_header("What-If Simulator", ctx)
run = require_run(ctx)
st.caption("Ask about: Rev C delay, demand change, effective week, Rev B order reduction, supplier block. "
           "The AI only translates the question; the engine calculates. The baseline is never changed.")
state = st.session_state
with st.form("question"):
    question = st.text_input("Question", placeholder="What if the Rev C supplier is delayed by one week?")
    if st.form_submit_button("Interpret", type="primary"):
        state.what_if = {"run_id": run["run_id"], "question": question, "outcome": None,
                         "parsed": parse_what_if_request(question, run["dataset"], ctx.provider)}
current = state.get("what_if")
if not current or current["run_id"] != run["run_id"]:
    st.stop()

parsed = current["parsed"]
st.caption(f"Interpreted by {parsed['source']}" + (f" (AI failed: {parsed['provider_error']})" if parsed["provider_error"] else ""))
if parsed["status"] != OK:
    st.warning(f"{parsed['status']}: {parsed['message']}")
    st.stop()
st.subheader("Interpreted parameters")
parameters = {k: v for k, v in parsed["parameters"].items() if k not in ("scenario_id", "requires_confirmation")}
st.dataframe(pd.DataFrame([{"Parameter": k.replace("_", " "), "Value": "unchanged" if v in (0, None) else str(v)}
                           for k, v in parameters.items()]), hide_index=True)
if current["outcome"] is None:
    if st.button("Confirm and run", type="primary"):
        try:
            current["outcome"] = what_if_service.submit_scenario_to_optimizer(
                parsed["parameters"], run, ctx.member2, ctx.user, current["question"])
            st.rerun()
        except NotAllowed as error:
            st.error(str(error))
    st.stop()

outcome = current["outcome"]
if outcome["status"] != OK:
    st.error(f"{outcome['status']}: {outcome['message']}")
    st.stop()
st.subheader("Result")
st.markdown(":blue-badge[Template-generated] " + what_if_service.describe_comparison(outcome["comparison"]))
st.dataframe(pd.DataFrame([{"Measure": r["measure"].replace("_", " "), **{
    k.capitalize(): "n/a" if r[k] is None else str(r[k]) for k in ("base", "alternative", "change")}}
    for r in outcome["comparison"]]), hide_index=True)
for record in outcome["result"]["escalations"]:
    st.warning(f"{record['code']}: {record['message']}")
