"""Plotly chart builders."""

from collections import Counter

import numpy as np
import plotly.graph_objects as go

_CHART_LAYOUT = dict(template="plotly_white", margin=dict(l=20, r=20, t=50, b=10))
_SPLINE = dict(shape="spline", smoothing=1.2)


def plot_rolling_trend(tg, window: int = 5) -> go.Figure:
    gf_col = f"rolling{window}GoalsFor"
    ga_col = f"rolling{window}GoalsAgainst"
    pts_col = f"rolling{window}Points"
    fig = go.Figure()
    if gf_col in tg.columns:
        fig.add_trace(
            go.Scatter(
                x=tg["gameDate"], y=tg[gf_col],
                mode="lines+markers",
                name=f"GF ({window}g)",
                line={**_SPLINE, "color": "#22c55e", "width": 2.5},
                marker=dict(size=5),
            )
        )
    if ga_col in tg.columns:
        fig.add_trace(
            go.Scatter(
                x=tg["gameDate"], y=tg[ga_col],
                mode="lines+markers",
                name=f"GA ({window}g)",
                line={**_SPLINE, "color": "#ef4444", "width": 2.5},
                marker=dict(size=5),
            )
        )
    if pts_col in tg.columns:
        fig.add_trace(
            go.Scatter(
                x=tg["gameDate"], y=tg[pts_col],
                mode="lines+markers",
                name=f"Pts ({window}g)", yaxis="y2",
                line={**_SPLINE, "color": "#3b82f6", "width": 2},
                marker=dict(size=4),
            )
        )
    fig.update_layout(
        **_CHART_LAYOUT,
        title=f"Rolling {window}-Game Trend",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(title="Goals"),
        yaxis2=dict(title=f"Points ({window}g)", overlaying="y", side="right"),
        height=370,
    )
    return fig


def plot_goal_diff_trend(tg) -> go.Figure:
    gd = tg["goalDiff"]
    colors = ["#22c55e" if v > 0 else "#ef4444" if v < 0 else "#f59e0b" for v in gd]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=tg["gameDate"], y=gd,
            marker_color=colors, opacity=0.72, name="Goal Diff",
            hovertemplate="<b>%{x|%b %d}</b><br>Goal diff: %{y}<extra></extra>",
        )
    )
    if "rolling5GoalDiff" in tg.columns:
        fig.add_trace(
            go.Scatter(
                x=tg["gameDate"], y=tg["rolling5GoalDiff"],
                mode="lines", name="5-Game Trend",
                line={**_SPLINE, "color": "#1d4ed8", "width": 2.5},
            )
        )
    fig.add_hline(y=0, line_dash="dot", line_color="#94a3b8", line_width=1)
    fig.update_layout(
        **_CHART_LAYOUT,
        title="Goal Differential (per game)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=340,
    )
    return fig


def plot_momentum(tg) -> go.Figure:
    ms = tg["momentumScore"]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=tg["gameDate"], y=ms,
            mode="lines+markers",
            line={**_SPLINE, "color": "#8b5cf6", "width": 2.5},
            marker=dict(
                size=6,
                color=ms,
                colorscale=[
                    [0, "#ef4444"], [0.45, "#ef4444"],
                    [0.45, "#f59e0b"], [0.55, "#f59e0b"],
                    [0.55, "#22c55e"], [1, "#22c55e"],
                ],
                cmin=30, cmax=70, showscale=False,
            ),
            fill="tozeroy",
            fillcolor="rgba(139,92,246,0.07)",
            name="Momentum",
        )
    )
    fig.add_hline(y=50, line_dash="dash", line_color="#94a3b8", line_width=1)
    fig.add_hrect(y0=55, y1=100, fillcolor="#22c55e", opacity=0.04, line_width=0)
    fig.add_hrect(y0=0, y1=45, fillcolor="#ef4444", opacity=0.04, line_width=0)
    fig.update_layout(**_CHART_LAYOUT, title="Momentum Score", height=320)
    return fig


def plot_points_path(tg, projected_points: float) -> go.Figure:
    pts = tg[["gameDate", "cumulativePoints"]].copy()
    pace = np.linspace(0, projected_points, len(pts))
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=pts["gameDate"], y=pts["cumulativePoints"],
            mode="lines+markers", name="Actual",
            line={**_SPLINE, "color": "#3b82f6", "width": 2.5},
            marker=dict(size=5),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=pts["gameDate"], y=pace,
            mode="lines", name="Projected pace",
            line=dict(dash="dash", color="#94a3b8", width=1.5),
        )
    )
    fig.update_layout(**_CHART_LAYOUT, height=360, title="Points Path vs Projected Pace")
    return fig


def plot_sim_histogram(
    a_goals: np.ndarray, b_goals: np.ndarray, team_a: str, team_b: str
) -> go.Figure:
    max_g = int(max(a_goals.max(), b_goals.max(), 8))
    x = list(range(0, max_g + 1))
    n = len(a_goals)
    ca = Counter(a_goals.tolist())
    cb = Counter(b_goals.tolist())
    ya = [ca.get(g, 0) / n * 100 for g in x]
    yb = [cb.get(g, 0) / n * 100 for g in x]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x, y=ya, name=team_a, opacity=0.78, marker_color="#3b82f6"))
    fig.add_trace(go.Bar(x=x, y=yb, name=team_b, opacity=0.78, marker_color="#ef4444"))
    fig.update_layout(
        **_CHART_LAYOUT,
        barmode="group",
        title="Simulated Goals Distribution (10,000 games)",
        xaxis_title="Goals Scored",
        yaxis_title="Frequency (%)",
        height=360,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig
