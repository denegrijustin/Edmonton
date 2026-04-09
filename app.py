"""NHL Intelligence Dashboard — main entry point.

This is a thin orchestrator.  All logic lives in dedicated modules:

- config/          Application constants
- utils/           Formatting, stoplights, logos, validation
- data/            Loaders, caching, team-name mappings
- api/             Unified NHL API client
- providers/       NHL API providers (legacy)
- models/          Projections, Monte Carlo simulation, season sim
- services/        Business logic: mode detection, odds, simulation, etc.
- views/           Tab / page renderers (new, team-first, playoff-focused)
- ui/              Shared components, charts, CSS
"""

from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

from config.settings import DEFAULT_TEAM, SEASON
from data.mappings import build_team_name_map
from models.projections import compute_outlook
from providers.metrics_provider import build_league_data, compute_team_metrics
from providers.schedule_provider import build_team_games
from services.mode_state import AppMode, detect_app_mode, get_safe_mode, update_mode_state
from services.live_refresh import get_live_game_state, should_auto_refresh, get_refresh_interval
from ui.styles import inject_css
from utils.logos import logo_url
from views import (
    overview,
    standings,
    schedule,
    comparison,
    playoff_race,
    bracket,
    simulator,
    player_impact,
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
        [
            "Auto",
            "Force Regular Season",
            "Force Playoff Race",
            "Force Playoffs",
            "Force Offseason",
        ],
        key="state_override",
    )
    sim_count = st.number_input(
        "Simulations (season sim)",
        min_value=100,
        max_value=5000,
        value=250,
        step=100,
        key="sim_count",
    )

    auto_refresh_on = st.checkbox("Live Auto-Refresh", value=False, key="auto_refresh_on")
    refresh_speed = st.radio(
        "Refresh Speed", ["Standard", "Faster"], horizontal=True, key="refresh_speed"
    )

    if st.button("🔄 Refresh Data", key="refresh_sims"):
        st.cache_data.clear()
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# STARTUP PHASE 1: Lightweight league data
# ══════════════════════════════════════════════════════════════════════════════
with st.spinner("Loading NHL standings…"):
    try:
        standings_df, team_metrics_dict = build_league_data()
    except Exception as _e:
        standings_df = pd.DataFrame()
        team_metrics_dict: Dict[str, Dict] = {}
        st.warning(
            f"Failed to load NHL standings data (check network and retry). "
            f"Details: {_e}"
        )

# ── Detect app mode (fail-safe) ──────────────────────────────────────────────
_auto_mode = detect_app_mode(SEASON, standings_df)

_mode_map = {
    "Auto": _auto_mode,
    "Force Regular Season": AppMode.REGULAR_SEASON,
    "Force Playoff Race": AppMode.PLAYOFF_RACE,
    "Force Playoffs": AppMode.PLAYOFFS,
    "Force Offseason": AppMode.OFFSEASON,
}
app_mode: AppMode = _mode_map.get(state_override, _auto_mode)

# Persist last confirmed valid mode in session state
if app_mode != AppMode.SAFE_FALLBACK:
    update_mode_state(st.session_state, app_mode)
elif "last_confirmed_mode" in st.session_state:
    app_mode = get_safe_mode(st.session_state)

# ── Load playoff series (only during playoffs) ────────────────────────────────
playoff_series: List[Dict] = []
if app_mode == AppMode.PLAYOFFS:
    try:
        from providers.playoff_provider import get_playoff_series_list

        playoff_series = get_playoff_series_list(SEASON)
    except Exception:
        playoff_series = []

# ── Season simulation: NOT run at startup; cached on demand ───────────────────
sim_results: Optional[Dict] = None

# Sorted team list; ensure DEFAULT is first if available
all_teams: List[str] = (
    sorted(standings_df["teamAbbrev"].dropna().unique().tolist())
    if not standings_df.empty
    else [DEFAULT_TEAM]
)
if DEFAULT_TEAM in all_teams:
    all_teams = [DEFAULT_TEAM] + [t for t in all_teams if t != DEFAULT_TEAM]

