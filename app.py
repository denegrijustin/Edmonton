"""NHL Intelligence Dashboard — main entry point.

Thin orchestrator.  All logic lives in dedicated modules:

- config/          Application constants
- utils/           Formatting, stoplights, logos, validation
- data/            Loaders, caching, team-name mappings
- providers/       NHL API providers
- models/          Projections, Monte Carlo simulation, season sim
- services/        Playoff state, series tracking, simulation wrapper,
                   player impact, play impact
- views/           Tab renderers (overview, standings, schedule, comparison,
                   playoff_race, bracket, simulator, player_impact, top_plays)
- ui/              Shared components, charts, CSS

Key design rules:
- Initial page load is fast: only standings + schedule are fetched.
- Simulations run ONLY on explicit user action (button click).
- All model outputs are clearly labeled as Projected/Simulated/Estimated.
- Never invent, fabricate, or hardcode standings, schedule, or stat data.
"""

from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from config.settings import DEFAULT_TEAM, SEASON
from data.mappings import build_team_name_map
from models.projections import compute_outlook
from providers.metrics_provider import build_league_data, compute_team_metrics
from providers.schedule_provider import build_team_games
from services.playoff_state import PlayoffState, detect_playoff_state
from services.series_tracker import build_series_from_games
from ui.styles import inject_css
from utils.logos import logo_url
from utils.state_detection import SeasonState, detect_season_state
from views import (
    bracket,
    comparison,
    overview,
    player_impact,
    playoff_race,
    schedule,
    simulator,
    standings,
    top_plays,
)

# ── Page config (must be first Streamlit command) ─────────────────────────────
st.set_page_config(
    page_title="NHL Intelligence Dashboard",
    page_icon="🏒",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_css()

# ── Sidebar settings ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    state_override = st.selectbox(
        "Season Mode",
        ["Auto", "Force Regular Season", "Force Playoffs", "Force Offseason"],
        key="state_override",
    )
    if st.button("🔄 Refresh Data", key="refresh_data"):
        st.cache_data.clear()
        st.rerun()

# ── Load league data at startup (fast — standings only) ───────────────────────
with st.spinner("Loading NHL standings…"):
    try:
        standings_df, team_metrics_dict = build_league_data()
    except Exception as _e:
        standings_df = pd.DataFrame()
        team_metrics_dict: Dict[str, Dict] = {}
        st.warning(
            f"Failed to load NHL standings (check network). Details: {_e}"
        )

# ── Detect season state ───────────────────────────────────────────────────────
_auto_state = detect_season_state(SEASON, standings_df)
_state_map = {
    "Auto": _auto_state,
    "Force Regular Season": SeasonState.REGULAR_SEASON,
    "Force Playoffs": SeasonState.PLAYOFFS,
    "Force Offseason": SeasonState.OFFSEASON,
}
season_state: SeasonState = _state_map.get(state_override, _auto_state)

# ── Detect playoff state (from schedule metadata, not failed API) ─────────────
playoff_state_obj = PlayoffState(playoffs_started=False)
series_list: List[Dict[str, Any]] = []

if season_state == SeasonState.PLAYOFFS:
    try:
        playoff_state_obj = detect_playoff_state(standings_df, season=SEASON)
        if playoff_state_obj.playoffs_started:
            series_list = build_series_from_games(
                playoff_state_obj.playoff_games
            )
    except Exception:
        pass

# NO simulation at startup — simulations are on-demand only.

# ── Team list ─────────────────────────────────────────────────────────────────
all_teams: List[str] = (
    sorted(standings_df["teamAbbrev"].dropna().unique().tolist())
    if not standings_df.empty
    else [DEFAULT_TEAM]
)
if DEFAULT_TEAM in all_teams:
    all_teams = [DEFAULT_TEAM] + [t for t in all_teams if t != DEFAULT_TEAM]

team_name_map = build_team_name_map(standings_df)

# ── Header with logo ─────────────────────────────────────────────────────────
hdr_left, hdr_right = st.columns([4, 1])
with hdr_left:
    st.markdown(
        "<h1 style='margin-bottom:0;font-size:1.6rem;'>🏒 NHL Intelligence Dashboard</h1>",
        unsafe_allow_html=True,
    )
