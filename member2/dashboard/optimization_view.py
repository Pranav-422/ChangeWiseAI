"""Recommendation, escalations, weekly balance and rejected plans. Reusable: render(result)."""
import pandas as pd
import streamlit as st

from ..engine.recommendation import describe_action
from .charts import weekly_balance

_BANNER = {"RECOMMENDED": st.success, "ESCALATED": st.warning,
           "NO_FEASIBLE_PLAN": st.error, "INVALID_DATA": st.error}


def _label(action):
    return f"Keep {action['po_id']} as is" if action["action"] == "KEEP_PO" else describe_action(action)


def recommendation_table(result):
    return pd.DataFrame([{
        "Rank": r["rank"], "Plan": r["plan_id"], "Effective week": f"W{r['effective_week']}",
        "Shortage": r["shortage_units"], "Excess (₹)": r["excess_value"],
        "Action cost (₹)": r["action_cost"], "E + C (₹)": r["secondary_cost"],
        "Robust": r["robustness"]["display"], "Near-ties": len(r["near_ties"]),
        "Actions": r["summary"],
    } for r in result["recommendations"]])


def rejected_table(result):
    return pd.DataFrame([{
        "Actions": "; ".join(_label(a) for a in p["actions"]) or "No change",
        "Rule": r["rule"], "Code": r["code"], "Reason": r["description"],
    } for p in result["rejected_plans"] for r in p["rejection_reasons"]])


def render(result):
    _BANNER[result["decision"]](f"Decision: {result['decision'].replace('_', ' ').lower()}")
    for record in result["escalations"]:
        st.warning(f"**{record['code']}**: {record['message']}")
        if record["evidence"]:
            st.dataframe(pd.DataFrame(record["evidence"]), hide_index=True)
    counts = result["counts"]
    for column, (label, value) in zip(st.columns(4), (
            ("Combinations", counts["combinations"]), ("Feasible plans", counts["feasible"]),
            ("Rejected plans", counts["rejected"]), ("Seconds", result["computation_seconds"]))):
        column.metric(label, value)
    if result["recommendations"]:
        st.subheader("Top plans")
        st.dataframe(recommendation_table(result), hide_index=True)
        pick = st.selectbox("Weekly balance for", result["recommendations"],
                            format_func=lambda r: f"#{r['rank']} {r['summary']}")
        st.plotly_chart(weekly_balance(pick["weekly"], "Closing stock by week"), key="weekly")
        with st.expander("Weekly table"):
            st.dataframe(pd.DataFrame(pick["weekly"]), hide_index=True)
        st.subheader("Best plan per effective week")
        st.dataframe(pd.DataFrame(result["effective_week_comparison"]), hide_index=True)
    if result["rejected_plans"]:
        st.subheader("Rejected plans")
        st.dataframe(rejected_table(result), hide_index=True)
