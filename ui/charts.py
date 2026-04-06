"""Chart builders — Plotly figures for the dashboard."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

_CHART_LAYOUT = dict(template="plotly_white", margin=dict(l=20, r=20, t=50, b=10))
_SPLINE = dict(shape="spline", smoothing=1.2)


def plot_team_trend(team_games: pd.DataFrame) -> go.Figure:
    """Rolling goal diff and shot diff trend."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=team_games["gameDate"], y=team_games["rolling3GoalDiff"],
        mode="lines+markers", name="Rolling 3 Goal Diff",
        line={**_SPLINE, "color": "#3b82f6", "width": 2.5},
        marker=dict(size=6),
    ))
    if "rolling3ShotDiff" in team_games.columns:
        fig.add_trace(go.Scatter(
            x=team_games["gameDate"], y=team_games["rolling3ShotDiff"],
            mode="lines+markers", name="Rolling 3 Shot Diff", yaxis="y2",
            line={**_SPLINE, "color": "#f59e0b", "width": 2},
            marker=dict(size=5),
        ))
    fig.add_hline(y=0, line_dash="dot", line_color="#cbd5e1", line_width=1)
    fig.update_layout(
        **_CHART_LAYOUT,
        title="Recent Form Trend",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(title="Goal Diff"),
        yaxis2=dict(title="Shot Diff", overlaying="y", side="right"),
        height=420,
    )
    return fig


def plot_momentum(team_games: pd.DataFrame) -> go.Figure:
    """Momentum score trend chart."""
    ms = team_games["momentumScore"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=team_games["gameDate"], y=ms,
        mode="lines+markers",
        line={**_SPLINE, "color": "#8b5cf6", "width": 2.5},
        marker=dict(size=6, color=ms,
                    colorscale=[[0, "#ef4444"], [0.45, "#ef4444"], [0.45, "#f59e0b"],
                                [0.55, "#f59e0b"], [0.55, "#22c55e"], [1, "#22c55e"]],
                    cmin=30, cmax=70, showscale=False),
        fill="tozeroy", fillcolor="rgba(139,92,246,0.07)", name="Momentum",
    ))
    fig.add_hline(y=50, line_dash="dash", line_color="#94a3b8", line_width=1)
    fig.add_hrect(y0=55, y1=100, fillcolor="#22c55e", opacity=0.04, line_width=0)
    fig.add_hrect(y0=0, y1=45, fillcolor="#ef4444", opacity=0.04, line_width=0)
    fig.update_layout(**_CHART_LAYOUT, title="Momentum Score", height=350)
    return fig


def plot_impact_chart(team_games: pd.DataFrame) -> go.Figure:
    """Game-by-game goal differential bar chart."""
    gd = team_games["goalDiff"]
    colors = ["#22c55e" if v > 0 else "#ef4444" if v < 0 else "#f59e0b" for v in gd]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=team_games["gameDate"], y=gd, marker_color=colors, opacity=0.75, name="Goal Diff",
        hovertemplate="<b>%{x|%b %d}</b><br>Goal diff: %{y}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=team_games["gameDate"], y=team_games["rolling3GoalDiff"],
        mode="lines", name="3-Game Trend",
        line={**_SPLINE, "color": "#1d4ed8", "width": 2.5},
    ))
    fig.add_hline(y=0, line_dash="dot", line_color="#94a3b8", line_width=1)
    fig.update_layout(**_CHART_LAYOUT, title="Game Impact", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), height=360)
    return fig


def plot_player_progress(player_games: pd.DataFrame, player_name: str) -> go.Figure:
    """Player grade progression chart."""
    df = player_games[player_games["playerName"] == player_name].copy()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["gameDate"], y=df["rollingGrade"], mode="lines+markers", name="Rolling Grade",
        line={**_SPLINE, "color": "#3b82f6", "width": 2.5}, marker=dict(size=6),
    ))
    fig.add_trace(go.Bar(x=df["gameDate"], y=df["points"], name="Points", opacity=0.3, marker_color="#6366f1"))
    fig.add_hrect(y0=70, y1=100, fillcolor="#22c55e", opacity=0.05, line_width=0)
    fig.add_hrect(y0=0, y1=50, fillcolor="#ef4444", opacity=0.05, line_width=0)
    fig.update_layout(**_CHART_LAYOUT, height=420, title=f"{player_name} Progression")
    return fig


def plot_rink_heatmap(df: pd.DataFrame, title: str) -> go.Figure:
    """Shot/goal location heat map on rink."""
    fig = px.density_heatmap(df, x="x", y="y", nbinsx=30, nbinsy=26, color_continuous_scale="YlOrRd", title=title)
    _draw_rink(fig)
    fig.update_layout(height=500, coloraxis_colorbar_title="Events")
    return fig


def plot_points_path(team_games: pd.DataFrame, projected_pts: float) -> go.Figure:
    """Cumulative points vs projected pace."""
    pts_path = team_games[["gameDate", "cumulativePoints"]].copy()
    pts_path["paceLine82"] = np.linspace(0, projected_pts, len(pts_path))
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=pts_path["gameDate"], y=pts_path["cumulativePoints"],
        mode="lines+markers", name="Actual",
        line={**_SPLINE, "color": "#3b82f6", "width": 2.5}, marker=dict(size=6),
    ))
    fig.add_trace(go.Scatter(
        x=pts_path["gameDate"], y=pts_path["paceLine82"],
        mode="lines", name="Projected pace",
        line=dict(dash="dash", color="#94a3b8", width=1.5),
    ))
    fig.update_layout(**_CHART_LAYOUT, height=380, title="Points Path")
    return fig


def plot_game_sim_histogram(home_dist: list[int], away_dist: list[int], home_abbrev: str, away_abbrev: str) -> go.Figure:
    """Histogram of simulated goal distributions."""
    fig = go.Figure()
    x_vals = list(range(len(home_dist)))
    fig.add_trace(go.Bar(x=x_vals, y=home_dist, name=f"{home_abbrev} Goals", marker_color="#3b82f6", opacity=0.7))
    fig.add_trace(go.Bar(x=x_vals, y=away_dist, name=f"{away_abbrev} Goals", marker_color="#ef4444", opacity=0.7))
    fig.update_layout(
        **_CHART_LAYOUT,
        title="Simulated Goal Distribution",
        xaxis_title="Goals", yaxis_title="Frequency",
        barmode="group", height=350,
    )
    return fig


def _draw_rink(fig: go.Figure) -> None:
    """Add simplified rink overlay shapes."""
    fig.update_xaxes(range=[-100, 100], showgrid=False, zeroline=False, visible=False)
    fig.update_yaxes(range=[-42.5, 42.5], showgrid=False, zeroline=False, visible=False, scaleanchor="x", scaleratio=1)
    shapes = [
        dict(type="rect", x0=-89, x1=89, y0=-42.5, y1=42.5, line=dict(color="#cbd5e1", width=2)),
        dict(type="line", x0=0, x1=0, y0=-42.5, y1=42.5, line=dict(color="#e2e8f0", width=2)),
        dict(type="line", x0=-25, x1=-25, y0=-42.5, y1=42.5, line=dict(color="#e2e8f0", width=1)),
        dict(type="line", x0=25, x1=25, y0=-42.5, y1=42.5, line=dict(color="#e2e8f0", width=1)),
        dict(type="circle", x0=-22, x1=22, y0=-22, y1=22, line=dict(color="#e2e8f0", width=1)),
    ]
    fig.update_layout(shapes=shapes, plot_bgcolor="#ffffff", paper_bgcolor="#ffffff", margin=dict(l=0, r=0, t=40, b=0))