with hdr_right:
    selected_team = st.selectbox(
        "Team",
        all_teams,
        index=0,
        key="global_team",
        label_visibility="collapsed",
    )

sel_name = team_name_map.get(selected_team, selected_team)
sel_metrics = team_metrics_dict.get(
    selected_team, compute_team_metrics(selected_team, standings_df)
)
sel_outlook = compute_outlook(selected_team, standings_df, team_metrics_dict)

# Show selected team logo + abbreviation in compact header
st.markdown(
    f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:6px;'>"
    f"<img src='{logo_url(selected_team)}' width='36' height='36'/>"
    f"<span style='font-size:1.1rem;font-weight:700;'>{sel_name}</span>"
    f"<span style='color:#64748b;font-size:0.9rem;'>{selected_team}</span>"
    f"</div>",
    unsafe_allow_html=True,
)

# Load schedule for selected team (lightweight)
with st.spinner(f"Loading {selected_team} schedule…"):
    try:
        sel_schedule, sel_tg = build_team_games(selected_team)
    except Exception:
        sel_schedule = pd.DataFrame()
        sel_tg = pd.DataFrame()

# ── Build tab list based on season state ──────────────────────────────────────
_TAB_LABELS = [
    "📊 Overview",
    "🏆 Standings",
    "📅 Schedule",
    "⚖️ Compare",
    "🏒 Playoff Race",
    "🗂️ Bracket",
    "🎲 Simulator",
    "📈 Player Impact",
    "🎬 Top Plays",
]

tabs = st.tabs(_TAB_LABELS)

with tabs[0]:  # Overview
    overview.render(
        selected_team=selected_team,
        sel_name=sel_name,
        sel_metrics=sel_metrics,
        sel_outlook=sel_outlook,
        sel_schedule=sel_schedule,
        sel_tg=sel_tg,
        standings_df=standings_df,
        team_metrics_dict=team_metrics_dict,
        team_name_map=team_name_map,
    )

with tabs[1]:  # Standings
    standings.render(
        selected_team=selected_team,
        standings_df=standings_df,
        team_metrics_dict=team_metrics_dict,
        team_name_map=team_name_map,
    )

with tabs[2]:  # Schedule
    schedule.render(
        selected_team=selected_team,
        sel_name=sel_name,
        sel_schedule=sel_schedule,
        sel_tg=sel_tg,
        standings_df=standings_df,
        team_metrics_dict=team_metrics_dict,
        team_name_map=team_name_map,
    )

with tabs[3]:  # Compare
    comparison.render(
        all_teams=all_teams,
        standings_df=standings_df,
        team_metrics_dict=team_metrics_dict,
        team_name_map=team_name_map,
    )

with tabs[4]:  # Playoff Race
    playoff_race.render(
        selected_team=selected_team,
        sel_name=sel_name,
        sel_metrics=sel_metrics,
        sel_outlook=sel_outlook,
        standings_df=standings_df,
        team_metrics_dict=team_metrics_dict,
        team_name_map=team_name_map,
        season_state=season_state,
    )

with tabs[5]:  # Bracket
    bracket.render(
        selected_team=selected_team,
        standings_df=standings_df,
        team_metrics_dict=team_metrics_dict,
        team_name_map=team_name_map,
        season_state=season_state,
        playoff_state_obj=playoff_state_obj,
        series_list=series_list,
        sel_outlook=sel_outlook,
    )

with tabs[6]:  # Simulator
    simulator.render(
        all_teams=all_teams,
        standings_df=standings_df,
        team_metrics_dict=team_metrics_dict,
        team_name_map=team_name_map,
        season_state=season_state,
        series_list=series_list,
    )

with tabs[7]:  # Player Impact
    player_impact.render(
        selected_team=selected_team,
        sel_name=sel_name,
        sel_tg=sel_tg,
        team_name_map=team_name_map,
    )

with tabs[8]:  # Top Plays
    top_plays.render(
        selected_team=selected_team,
        sel_name=sel_name,
        sel_schedule=sel_schedule,
        sel_tg=sel_tg,
    )