team_name_map = build_team_name_map(standings_df)

# ══════════════════════════════════════════════════════════════════════════════
# HEADER — Logo-first team selector
# ══════════════════════════════════════════════════════════════════════════════
hdr_left, hdr_mid, hdr_right = st.columns([3, 1, 2])
with hdr_left:
    st.markdown(
        "<h1 style='margin-bottom:0;font-size:1.75rem;'>🏒 NHL Intelligence Dashboard</h1>",
        unsafe_allow_html=True,
    )
with hdr_mid:
    _mode_labels = {
        AppMode.REGULAR_SEASON: "🏒 Regular Season",
        AppMode.PLAYOFF_RACE: "🔥 Playoff Race",
        AppMode.PLAYOFFS: "🏆 Playoffs",
        AppMode.OFFSEASON: "🏁 Offseason",
        AppMode.SAFE_FALLBACK: "⚠️ Safe Mode",
    }
    st.markdown(
        f"<div style='text-align:center;padding:8px 0;font-size:0.85rem;"
        f"color:#64748b;font-weight:600;'>{_mode_labels.get(app_mode, '')}</div>",
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

# Show selected team logo prominently
_sel_logo = logo_url(selected_team)
_sel_name = team_name_map.get(selected_team, selected_team)
st.markdown(
    f"<div style='display:flex;align-items:center;gap:12px;margin:4px 0 8px 0;'>"
    f"<img src='{_sel_logo}' width='42' height='42' style='object-fit:contain;'/>"
    f"<span style='font-size:1.15rem;font-weight:700;'>{_sel_name}</span>"
    f"<span style='font-size:0.85rem;color:#64748b;'>({selected_team})</span>"
    f"</div>",
    unsafe_allow_html=True,
)

# ══════════════════════════════════════════════════════════════════════════════
# STARTUP PHASE 2: Selected-team detail (only for chosen team)
# ══════════════════════════════════════════════════════════════════════════════
sel_name = _sel_name
sel_metrics = team_metrics_dict.get(selected_team, compute_team_metrics(selected_team, standings_df))
sel_outlook = compute_outlook(selected_team, standings_df, team_metrics_dict)

with st.spinner(f"Loading {selected_team} game data…"):
    try:
        sel_schedule, sel_tg = build_team_games(selected_team)
    except Exception:
        sel_schedule = pd.DataFrame()
        sel_tg = pd.DataFrame()

# ── Live game detection (lightweight) ─────────────────────────────────────────
live_state = None
try:
    live_state = get_live_game_state(selected_team)
except Exception:
    pass

# Show live game banner if active
if live_state and live_state.get("status") not in (None, "Final", "Scheduled", ""):
    _ls = live_state
    _opp = _ls.get("opponent", "")
    _opp_logo = logo_url(_opp)
    _score = _ls.get("score", "")
    _period = _ls.get("period", "")
    _clock = _ls.get("clock", "")
    _shots = _ls.get("shots", {})
    _venue = "Home" if _ls.get("is_home") else "Away"
    st.markdown(
        f"<div style='background:#eff6ff;border:2px solid #3b82f6;border-radius:12px;"
        f"padding:12px 16px;margin-bottom:10px;'>"
        f"<div style='display:flex;align-items:center;gap:12px;'>"
        f"<span style='font-size:1.4rem;font-weight:800;'>🔴 LIVE</span>"
        f"<img src='{_sel_logo}' width='36' height='36' style='object-fit:contain;'/>"
        f"<span style='font-size:1.3rem;font-weight:800;'>{_score}</span>"
        f"<img src='{_opp_logo}' width='36' height='36' style='object-fit:contain;'/>"
        f"<span style='font-size:0.9rem;color:#3b82f6;font-weight:600;'>"
        f"P{_period} · {_clock} · {_venue}</span>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════════════════════════════════════
# TABS — 9 primary views
# ══════════════════════════════════════════════════════════════════════════════
tab_ov, tab_st, tab_sc, tab_cmp, tab_pr, tab_br, tab_sim, tab_pi, tab_tp = st.tabs(
    [
        "📊 Overview",
        "📋 Standings",
        "📅 Schedule",
        "⚖️ Compare",
        "🏆 Playoff Race",
        "🔲 Bracket",
        "🎲 Simulator",
        "⭐ Player Impact",
        "🎬 Top Plays",
    ]
)

with tab_ov:
    try:
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
            app_mode=app_mode,
            playoff_series=playoff_series,
        )
    except Exception as _e:
        st.error(f"Overview failed to render: {_e}")

with tab_st:
    try:
        standings.render(
            standings_df=standings_df,
            team_metrics_dict=team_metrics_dict,
            team_name_map=team_name_map,
            selected_team=selected_team,
            app_mode=app_mode,
        )
    except Exception as _e:
        st.error(f"Standings failed to render: {_e}")

with tab_sc:
    try:
        schedule.render(
            selected_team=selected_team,
            sel_schedule=sel_schedule,
            standings_df=standings_df,
            team_metrics_dict=team_metrics_dict,
            team_name_map=team_name_map,
        )
    except Exception as _e:
        st.error(f"Schedule failed to render: {_e}")

with tab_cmp:
    try:
        comparison.render(
            all_teams=all_teams,
            standings_df=standings_df,
            team_metrics_dict=team_metrics_dict,
            team_name_map=team_name_map,
        )
    except Exception as _e:
        st.error(f"Comparison failed to render: {_e}")

with tab_pr:
    try:
        playoff_race.render(
            selected_team=selected_team,
            sel_metrics=sel_metrics,
            sel_outlook=sel_outlook,
            standings_df=standings_df,
            team_metrics_dict=team_metrics_dict,
            team_name_map=team_name_map,
            app_mode=app_mode,
            sim_results=sim_results,
            playoff_series=playoff_series,
        )
    except Exception as _e:
        st.error(f"Playoff Race failed to render: {_e}")

with tab_br:
    try:
        bracket.render(
            selected_team=selected_team,
            team_metrics_dict=team_metrics_dict,
            team_name_map=team_name_map,
            app_mode=app_mode,
            playoff_series=playoff_series,
        )
    except Exception as _e:
        st.error(f"Bracket failed to render: {_e}")

with tab_sim:
    try:
        simulator.render(
            all_teams=all_teams,
            standings_df=standings_df,
            team_metrics_dict=team_metrics_dict,
            team_name_map=team_name_map,
            app_mode=app_mode,
            playoff_series=playoff_series,
        )
    except Exception as _e:
        st.error(f"Simulator failed to render: {_e}")

with tab_pi:
    try:
        player_impact.render(
            selected_team=selected_team,
            sel_tg=sel_tg,
            sel_schedule=sel_schedule,
            app_mode=app_mode,
        )
    except Exception as _e:
        st.error(f"Player Impact failed to render: {_e}")

with tab_tp:
    try:
        top_plays.render(
            selected_team=selected_team,
            sel_schedule=sel_schedule,
            sel_tg=sel_tg,
        )
    except Exception as _e:
        st.error(f"Top Plays failed to render: {_e}")

# ── Live auto-refresh (scoped to live sections only) ──────────────────────────
if auto_refresh_on and live_state and should_auto_refresh(live_state):
    _interval = get_refresh_interval(live_state)
    if refresh_speed == "Faster":
        _interval = max(_interval // 2, 10)
    if _interval > 0:
        import time

        _ts_key = "last_refresh_ts"
        _now = time.time()
        _last = st.session_state.get(_ts_key, 0)
        if (_now - _last) >= _interval:
            st.session_state[_ts_key] = _now
            st.rerun()
