"""Nine-scenario stress grids. Reusable: render(result)."""
import pandas as pd
import streamlit as st

from .charts import stress_grid


def render(result):
    if not result["recommendations"]:
        st.info("No feasible plan to stress-test.")
        return
    st.caption("Supplementary evidence: it never changes the official ranking.")
    for plan in result["recommendations"]:
        score = plan["robustness"]
        st.plotly_chart(stress_grid(
            score, f"#{plan['rank']} {plan['plan_id']}: {score['display']} runs without shortage "
                   f"({score['ratio']:.2%})"), key=f"stress-{plan['plan_id']}")
        with st.expander(f"Runs for {plan['plan_id']}"):
            st.write(plan["summary"])
            st.dataframe(pd.DataFrame(score["scenarios"]), hide_index=True)
