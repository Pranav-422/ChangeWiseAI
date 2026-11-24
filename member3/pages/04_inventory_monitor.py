import pandas as pd
import streamlit as st

from member2.evaluation.run_all import rupees
from member3.application.session_manager import context, page_header
from member3.components import exception_table, inventory_charts, kpi_cards

ctx = context()
page_header("Inventory Monitor", ctx)
baseline = ctx.member1.baseline(ctx.dataset)
if baseline is None:
    st.error("The records are incomplete or conflicting, so inventory cannot be simulated.")
    for error in ctx.member2.input_problems(ctx.dataset):
        st.error(error["description"])
    st.stop()

views = {"Without corrective action": {"weekly": baseline["weekly"], "shortage": baseline["total_shortage"],
                                       "excess": baseline["total_excess_value"]}}
if ctx.run:
    for plan in ctx.run["result"]["recommendations"]:
        views[f"Plan #{plan['rank']}: {plan['summary']}"] = {
            "weekly": plan["weekly"], "shortage": plan["shortage_units"], "excess": plan["excess_value"]}
view = views[st.selectbox("Show", list(views))]
weekly = view["weekly"]
kpi_cards.render([
    ("Shortage (units)", view["shortage"], "Total unmet demand over the horizon"),
    ("Shortage weeks", ", ".join(f"W{w['week']}" for w in weekly if w["shortage"]) or "none", None),
    ("Rev B left at the end", weekly[-1]["rev_b_closing"], "Units"),
    ("Rev C at the end", weekly[-1]["rev_c_closing"], "Units"),
    ("Excess value", rupees(view["excess"]), "Rev B leftover plus Rev C above four weeks of demand"),
])
inventory_charts.balance(weekly, "Closing stock by week", "inv-balance")
left, right = st.columns(2)
with left:
    inventory_charts.demand_and_receipts(weekly, "inv-demand")
with right:
    inventory_charts.shortage(weekly, "inv-short")
for revision in "BC":
    st.subheader(f"Rev {revision}")
    st.dataframe(inventory_charts.revision_table(weekly, revision), hide_index=True)
st.subheader("Demand and shortage")
st.dataframe(pd.DataFrame([{"Week": f"W{w['week']}", "Demand": w["demand"], "Shortage": w["shortage"]} for w in weekly]),
             hide_index=True)
st.subheader("Stock records")
st.dataframe(pd.DataFrame(ctx.dataset["inventory"]), hide_index=True)
st.subheader("Exceptions by severity")
exception_table.render(ctx.member1.exceptions(ctx.dataset, baseline))
