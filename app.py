"""NHL Intelligence Dashboard — main entry point.

This is a thin orchestrator.  All logic lives in dedicated modules:

- config/          Application constants
- utils/           Formatting, stoplights, logos, validation
- data/            Loaders, caching, team-name mappings
- providers/       NHL API providers
- models/          Projections, Monte Carlo simulation, season sim
- ui/              Tab renderers, components, charts, CSS
"""

from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

from config.settings import DEFAULT_TEAM, SEASON
from data.mappings import build_team_name_map
from models.projections import compute_outlook
from providers.metrics_provider import build_league_data, compute_team_metrics
from providers.schedule_provider import build_team_games
from ui import compare, overview, playoff_race, simulate, trends
from ui.styles import inject_css
from utils.state_detection import SeasonState, detect_season_state

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
    sim_count = st.number_input(
        "Simulations",
        min_value=100,
        max_value=5000,
        value=1000,
        step=100,
        key="sim_count",
    )
    if st.button("🔄 Refresh Simulations", key="refresh_sims"):
        st.cache_data.clear()
        st.rerun()

# ── Load league data at startup ───────────────────────────────────────────────
with st.spinner("Loading NHL standings data…"):
    try:
        standings_df, team_metrics_dict = build_league_data()
    except Exception as _e:
        standings_df = pd.DataFrame()
        team_metrics_dict: Dict[str, Dict] = {}
        st.warning(
            f"Failed to load NHL standings data (check network connection and try refreshing). "
            f"Details: {_e}"
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

# ── Load playoff series (only during playoffs) ────────────────────────────────
playoff_series: List[Dict] = []
if season_state == SeasonState.PLAYOFFS:
    try:
        from providers.playoff_provider import get_playoff_series_list

        playoff_series = get_playoff_series_list(SEASON)
    except Exception:
        playoff_series = []

# ── Run season simulation (cached in session_state) ───────────────────────────
sim_results: Optional[Dict] = None
if season_state == SeasonState.REGULAR_SEASON and not standings_df.empty:
    _sim_key = f"sim_{SEASON}_{int(sim_count)}"
    if _sim_key not in st.session_state:
        with st.spinner(f"Running {int(sim_count):,} season simulations…"):
            try:
                from models.season_sim import get_all_remaining_games, run_season_simulation

                _remaining = get_all_remaining_games(standings_df)
                st.session_state[_sim_key] = run_season_simulation(
                    standings_df, _remaining, team_metrics_dict, n_sims=int(sim_count)
                )
            except Exception as _sim_err:
                st.session_state[_sim_key] = None
    sim_results = st.session_state.get(_sim_key)

# Sorted team list; ensure DEFAULT is first if available
all_teams: List[str] = (
    sorted(standings_df["teamAbbrev"].dropna().unique().tolist())
    if not standings_df.empty
    else [DEFAULT_TEAM]
)
if DEFAULT_TEAM in all_teams:
    all_teams = [DEFAULT_TEAM] + [t for t in all_teams if t != DEFAULT_TEAM]

team_name_map = build_team_name_map(standings_df)

# ── Header ────────────────────────────────────────────────────────────────────
hdr_left, hdr_right = st.columns([4, 1])
with hdr_left:
    st.markdown(
        "<h1 style='margin-bottom:0;font-size:1.75rem;'>🏒 NHL Intelligence Dashboard</h1>",
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
sel_metrics = team_metrics_dict.get(selected_team, compute_team_metrics(selected_team, standings_df))
sel_outlook = compute_outlook(selected_team, standings_df, team_metrics_dict)

# Load detailed game data for selected team
with st.spinner(f"Loading {selected_team} game data…"):
    try:
        sel_schedule, sel_tg = build_team_games(selected_team)
    except Exception:
        sel_schedule = pd.DataFrame()
        sel_tg = pd.DataFrame()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_ov, tab_tr, tab_pl, tab_cmp, tab_sim = st.tabs(
    ["📊 Overview", "📈 Trends", "🏆 Playoff Race", "⚖️ Compare", "🎲 Simulate"]
)

with tab_ov:
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

with tab_tr:
    trends.render(
        selected_team=selected_team,
        sel_tg=sel_tg,
        sel_schedule=sel_schedule,
        sel_outlook=sel_outlook,
    )

with tab_pl:
    playoff_race.render(
        selected_team=selected_team,
        sel_metrics=sel_metrics,
        sel_outlook=sel_outlook,
        standings_df=standings_df,
        team_metrics_dict=team_metrics_dict,
        team_name_map=team_name_map,
        season_state=season_state,
        sim_results=sim_results,
        playoff_series=playoff_series,
    )

with tab_cmp:
    compare.render(
        all_teams=all_teams,
        standings_df=standings_df,
        team_metrics_dict=team_metrics_dict,
        team_name_map=team_name_map,
    )

with tab_sim:
    simulate.render(
        all_teams=all_teams,
        standings_df=standings_df,
        team_metrics_dict=team_metrics_dict,
    )
