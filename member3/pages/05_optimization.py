import streamlit as st

from member3.application.session_manager import context, page_header, require_run
from member3.components import explanation_panel, plan_comparison, robustness_chart

ctx = context()
page_header("Optimization Recommendations", ctx)
run = require_run(ctx)
result = run["result"]
st.caption(f"{run['run_id']} | {run['created_at']} UTC | engine {result['engine_version']} | "
           f"simulator `{result['simulator']}`")
tabs = st.tabs(["Explanation", "Recommendation", "Plan comparison", "Robustness", "Baselines"])
with tabs[0]:
    explanation_panel.render(run["explanation"])
with tabs[1]:
    plan_comparison.render_recommendation(result)
with tabs[2]:
    plan_comparison.render_plans(result)
with tabs[3]:
    robustness_chart.render(result)
with tabs[4]:
    plan_comparison.render_baselines(ctx.member2.compare(run["dataset"], result))
