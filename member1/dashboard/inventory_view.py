"""Standalone Rev B / Rev C inventory view. Run:  streamlit run dashboard/inventory_view.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from engine import CONFIG  # noqa: E402
from engine.data_loader import load_csv_data, to_records  # noqa: E402
from engine.inventory import calculate_closing_stock, simulate_inventory  # noqa: E402
from engine.scenarios import SCENARIOS, load_scenario  # noqa: E402

st.set_page_config(page_title="ChangeWise - Inventory", layout="wide")
st.title("Rev B / Rev C weekly inventory")
st.caption("Synthetic demo data. Every number below is computed by the Member 1 simulator.")

scenario = st.sidebar.selectbox("Seeded scenario", list(SCENARIOS), format_func=lambda s: f"{s} - {SCENARIOS[s]}")
data = load_scenario(scenario, load_csv_data())
change = to_records(data["engineering_changes"])[0]
eff0, use0 = int(change["effective_week"]), int(change["use_up_end_week"])
eff = st.sidebar.slider("Effective week (Rev C)", 1, max(CONFIG["horizon_weeks"], eff0), eff0)
use_up = st.sidebar.slider("Rev B use-up end week", 1, max(CONFIG["horizon_weeks"], use0), use0)
shift = st.sidebar.select_slider("Rev C lead-time shock (weeks)", [0, 1, 2], 0)
demand_pct = st.sidebar.select_slider("Demand shock", [-10, 0, 10], 0, format_func=lambda p: f"{p:+d}%")

sim = simulate_inventory(data["materials"], data["inventory"], data["demand"], data["purchase_orders"],
                         {**change, "effective_week": eff, "use_up_end_week": use_up}, data["suppliers"],
                         lead_time_shift=shift, demand_multiplier=1 + demand_pct / 100, scenario_id=scenario.upper())

status_color = {"VALID": "green", "NEEDS_REVIEW": "orange", "INSUFFICIENT_DATA": "orange", "INVALID": "red"}
st.markdown(f"**{sim['simulation_id']}** · status :{status_color[sim['validation_status']]}[{sim['validation_status']}]"
            f" · engine {sim['engine_version']}")
if not sim["weeks"]:
    st.error("Simulation not run: core inputs are invalid or missing.")
    st.dataframe(pd.DataFrame(sim["issues"]), hide_index=True)
    st.stop()
if sim["validation_status"] in ("INVALID", "INSUFFICIENT_DATA"):
    st.error("Not plannable: the numbers below are indicative only until the validation issues at the bottom are fixed.")
elif sim["validation_status"] == "NEEDS_REVIEW":
    st.warning("Needs planner review: see the validation issues at the bottom of the page.")

ex, sh = sim["excess"], sim["shortage"]
c = st.columns(5)
c[0].metric("Total shortage (units)", sh["total_shortage_units"],
            help=f"First shortage week: {sh['first_shortage_week'] or '-'}; weeks short: {sh['shortage_weeks']}")
c[1].metric("Rev B scrap (units)", ex["rev_b_scrap_units"])
c[2].metric("E_B Rev B scrap value", f"₹{ex['rev_b_scrap_value']:,.0f}")
c[3].metric("E_C Rev C excess value", f"₹{ex['rev_c_excess_value']:,.0f}")
c[4].metric("E = E_B + E_C", f"₹{ex['total_excess_value']:,.0f}")

w = pd.DataFrame(sim["weeks"])
w["label"] = "W" + w["week"].astype(str)
fig = go.Figure()
fig.add_bar(x=w["label"], y=w["demand"], name="Demand", marker_color="#c9d3e0")
fig.add_bar(x=w["label"], y=w["shortage"], name="Unmet demand", marker_color="#d62728")
fig.add_scatter(x=w["label"], y=w["rev_b_closing"], name="Rev B closing", mode="lines+markers", line_color="#1f4e79")
fig.add_scatter(x=w["label"], y=w["rev_c_closing"], name="Rev C closing", mode="lines+markers", line_color="#2ca02c")
rec = w.assign(receipts=w["rev_b_receipts"] + w["rev_c_receipts"]).query("receipts > 0")   # weeks with a delivery only
fig.add_scatter(x=rec["label"], y=rec["receipts"], name="Receipts", mode="markers+text", text=rec["receipts"],
                textposition="middle right", marker_symbol="triangle-up", marker_size=12, marker_color="#ff7f0e")
fig.add_vline(x=eff - 1, line_dash="dash", annotation_text=f"Rev C effective W{eff}", annotation_position="top left")
fig.add_vline(x=use_up - 1 + 0.5, line_dash="dot", annotation_text=f"Rev B use-up end W{use_up}",
              annotation_position="bottom right")
fig.update_layout(barmode="overlay", height=430, yaxis_title="Units", legend_orientation="h", margin=dict(t=30))
st.plotly_chart(fig, use_container_width=True)

ok = all(r["rev_b_reconciled"] and r["rev_c_reconciled"] for r in calculate_closing_stock(sim))
st.subheader("Weekly balances " + ("✅ reconciled" if ok else "❌ NOT reconciled"))
cols = ["label", "demand", "applicable_revision", "rev_b_opening", "rev_b_receipts", "rev_b_usage", "rev_b_closing",
        "rev_c_opening", "rev_c_receipts", "rev_c_usage", "rev_c_closing", "shortage"]
st.dataframe(w[cols].rename(columns={"label": "week"}), hide_index=True, use_container_width=True)

st.subheader("Exceptions (severity-ranked)")
if sim["exceptions"]:
    st.dataframe(pd.DataFrame(sim["exceptions"])[["severity_rank", "severity_level", "severity_score", "exception_type",
                                                  "material_id", "week", "quantity", "financial_impact", "owner_role",
                                                  "description", "recommended_action"]],
                 hide_index=True, use_container_width=True)
else:
    st.success("No exceptions.")
issues = [i for i in sim["issues"] if i["status"] != "VALID"]
if issues:
    st.subheader("Validation issues")
    st.dataframe(pd.DataFrame(issues), hide_index=True, use_container_width=True)
