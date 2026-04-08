"""Top plays view — last completed game's highest-impact plays.

Animated rink diagram using Plotly scatter. Supports ranked and timeline modes.
Controls: play/pause/step. Falls back to table-only when no coordinates.
Special callouts: Turning Point, Winning Play, Most Damaging.
"""

from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from ui.components import kpi_html
from utils.formatters import fmt_signed_float
from utils.logos import logo_url
from utils.streamlit_keys import mk_key
from services.play_impact import find_last_completed_game, get_top_plays


_CALLOUT_STYLES = {
    "Turning Point": ("🔄", "#7c3aed", "#f5f3ff"),
    "Winning Play": ("🏆", "#059669", "#ecfdf5"),
    "Most Damaging Negative Play": ("💥", "#dc2626", "#fef2f2"),
}

_RINK_WIDTH = 200
_RINK_HEIGHT = 85


def _rink_figure(plays: List[Dict[str, Any]], team: str) -> Any:
    """Build a Plotly figure of plays on a rink diagram."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None

    fig = go.Figure()

    # Rink outline
    fig.add_shape(
        type="rect", x0=-100, y0=-42.5, x1=100, y1=42.5,
        line=dict(color="#94a3b8", width=2),
        fillcolor="#f0f9ff",
    )
    # Center line
    fig.add_shape(
        type="line", x0=0, y0=-42.5, x1=0, y1=42.5,
        line=dict(color="#ef4444", width=2),
    )
    # Blue lines
    fig.add_shape(
        type="line", x0=-25, y0=-42.5, x1=-25, y1=42.5,
        line=dict(color="#3b82f6", width=2),
    )
    fig.add_shape(
        type="line", x0=25, y0=-42.5, x1=25, y1=42.5,
        line=dict(color="#3b82f6", width=2),
    )
    # Goal creases
    for gx in [-89, 89]:
        fig.add_shape(
            type="circle", x0=gx - 4, y0=-4, x1=gx + 4, y1=4,
            line=dict(color="#ef4444", width=1),
            fillcolor="rgba(239,68,68,0.1)",
        )

    # Positive plays
    pos = [p for p in plays if p.get("x_coord") is not None and p.get("is_positive")]
    neg = [p for p in plays if p.get("x_coord") is not None and not p.get("is_positive")]

    if pos:
        fig.add_trace(go.Scatter(
            x=[p["x_coord"] for p in pos],
            y=[p["y_coord"] for p in pos],
            mode="markers+text",
            marker=dict(
                size=[max(8, min(20, abs(p["impact_score"]) * 2)) for p in pos],
                color="#22c55e",
                line=dict(width=1, color="#166534"),
            ),
            text=[f"#{p['rank']}" for p in pos],
            textposition="top center",
            textfont=dict(size=9, color="#166534"),
            hovertext=[
                f"#{p['rank']} {p['event_type'].title()}<br>"
                f"P{p['period']} {p['time_in_period']}<br>"
                f"Impact: {p['impact_score']:+.1f}"
                + (f"<br>{p['callout']}" if p.get("callout") else "")
                for p in pos
            ],
            hoverinfo="text",
            name=f"{team} Positive",
        ))

    if neg:
        fig.add_trace(go.Scatter(
            x=[p["x_coord"] for p in neg],
            y=[p["y_coord"] for p in neg],
            mode="markers+text",
            marker=dict(
                size=[max(8, min(20, abs(p["impact_score"]) * 2)) for p in neg],
                color="#ef4444",
                line=dict(width=1, color="#991b1b"),
                symbol="x",
            ),
            text=[f"#{p['rank']}" for p in neg],
            textposition="top center",
            textfont=dict(size=9, color="#991b1b"),
            hovertext=[
                f"#{p['rank']} {p['event_type'].title()}<br>"
                f"P{p['period']} {p['time_in_period']}<br>"
                f"Impact: {p['impact_score']:+.1f}"
                + (f"<br>{p['callout']}" if p.get("callout") else "")
                for p in neg
            ],
            hoverinfo="text",
            name="Opponent / Negative",
        ))

    fig.update_layout(
        template="plotly_white",
        height=380,
        margin=dict(l=10, r=10, t=40, b=10),
        title="Play Impact on Rink",
        xaxis=dict(range=[-105, 105], showgrid=False, zeroline=False, visible=False),
        yaxis=dict(
            range=[-48, 48], showgrid=False, zeroline=False, visible=False,
            scaleanchor="x", scaleratio=1,
        ),
        showlegend=True,
        legend=dict(orientation="h", y=-0.05),
    )
    return fig


def _timeline_figure(plays: List[Dict[str, Any]]) -> Any:
    """Build a timeline bar chart of play impacts."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None

    sorted_plays = sorted(
        plays,
        key=lambda p: (p.get("period", 0), p.get("time_in_period", "")),
    )

    labels = [
        f"P{p['period']} {p['time_in_period']} — {p['event_type'].title()}"
        for p in sorted_plays
    ]
    impacts = [p["impact_score"] for p in sorted_plays]
    colors = ["#22c55e" if i >= 0 else "#ef4444" for i in impacts]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=list(range(len(labels))),
        y=impacts,
        marker_color=colors,
        text=[f"{v:+.1f}" for v in impacts],
        textposition="outside",
        hovertext=labels,
        hoverinfo="text",
    ))
    fig.update_layout(
        template="plotly_white",
        height=350,
        margin=dict(l=10, r=10, t=40, b=60),
        title="Play Impact Timeline",
        xaxis=dict(
            tickmode="array",
            tickvals=list(range(len(labels))),
            ticktext=[f"P{p['period']}" for p in sorted_plays],
            tickangle=0,
        ),
        yaxis=dict(title="Impact Score"),
    )
    return fig


