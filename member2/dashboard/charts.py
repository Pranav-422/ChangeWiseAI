"""Shared Plotly figures. Colours are a validated colour-blind-safe pair plus reserved status colours."""
import plotly.graph_objects as go

REV_B, REV_C = "#2a78d6", "#eb6834"      # categorical slots 1 and 2
EXCESS, ACTION = "#2a78d6", "#eb6834"
GOOD, CRITICAL = "#1baf7a", "#e34948"    # status only, always with a text label


def _layout(fig, title, y_title=None, x_title=None, height=340):
    fig.update_layout(title=title, height=height, margin=dict(l=10, r=10, t=50, b=10), bargap=0.35,
                      legend=dict(orientation="h", y=-0.2), hovermode="x unified")
    fig.update_yaxes(title=y_title, rangemode="tozero")
    fig.update_xaxes(title=x_title)
    return fig


def weekly_balance(weekly, title):
    weeks = [f"W{w['week']}" for w in weekly]
    fig = go.Figure()
    for key, name, colour in (("rev_b_closing", "Rev B closing stock", REV_B),
                              ("rev_c_closing", "Rev C closing stock", REV_C)):
        fig.add_scatter(x=weeks, y=[w[key] for w in weekly], name=name, mode="lines+markers",
                        line=dict(color=colour, width=2), marker=dict(size=8))
    if any(w["shortage"] for w in weekly):
        fig.add_bar(x=weeks, y=[w["shortage"] for w in weekly], name="Shortage", marker_color=CRITICAL,
                    text=[w["shortage"] or "" for w in weekly], textposition="outside")
    return _layout(fig, title, "Units")


def cost_bars(labels, excess, action, title):
    """Stacked E + C per plan or configuration, total labelled."""
    fig = go.Figure()
    line = dict(color="rgba(255,255,255,0.9)", width=2)
    fig.add_bar(y=labels, x=excess, name="Excess value", orientation="h",
                marker=dict(color=EXCESS, line=line), hovertemplate="₹%{x:,.0f}")
    fig.add_bar(y=labels, x=action, name="Action cost", orientation="h",
                marker=dict(color=ACTION, line=line), hovertemplate="₹%{x:,.0f}")
    totals = [e + a for e, a in zip(excess, action)]
    fig.add_scatter(y=labels, x=totals, mode="text", text=[f"  ₹{t:,.0f}" for t in totals],
                    textposition="middle right", showlegend=False, hoverinfo="skip")
    fig.update_layout(barmode="stack")
    _layout(fig, title, x_title="₹", height=130 + 60 * len(labels))
    fig.update_xaxes(range=[0, max(totals + [1]) * 1.2])
    return fig.update_yaxes(autorange="reversed").update_layout(hovermode="closest")


def shortage_bars(labels, shortage, title):
    fig = go.Figure(go.Bar(y=labels, x=shortage, orientation="h", marker_color=CRITICAL,
                           text=[f"{s:g}" for s in shortage], textposition="outside"))
    _layout(fig, title, x_title="Units", height=130 + 50 * len(labels))
    fig.update_xaxes(range=[0, max(list(shortage) + [1]) * 1.2])
    return fig.update_yaxes(autorange="reversed").update_layout(hovermode="closest")


def stress_grid(robustness, title):
    """3 x 3 grid: each cell states the result in words, so colour is never the only signal."""
    runs = robustness["scenarios"]
    leads = sorted({r["lead_time_shock"] for r in runs})
    demands = sorted({r["demand_shock"] for r in runs})
    cell = {(r["lead_time_shock"], r["demand_shock"]): r["shortage_units"] for r in runs}
    units = [[cell[lead, demand] for demand in demands] for lead in leads]
    fig = go.Figure(go.Heatmap(
        z=[[int(u > 0) for u in row] for row in units],
        x=[f"Demand {d:+.0%}" for d in demands], y=[f"Lead time +{lead} wk" for lead in leads],
        text=[["✓ no shortage" if u == 0 else f"✗ {u:g} short" for u in row] for row in units],
        texttemplate="%{text}", textfont=dict(color="#0b0b0b"), hovertemplate="%{y}, %{x}: %{text}<extra></extra>",
        colorscale=[[0, "#bfe8d6"], [1, "#f6b9b8"]], zmin=0, zmax=1, showscale=False, xgap=2, ygap=2))
    return _layout(fig, title, height=260).update_layout(hovermode="closest").update_yaxes(autorange="reversed")
