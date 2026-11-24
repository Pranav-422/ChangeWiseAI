import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from member2.dashboard.charts import CRITICAL, REV_B, REV_C, _layout, weekly_balance

COLUMNS = ("opening", "receipts", "usage", "closing")


def revision_table(weekly, revision):
    prefix = f"rev_{revision.lower()}_"
    return pd.DataFrame([{"Week": f"W{w['week']}", **{c.title(): w[prefix + c] for c in COLUMNS}} for w in weekly])


def balance(weekly, title, key):
    st.plotly_chart(weekly_balance(weekly, title), key=key)


def demand_and_receipts(weekly, key):
    weeks = [f"W{w['week']}" for w in weekly]
    fig = go.Figure()
    for prefix, name, colour in (("rev_b", "Rev B receipts", REV_B), ("rev_c", "Rev C receipts", REV_C)):
        fig.add_bar(x=weeks, y=[w[f"{prefix}_receipts"] for w in weekly], name=name, marker_color=colour)
    fig.add_scatter(x=weeks, y=[w["demand"] for w in weekly], name="Demand", mode="lines+markers",
                    line=dict(color="#52514e", width=2, dash="dot"), marker=dict(size=8))
    st.plotly_chart(_layout(fig, "Weekly demand and supplier receipts", "Units"), key=key)


def shortage(weekly, key):
    if not any(w["shortage"] for w in weekly):
        st.success("✓ No shortage in any week.")
        return
    fig = go.Figure(go.Bar(x=[f"W{w['week']}" for w in weekly], y=[w["shortage"] for w in weekly],
                           marker_color=CRITICAL, text=[w["shortage"] or "" for w in weekly], textposition="outside"))
    st.plotly_chart(_layout(fig, "Unmet demand by week", "Units", height=260), key=key)
