"""Baseline A, Baseline B and ChangeWise. Reusable: render(rows) with compare_configurations() output."""
import pandas as pd
import streamlit as st

from .charts import cost_bars, shortage_bars


def render(rows):
    if not rows:
        st.info("Input data is invalid, so no configuration was run.")
        return
    labels = [r["configuration"] for r in rows]
    if any(r["shortage_units"] for r in rows):
        st.plotly_chart(shortage_bars(labels, [r["shortage_units"] for r in rows], "Shortage by configuration"), key="es")
    else:
        st.success("✓ No shortage in any of these configurations.")
    st.plotly_chart(cost_bars(labels, [r["excess_value"] for r in rows], [r["action_cost"] for r in rows],
                              "Excess value + action cost by configuration"), key="ec")
    st.dataframe(pd.DataFrame([{
        "Configuration": r["configuration"], "Shortage": r["shortage_units"],
        "Shortage weeks": ", ".join(f"W{w}" for w in r["shortage_weeks"]), "Rev B leftover": r["rev_b_leftover"],
        "Rev C closing": r["rev_c_closing"], "Excess (₹)": r["excess_value"],
        "Action cost (₹)": r["action_cost"], "E + C (₹)": r["secondary_cost"],
        "Rule violations": r["hard_rule_violations"], "Robust": r["robustness"]["display"],
    } for r in rows]), hide_index=True)
    for row in rows:
        st.caption(f"**{row['configuration']}**: {' '.join(row['assumptions'])}")
    st.caption("Synthetic data: this shows ranking logic, not proven savings.")
