"""Standalone Member 2 dashboard (Member 3's shell imports the views instead).

    streamlit run member2/dashboard/app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # streamlit runs this file as a script

import streamlit as st  # noqa: E402

from member2.dashboard import evaluation_view, optimization_view, plan_comparison, robustness_view  # noqa: E402
from member2.engine.pipeline import run_optimization  # noqa: E402
from member2.evaluation.comparison import compare_configurations  # noqa: E402
from member2.integration import member1_bridge  # noqa: E402


@st.cache_data
def compute(name):
    data = member1_bridge.load_dataset(name)
    result = run_optimization(data)
    return result, compare_configurations(data, result=result)


st.set_page_config(page_title="ChangeWise optimization", layout="wide")
st.title("ChangeWise: optimization engine")
name = st.sidebar.selectbox("Scenario", member1_bridge.list_scenarios())
result, rows = compute(name)
st.sidebar.caption(f"Simulator: `{result['simulator']}`")
st.sidebar.caption(f"Method: {result['method'] or 'not run'}")
st.sidebar.caption(f"Input hash: `{result['input_hash'][:12]}`")
tabs = st.tabs(["Recommendation", "Plan comparison", "Robustness", "Baselines"])
for tab, view, payload in zip(tabs, (optimization_view, plan_comparison, robustness_view, evaluation_view),
                              (result, result, result, rows)):
    with tab:
        view.render(payload)
