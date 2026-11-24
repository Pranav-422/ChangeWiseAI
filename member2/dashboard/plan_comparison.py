"""Cost comparison across the recommended plans. Reusable: render(result)."""
import pandas as pd
import streamlit as st

from .charts import cost_bars, shortage_bars


def render(result):
    plans = result["recommendations"]
    if not plans:
        st.info("No feasible plan to compare.")
        return
    labels = [f"#{p['rank']} {p['plan_id']}" for p in plans]
    st.caption("First priority: shortage. Second priority: excess value + action cost.")
    if any(p["shortage_units"] for p in plans):
        st.plotly_chart(shortage_bars(labels, [p["shortage_units"] for p in plans], "Shortage by plan"), key="ps")
    else:
        st.success("✓ No shortage in any of these plans.")
    st.plotly_chart(cost_bars(labels, [p["excess_value"] for p in plans],
                              [p["action_cost"] for p in plans], "Excess value + action cost by plan"), key="pc")
    st.subheader("All feasible plans")
    st.dataframe(pd.DataFrame([{
        "Rank": p["rank"], "Plan": p["plan_id"], "Effective week": p["effective_week"],
        "Policy": p["consumption_policy"], "Shortage": p["shortage_units"], "Excess (₹)": p["excess_value"],
        "Action cost (₹)": p["action_cost"], "E + C (₹)": p["secondary_cost"],
        "Redundant variant of": p.get("redundant_of"),
    } for p in result["ranked_plans"]]), hide_index=True)
    if result["near_ties"]:
        st.subheader("Near-ties with the leading plan")
        st.dataframe(pd.DataFrame(result["near_ties"]), hide_index=True)
