import pandas as pd
import streamlit as st

_MARK = {"Critical": "🔴 Critical", "High": "🟠 High", "Medium": "🟡 Medium", "Low": "⚪ Low"}


def render(exceptions):
    """Member 1's exceptions in Member 1's order (severity, highest first)."""
    if not exceptions:
        st.success("✓ No exceptions.")
        return
    st.dataframe(pd.DataFrame([{
        "Band": _MARK.get(e["band"], e["band"]), "Exception": e["exception_id"],
        "Type": e["type"].replace("_", " ").capitalize(), "Week": f"W{e['week']}", "Units": e["units"],
        "Impact (₹)": e["impact_rs"], "Severity": e["severity"], "Description": e["description"],
    } for e in exceptions]), hide_index=True)