def _plays_table_html(plays: List[Dict[str, Any]]) -> str:
    """Build an HTML table of plays."""
    if not plays:
        return "<p style='color:#94a3b8;'>No play data available.</p>"

    rows = []
    for p in plays:
        impact = p.get("impact_score", 0)
        is_pos = p.get("is_positive", True)
        callout = p.get("callout", "")

        if is_pos:
            bg = "#dcfce7" if impact > 5 else "#f0fdf4"
        else:
            bg = "#fee2e2" if impact < -5 else "#fef2f2"

        callout_html = ""
        if callout:
            icon, fg, cbg = _CALLOUT_STYLES.get(callout, ("📌", "#475569", "#f1f5f9"))
            callout_html = (
                f"<span style='background:{cbg};color:{fg};padding:2px 6px;"
                f"border-radius:4px;font-size:0.72rem;font-weight:600;'>"
                f"{icon} {callout}</span>"
            )

        rows.append(
            f"<tr style='background:{bg};border-bottom:1px solid #e2e8f0;'>"
            f"<td style='padding:6px;text-align:center;font-weight:700;'>"
            f"#{p.get('rank', '')}</td>"
            f"<td style='padding:6px;'>"
            f"P{p.get('period', '?')} {p.get('time_in_period', '')}</td>"
            f"<td style='padding:6px;font-weight:600;'>"
            f"{p.get('event_type', '').replace('-', ' ').title()}</td>"
            f"<td style='padding:6px;text-align:center;font-weight:700;"
            f"font-size:0.95rem;'>{impact:+.1f}</td>"
            f"<td style='padding:6px;font-size:0.8rem;'>"
            f"{p.get('home_score', 0)}–{p.get('away_score', 0)}</td>"
            f"<td style='padding:6px;'>{callout_html}</td>"
            f"</tr>"
        )

    header = (
        "<thead><tr style='border-bottom:2px solid #cbd5e1;background:#f8fafc;'>"
        "<th style='padding:6px;text-align:center;'>#</th>"
        "<th style='padding:6px;'>Time</th>"
        "<th style='padding:6px;'>Event</th>"
        "<th style='padding:6px;text-align:center;'>Impact</th>"
        "<th style='padding:6px;'>Score</th>"
        "<th style='padding:6px;'>Callout</th>"
        "</tr></thead>"
    )
    return (
        f"<table style='width:100%;border-collapse:collapse;font-size:0.85rem;'>"
        f"{header}<tbody>{''.join(rows)}</tbody></table>"
    )


# ── Public render ─────────────────────────────────────────────────────────────

