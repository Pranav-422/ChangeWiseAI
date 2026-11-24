import streamlit as st

from member2.evaluation.run_all import rupees
from member3.application.session_manager import context, page_header
from member3.components import exception_table, inventory_charts, kpi_cards, stage_bar
from member3.services import action_tracker_service, approval_service, ecn_service, planning_service

ctx = context()
page_header("Executive Dashboard", ctx)
stage = planning_service.change_stage(ctx.scenario)
review, run = ecn_service.latest_review(ctx.scenario), ctx.run
stage_bar.render(stage)
if not review:
    st.warning("No ECN has been received for this scenario.")
elif review["status"] != "CONFIRMED":
    st.warning(f"The ECN is {review['validation']['validation_status'].replace('_', ' ').lower()} and not confirmed.")

baseline = ctx.member1.baseline(ctx.dataset)
exceptions = ctx.member1.exceptions(ctx.dataset, baseline)
bom = ctx.member1.bom_impact(ctx.dataset["engineering_change"]["old_material_id"])
if baseline is None:
    st.error("Member 1's records are incomplete or conflicting, so inventory cannot be simulated.")
change = ctx.dataset["engineering_change"]
kpi_cards.render([
    ("Active changes", int(change["status"] == "APPROVED" and stage < 5), "Approved engineering changes not yet closed"),
    ("Affected assemblies", len(bom["finished_assemblies"]), ", ".join(bom["finished_assemblies"])),
    ("Shortage (units)", baseline and baseline["total_shortage"], "Without corrective action"),
    ("Excess exposure", baseline and rupees(baseline["total_excess_value"]), "Without corrective action"),
    ("Critical exceptions", sum(e["band"] == "Critical" for e in exceptions) if baseline else None, "Member 1 severity band"),
    ("Pending approvals", len(approval_service.pending_runs()), "Across all scenarios"),
])

if baseline:
    left, right = st.columns(2)
    with left:
        inventory_charts.balance(baseline["weekly"], "Closing stock without corrective action", "dash-balance")
    with right:
        inventory_charts.demand_and_receipts(baseline["weekly"], "dash-demand")
st.subheader("Exceptions by severity")
if baseline:
    exception_table.render(exceptions)

left, right = st.columns(2)
with left:
    st.subheader("Recommended plan")
    if not run:
        st.info("Planning has not been run.")
    else:
        st.caption(f"Last simulation: {run['created_at']} UTC ({run['run_id']})")
        result = run["result"]
        state = ctx.approval["decision"].title() if ctx.approval else "Awaiting planner decision"
        if result["recommendations"]:
            best = result["recommendations"][0]
            st.markdown(f"**{best['summary']}**")
            st.markdown(f"Shortage {best['shortage_units']:g} units, E + C {rupees(best['secondary_cost'])}, "
                        f"robustness {best['robustness']['display']}. Status: {state}.")
        else:
            st.error(result["decision"].replace("_", " ").capitalize())
        for record in result["escalations"]:
            st.warning(f"{record['code']}: {record['message']}")
with right:
    st.subheader("Action completion")
    items = action_tracker_service.list_items(run["run_id"]) if run else []
    if items:
        done = sum(i["status"] == "DONE" for i in items)
        st.progress(done / len(items), f"{done} of {len(items)} actions done")
    else:
        st.info("No approved actions yet.")
