"""Top Plays view — ranked play-by-play impact analysis for the last game."""

import streamlit as st

from services.play_impact import (
    get_last_completed_game, compute_play_impacts, rank_top_plays,
)
from ui.components import kpi_html
from utils.formatters import fmt_number
from utils.logos import logo_url
from utils.streamlit_keys import mk_key
from utils.validators import safe_numeric, safe_int


_PAGE = "top_plays"


def _logo_img(abbrev: str, size: int = 28) -> str:
    return (
        f"<img src='{logo_url(abbrev)}' width='{size}' height='{size}' "
        f"style='object-fit:contain;vertical-align:middle;'/>"
    )


def _badge(text: str, color: str) -> str:
    return (
        f"<span style='display:inline-block;padding:2px 6px;border-radius:4px;"
        f"background:{color};color:#fff;font-size:0.7rem;font-weight:700;"
        f"margin-left:4px;'>{text}</span>"
    )


def _impact_color(score: float, positive: bool) -> str:
    if positive:
        return "#bbf7d0" if score >= 1.5 else "#d1fae5"
    return "#fecaca" if score >= 1.5 else "#fed7aa"


# ── Main render ───────────────────────────────────────────────────────────────

def render(selected_team, sel_schedule, sel_tg):
    """Render the Top Plays tab."""
    try:
        _render_inner(selected_team, sel_schedule, sel_tg)
    except Exception as exc:
        st.error(f"Top Plays view could not be rendered: {exc}")


def _render_inner(selected_team, sel_schedule, sel_tg):
    st.markdown("#### Top Plays — Play Impact Analysis")
    st.caption("Play Impact Model based on API play-by-play data")

    # Find last completed game
    schedule_for_lookup = sel_tg if sel_tg is not None and not sel_tg.empty else sel_schedule
    if schedule_for_lookup is None or schedule_for_lookup.empty:
        st.info("Schedule data unavailable — cannot identify last game.")
        return

    last_game = get_last_completed_game(selected_team, schedule_for_lookup)
    if not last_game:
        st.info("No completed games found for this team.")
        return

    game_id = last_game.get("gameId")
    opp = last_game.get("opponent", "???")
    date = str(last_game.get("gameDate", ""))[:10]
    score = last_game.get("score", "")

    # Game header
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:12px;margin-bottom:8px;'>"
        f"{_logo_img(selected_team, 36)} vs {_logo_img(opp, 36)}"
        f"<span style='font-weight:700;font-size:1rem;'>{date}</span>"
        f"<span style='font-size:0.9rem;color:#64748b;'>{score}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Button-triggered load
    cache_key = f"tp_{selected_team}_{game_id}"
    if st.button("Load Top Plays", key=mk_key(_PAGE, "load_btn")):
        with st.spinner("Analyzing play-by-play data…"):
            plays = compute_play_impacts(game_id, selected_team)
            ranked = rank_top_plays(plays, n=10)
        st.session_state[cache_key] = {"plays": plays, "ranked": ranked}

    data = st.session_state.get(cache_key)
    if not data:
        st.info("Press **Load Top Plays** to analyze the game.")
        return

    plays = data.get("plays", [])
    ranked = data.get("ranked", [])

    if not ranked:
        st.warning("No play impact data available for this game.")
        return

    # ── Ranked play table ─────────────────────────────────────────────────
    _render_play_table(ranked)

    # ── Rink diagram section ──────────────────────────────────────────────
    plays_with_coords = [p for p in plays if p.get("x") is not None and p.get("y") is not None]
    if plays_with_coords:
        with st.expander("Rink Diagram (Play Positions)"):
            _render_rink_diagram(plays_with_coords)
    else:
        st.info("No coordinate data available for rink diagram — showing ranked table only.")