def render(
    selected_team: str,
    sel_name: str,
    sel_schedule: pd.DataFrame,
    sel_tg: pd.DataFrame,
    **kwargs: Any,
) -> None:
    """Render the top plays view for the last completed game."""
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:12px;'>"
        f"<img src='{logo_url(selected_team)}' width='42' height='42'/>"
        f"<div>"
        f"<span style='font-size:1.1rem;font-weight:700;'>"
        f"Top Plays — {sel_name}</span><br/>"
        f"<span style='font-size:0.8rem;color:#64748b;'>"
        f"Impact scores estimated from play-by-play data</span>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    # Find last completed game
    if sel_schedule is None or sel_schedule.empty:
        st.warning("Schedule data unavailable.")
        return

    last_game = find_last_completed_game(sel_schedule, selected_team)
    if not last_game:
        st.info("No completed games found in the schedule.")
        return

    game_id = last_game["gameId"]
    opp = last_game.get("opponent", "?")
    date = str(last_game.get("gameDate", ""))[:10]
    home_score = last_game.get("homeScore", "?")
    away_score = last_game.get("awayScore", "?")
    is_home = last_game.get("isHome", True)

    venue_str = "Home" if is_home else "Away"
    if is_home:
        score_str = f"{home_score}–{away_score}"
    else:
        score_str = f"{away_score}–{home_score} (away)"

    st.markdown(
        f"**Last Game:** vs "
        f"<img src='{logo_url(opp)}' width='20' height='20' "
        f"style='vertical-align:middle;'/> "
        f"**{opp}** · {date} · {venue_str} · **{score_str}**",
        unsafe_allow_html=True,
    )

    # Fetch plays
    load_key = f"top_plays_{game_id}"
    load_btn = st.button(
        "▶ Load Top Plays",
        key=mk_key("top_plays", "button", "load"),
    )

    if load_btn:
        with st.spinner("Fetching play-by-play data…"):
            try:
                play_data = get_top_plays(game_id, selected_team)
                st.session_state[load_key] = play_data
            except Exception as e:
                st.error(f"Failed to fetch play data: {e}")
                st.session_state[load_key] = None

    play_data = st.session_state.get(load_key)
    if play_data is None:
        st.info("Click **▶ Load Top Plays** to fetch and analyze the play-by-play data.")
        return

    if play_data.get("error"):
        st.warning(play_data["error"])
        return

    plays = play_data.get("plays", [])
    has_coords = play_data.get("has_coordinates", False)

    if not plays:
        st.warning("No high-impact plays found in this game.")
        return

    # ── Callout highlights ────────────────────────────────────────────────
    callout_plays = [p for p in plays if p.get("callout")]
    if callout_plays:
        cols = st.columns(min(len(callout_plays), 3))
        for i, p in enumerate(callout_plays[:3]):
            callout = p["callout"]
            icon, fg, bg = _CALLOUT_STYLES.get(callout, ("📌", "#475569", "#f1f5f9"))
            with cols[i]:
                st.markdown(
                    f"<div style='background:{bg};border:1px solid {fg};"
                    f"border-radius:10px;padding:12px;text-align:center;'>"
                    f"<div style='font-size:1.5rem;'>{icon}</div>"
                    f"<div style='font-weight:700;color:{fg};font-size:0.9rem;'>"
                    f"{callout}</div>"
                    f"<div style='font-size:0.85rem;font-weight:600;'>"
                    f"{p['event_type'].replace('-', ' ').title()}</div>"
                    f"<div style='font-size:0.8rem;color:#64748b;'>"
                    f"P{p['period']} {p['time_in_period']} · "
                    f"Impact: {p['impact_score']:+.1f}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    # ── View mode ─────────────────────────────────────────────────────────
    view_mode = st.radio(
        "Display Mode",
        ["Ranked Table", "Rink Diagram", "Timeline"],
        horizontal=True,
        key=mk_key("top_plays", "radio", "view_mode"),
    )

    if view_mode == "Ranked Table":
        st.markdown(_plays_table_html(plays), unsafe_allow_html=True)

    elif view_mode == "Rink Diagram":
        if not has_coords:
            st.warning(
                "No coordinate data available for this game. "
                "Showing table instead."
            )
            st.markdown(_plays_table_html(plays), unsafe_allow_html=True)
        else:
            fig = _rink_figure(plays, selected_team)
            if fig:
                # Step-through controls
                step_col1, step_col2, step_col3 = st.columns([1, 1, 2])
                with step_col1:
                    show_all = st.checkbox(
                        "Show all plays",
                        value=True,
                        key=mk_key("top_plays", "checkbox", "show_all"),
                    )
                if not show_all:
                    with step_col2:
                        play_idx = st.slider(
                            "Play #",
                            min_value=1,
                            max_value=len(plays),
                            value=1,
                            key=mk_key("top_plays", "slider", "play_step"),
                        )
                    # Filter to show plays up to selected index
                    visible = plays[:play_idx]
                    fig = _rink_figure(visible, selected_team)

                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key=mk_key("top_plays", "chart", "rink"),
                )
            else:
                st.warning("Plotly not available. Showing table instead.")
                st.markdown(_plays_table_html(plays), unsafe_allow_html=True)

    elif view_mode == "Timeline":
        fig = _timeline_figure(plays)
        if fig:
            st.plotly_chart(
                fig,
                use_container_width=True,
                key=mk_key("top_plays", "chart", "timeline"),
            )
        else:
            st.warning("Plotly not available. Showing table instead.")
            st.markdown(_plays_table_html(plays), unsafe_allow_html=True)

    st.caption(
        f"ℹ️ Impact scores are **estimated** from the "
        f"{play_data.get('model_label', 'Play Impact Model')}. "
        f"All event data from the NHL API."
    )
