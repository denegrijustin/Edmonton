"""NHL Intelligence Dashboard — main entry point.

This is a thin orchestrator.  All logic lives in dedicated modules:

- config/          Application constants
- utils/           Formatting, stoplights, logos, validation
- data/            Loaders, caching, team-name mappings
- providers/       NHL API providers, MoneyPuck
- models/          Projections, Monte Carlo simulation
- ui/              Tab renderers, components, charts, CSS
"""

from typing import Dict, List

import pandas as pd
import streamlit as st

from config.settings import DEFAULT_TEAM
from data.mappings import build_team_name_map
from models.projections import compute_outlook
from providers.metrics_provider import build_league_data, compute_team_metrics
from providers.moneypuck_provider import load_moneypuck_cached
from providers.schedule_provider import build_team_games
from ui import compare, overview, playoff_race, simulate, trends
from ui.styles import inject_css

# ── Page config (must be first Streamlit command) ─────────────────────────────
st.set_page_config(
    page_title="NHL Intelligence Dashboard",
    page_icon="🏒",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_css()

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

# Pre-load MoneyPuck playoff odds for all teams at startup
try:
    load_moneypuck_cached()
except Exception:
    pass  # Non-fatal — degraded mode handled in the Playoff Race tab

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
        team_name_map=team_name_map,
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