def _render_play_table(ranked):
    """Render the ranked plays as an HTML table with badges."""
    html = (
        "<table style='width:100%;border-collapse:collapse;font-size:0.82rem;'>"
        "<tr style='border-bottom:2px solid #e2e8f0;'>"
        "<th style='padding:4px 6px;'>#</th>"
        "<th style='padding:4px 6px;'>Period</th>"
        "<th style='padding:4px 6px;'>Time</th>"
        "<th style='padding:4px 6px;text-align:left;'>Event</th>"
        "<th style='padding:4px 6px;text-align:left;'>Player</th>"
        "<th style='padding:4px 6px;'>Impact</th>"
        "<th style='padding:4px 6px;'>+/−</th>"
        "<th style='padding:4px 6px;'>Badge</th>"
        "</tr>"
    )

    for i, p in enumerate(ranked, 1):
        period = p.get("period", "—")
        time = p.get("time", "—")
        event = p.get("event_type", p.get("description", "—"))
        player = p.get("player", "—")
        impact = safe_numeric(p.get("impact_score", 0))
        positive = p.get("positive", impact >= 0)
        bg = _impact_color(abs(impact), positive)
        sign = "+" if positive else "−"

        # Determine badge
        badges = ""
        if i == 1:
            if positive:
                badges = _badge("Winning Play", "#22c55e")
            else:
                badges = _badge("Most Damaging", "#ef4444")
        if i <= 3 and abs(impact) >= 1.5:
            badges += _badge("Turning Point", "#8b5cf6")

        html += (
            f"<tr style='border-bottom:1px solid #f1f5f9;'>"
            f"<td style='padding:4px 6px;text-align:center;font-weight:700;'>{i}</td>"
            f"<td style='padding:4px 6px;text-align:center;'>P{period}</td>"
            f"<td style='padding:4px 6px;text-align:center;'>{time}</td>"
            f"<td style='padding:4px 6px;'>{event}</td>"
            f"<td style='padding:4px 6px;font-weight:600;'>{player}</td>"
            f"<td style='padding:4px 6px;text-align:center;font-weight:700;"
            f"background:{bg};'>{abs(impact):.2f}</td>"
            f"<td style='padding:4px 6px;text-align:center;font-weight:700;"
            f"color:{'#22c55e' if positive else '#ef4444'};'>{sign}</td>"
            f"<td style='padding:4px 6px;'>{badges}</td>"
            f"</tr>"
        )

    html += "</table>"
    st.markdown(html, unsafe_allow_html=True)


def _render_rink_diagram(plays):
    """Render a simple Plotly scatter plot on a rink-like background."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        st.info("Plotly is required for the rink diagram. Install with: pip install plotly")
        return

    xs = [p["x"] for p in plays]
    ys = [p["y"] for p in plays]
    impacts = [safe_numeric(p.get("impact_score", 0)) for p in plays]
    labels = [
        f"{p.get('event_type', '')} - {p.get('player', '')} ({p.get('impact_score', 0):+.2f})"
        for p in plays
    ]
    colors = ["#22c55e" if p.get("positive", True) else "#ef4444" for p in plays]
    sizes = [max(6, min(20, abs(imp) * 6)) for imp in impacts]

    fig = go.Figure()

    # Rink outline (simplified)
    fig.add_shape(type="rect", x0=-100, y0=-42.5, x1=100, y1=42.5,
                  line=dict(color="#94a3b8", width=2), fillcolor="#f8fafc")
    fig.add_shape(type="line", x0=0, y0=-42.5, x1=0, y1=42.5,
                  line=dict(color="#ef4444", width=2))

    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers",
        marker=dict(size=sizes, color=colors, opacity=0.8,
                    line=dict(width=1, color="#fff")),
        text=labels, hoverinfo="text",
    ))

    fig.update_layout(
        height=320, margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(range=[-105, 105], showgrid=False, zeroline=False, visible=False),
        yaxis=dict(range=[-50, 50], showgrid=False, zeroline=False, visible=False,
                   scaleanchor="x"),
        showlegend=False, plot_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(fig, use_container_width=True,
                    key=mk_key(_PAGE, "rink_chart"))
