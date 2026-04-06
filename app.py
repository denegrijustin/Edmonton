"""NHL Analytics Dashboard — Production-ready, data-first Streamlit application.

Entry point that orchestrates data loading, feature engineering, models,
simulations, and UI rendering through the modular architecture.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.settings import (
    DEFAULT_TEAM,
    DEFAULT_TEAM_NAME,
    MC_SIMULATIONS,
    SEASON,
    TOTAL_GAMES,
)
from config.teams import CONFERENCES, DIVISIONS, TEAMS, TEAM_LOGOS
from data.loader import LeagueDataLoader
from features.momentum import compute_momentum
from features.player_ratings import compute_player_ratings
from features.team_features import compute_team_features
from models.playoff_model import PlayoffModel
from models.projections import project_opponents, project_seeds
from providers.nhl_api import NHLApiProvider
from simulations.game_sim import simulate_game
from simulations.season_sim import simulate_season
from ui.charts import (
    plot_game_sim_histogram,
    plot_impact_chart,
    plot_momentum,
    plot_player_progress,
    plot_points_path,
    plot_rink_heatmap,
    plot_team_trend,
)
from ui.components import (
    kpi_card,
    render_kpi,
    stoplight_for_value,
    team_logo_html,
    team_logo_with_name,
)
from ui.styles import DASHBOARD_CSS
from utils.helpers import format_record, zscore
from utils.stoplight import sl_grade, sl_momentum, sl_odds, sl_result, sl_damage

# ────────────────────────────────────────────────────────────────
# Page config
# ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NHL Analytics Dashboard",
    page_icon="🏒",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────
ALL_TEAM_OPTIONS = sorted(TEAMS.keys())


def _logo_col(abbrev: str, size: int = 24) -> str:
    return team_logo_html(abbrev, size)


def _detect_season_state(standings: pd.DataFrame, schedule: pd.DataFrame, focus: str) -> str:
    """Detect: regular_season | bracket_locked | active_playoff."""
    if schedule.empty:
        return "regular_season"
    playoff_games = schedule[schedule["gameType"] == 3]
    if not playoff_games.empty:
        if playoff_games["isCompleted"].any():
            return "active_playoff"
        return "bracket_locked"
    return "regular_season"


def _edm_eliminated(standings: pd.DataFrame, season_sim: dict) -> bool:
    """Check if Edmonton is mathematically eliminated."""
    if not season_sim:
        return False
    edm_sim = season_sim.get(DEFAULT_TEAM, {})
    return edm_sim.get("makePlayoffsPct", 50) < 1


# ────────────────────────────────────────────────────────────────
# Data load
# ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="Loading league data…")
def _load_league_data(focus_team: str) -> dict[str, Any]:
    loader = LeagueDataLoader(focus_team)
    return loader.load_all()


# Determine focus team
focus_team = st.session_state.get("focus_team", DEFAULT_TEAM)

try:
    data = _load_league_data(focus_team)
except Exception as e:
    st.error(f"⚠️ Data load failed: {e}")
    st.stop()

standings: pd.DataFrame = data["standings"]
schedule: pd.DataFrame = data["schedule"]
roster: pd.DataFrame = data["roster"]
team_games: pd.DataFrame = data["team_games"]
player_games: pd.DataFrame = data["player_games"]
shot_events: pd.DataFrame = data["shot_events"]
season_sim: dict = data["season_sim"]
health = data["health"]

# Season state detection
season_state = _detect_season_state(standings, schedule, focus_team)

# Edmonton elimination auto-shift
if focus_team == DEFAULT_TEAM and _edm_eliminated(standings, season_sim):
    st.info("🏒 Edmonton is projected eliminated — shifting focus to Western Conference playoff race.")
    focus_team = DEFAULT_TEAM  # keep EDM but show Western race prominently

# ────────────────────────────────────────────────────────────────
# Header with logo
# ────────────────────────────────────────────────────────────────
team_info = TEAMS.get(focus_team, {})
team_name = team_info.get("name", focus_team)
logo_url = TEAM_LOGOS.get(focus_team, "")

hdr1, hdr2 = st.columns([0.08, 0.92])
with hdr1:
    st.markdown(f'<img src="{logo_url}" width="64" height="64">', unsafe_allow_html=True)
with hdr2:
    st.title(f"NHL Analytics Dashboard — {team_name}")
    st.caption(f"Season {SEASON[:4]}–{SEASON[4:]} | {season_state.replace('_', ' ').title()} | Data-driven hockey analytics")

# ────────────────────────────────────────────────────────────────
# Team selector (sidebar)
# ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Team Selector")
    selected_team = st.selectbox(
        "Focus Team",
        ALL_TEAM_OPTIONS,
        index=ALL_TEAM_OPTIONS.index(focus_team) if focus_team in ALL_TEAM_OPTIONS else 0,
        format_func=lambda x: f"{x} — {TEAMS.get(x, {}).get('name', x)}",
    )
    if selected_team != focus_team:
        st.session_state["focus_team"] = selected_team
        st.rerun()

# ────────────────────────────────────────────────────────────────
# KPI Row
# ────────────────────────────────────────────────────────────────
team_standing = standings[standings["teamAbbrev"] == focus_team]

if not team_standing.empty:
    ts = team_standing.iloc[0]
    wins = int(ts.get("wins", 0))
    losses = int(ts.get("losses", 0))
    otl = int(ts.get("otLosses", 0))
    pts = int(ts.get("points", 0))
    gd = int(ts.get("goalDifferential", 0))
    gp = int(ts.get("gamesPlayed", 0))
    proj_pts = int(ts.get("projectedPoints", 0))
    proj_rec = ts.get("projectedRecord", "—")
    playoff_odds = float(ts.get("playoffOdds", 50))
    conf_rank = ts.get("conferenceSequence", "—")
    div_rank = ts.get("divisionSequence", "—")
    proj_seed = int(ts.get("projectedSeed", 0))
    proj_opp = ts.get("projectedOpponent", "—")
    momentum_val = float(team_games["momentumScore"].iloc[-1]) if not team_games.empty and "momentumScore" in team_games.columns else 50.0
else:
    wins = losses = otl = pts = gd = gp = proj_pts = 0
    proj_rec = "—"
    playoff_odds = 50.0
    conf_rank = div_rank = "—"
    proj_seed = 0
    proj_opp = "—"
    momentum_val = 50.0

# MC sim odds (if available)
mc_odds = season_sim.get(focus_team, {}).get("makePlayoffsPct", playoff_odds)

k1, k2, k3, k4, k5, k6 = st.columns(6)
with k1:
    render_kpi("Record", format_record(wins, losses, otl), f"{gp} GP | {pts} pts")
with k2:
    render_kpi("Goal Diff", f"{gd:+d}", "Season to date", stoplight_for_value(gd, 5, -5))
with k3:
    render_kpi("Momentum", f"{momentum_val:.0f}", team_games["momentumDirection"].iloc[-1] if not team_games.empty and "momentumDirection" in team_games.columns else "—", stoplight_for_value(momentum_val, 55, 45))
with k4:
    render_kpi("Projected Pts", str(proj_pts), f"Projected: {proj_rec}", stoplight_for_value(proj_pts, 95, 85))
with k5:
    render_kpi("Playoff Odds", f"{mc_odds:.0f}%", f"Proj Seed: {proj_seed}", stoplight_for_value(mc_odds, 70, 40))
with k6:
    opp_logo = team_logo_html(str(proj_opp), 20) if proj_opp and proj_opp != "—" and proj_opp in TEAMS else ""
    render_kpi("Proj Opponent", f"{opp_logo} {proj_opp}", f"Conf Rank: {conf_rank}")

# ────────────────────────────────────────────────────────────────
# Filters
# ────────────────────────────────────────────────────────────────
with st.container():
    fc1, fc2, fc3, fc4 = st.columns([1.3, 1.2, 1.2, 1.4])
    with fc1:
        venue_filter = st.selectbox("Venue", ["All", "Home", "Away"], index=0)
    with fc2:
        strength_filter = st.selectbox("Strength", ["All", "5v5", "PP", "SH"], index=0)
    with fc3:
        window_choice = st.selectbox("Trend Window", [3, 5, 10], index=0)
    with fc4:
        player_options = sorted(player_games["playerName"].dropna().unique().tolist()) if not player_games.empty else []
        default_player = "Connor McDavid" if "Connor McDavid" in player_options else (player_options[0] if player_options else None)
        player_selected = st.selectbox("Player Focus", player_options, index=player_options.index(default_player) if default_player and default_player in player_options else 0)

# Apply venue filter
team_games_view = team_games[team_games["venue"] == venue_filter] if venue_filter != "All" and not team_games.empty else team_games
shot_events_view = shot_events.copy() if not shot_events.empty else shot_events
if venue_filter != "All" and not shot_events_view.empty:
    shot_events_view = shot_events_view[shot_events_view["venue"] == venue_filter]
if strength_filter != "All" and not shot_events_view.empty:
    shot_events_view = shot_events_view[shot_events_view["strength"].astype(str).str.contains(strength_filter, case=False, na=False)]

# ────────────────────────────────────────────────────────────────
# Main Tabs
# ────────────────────────────────────────────────────────────────
tabs = st.tabs([
    "🏒 Team Profile",
    "🏆 Playoff Race",
    "⚔️ Team Comparison",
    "📊 Next Game",
    "🎯 Shot Maps",
    "⭐ Player Ratings",
    "🎲 Game Simulation",
    "📋 Game Log",
    "🔧 Data Health",
])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB: Team Profile
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[0]:
    if not team_standing.empty:
        ts = team_standing.iloc[0]
        p1, p2 = st.columns([1.2, 1])

        with p1:
            st.markdown(f"### {team_logo_html(focus_team, 40)} Team Identity", unsafe_allow_html=True)
            profile_data = {
                "Record": format_record(wins, losses, otl),
                "Points": pts,
                "Regulation Wins": int(ts.get("regulationWins", 0)),
                "Goal Differential": f"{gd:+d}",
                "Home": ts.get("homeRecord", "—"),
                "Away": ts.get("awayRecord", "—"),
                "Last 10": ts.get("last10Record", "—"),
                "Streak": f"{ts.get('streakCode', '')} {ts.get('streakCount', '')}",
                "Points %": f"{float(ts.get('pointPctg', 0)):.3f}",
                "Division": ts.get("division", "—"),
                "Conference Rank": conf_rank,
                "Division Rank": div_rank,
            }
            for label, val in profile_data.items():
                st.markdown(f"**{label}:** {val}")

        with p2:
            st.markdown("### Projected Finish")
            proj_data = {
                "Projected Record": proj_rec,
                "Projected Points": proj_pts,
                "Projected Seed": proj_seed,
                "Projected Opponent": f"{team_logo_html(str(proj_opp), 20)} {proj_opp}" if proj_opp and proj_opp != "—" and str(proj_opp) in TEAMS else str(proj_opp),
                "Playoff Odds (Model)": f"{playoff_odds:.0f}%",
                "Playoff Odds (MC Sim)": f"{mc_odds:.0f}%",
                "Momentum": f"{momentum_val:.0f} — {team_games['momentumDirection'].iloc[-1] if not team_games.empty and 'momentumDirection' in team_games.columns else '—'}",
            }
            for label, val in proj_data.items():
                st.markdown(f"**{label}:** {val}", unsafe_allow_html=True)

    # Team trends
    if not team_games_view.empty:
        _tgv = team_games_view if not team_games_view.empty else team_games
        st.markdown("### Team Trends")
        tc1, tc2 = st.columns([1.3, 1])
        with tc1:
            st.plotly_chart(plot_team_trend(_tgv), use_container_width=True)
        with tc2:
            st.plotly_chart(plot_momentum(_tgv), use_container_width=True)
        st.plotly_chart(plot_impact_chart(_tgv), use_container_width=True)

    # Last 5 / Next 5
    if not schedule.empty:
        st.markdown("### Last 5 & Next 5 Games")
        l5_col, n5_col = st.columns(2)

        completed = schedule[schedule["isCompleted"]].sort_values("gameDate", ascending=False).head(5)
        upcoming = schedule[~schedule["isCompleted"]].sort_values("gameDate").head(5)

        with l5_col:
            st.markdown("**Last 5 Games**")
            if not completed.empty:
                l5_rows = []
                for _, g in completed.iterrows():
                    opp = g["awayTeam"] if g["homeTeam"] == focus_team else g["homeTeam"]
                    venue = "Home" if g["homeTeam"] == focus_team else "Away"
                    ts_score = g["homeScore"] if g["homeTeam"] == focus_team else g["awayScore"]
                    os_score = g["awayScore"] if g["homeTeam"] == focus_team else g["homeScore"]
                    result = "W" if ts_score and os_score and ts_score > os_score else ("L" if ts_score and os_score and ts_score < os_score else "OTL")
                    l5_rows.append({
                        "Opponent": opp,
                        "Score": f"{ts_score}–{os_score}" if ts_score is not None else "—",
                        "Venue": venue,
                        "Result": result,
                        "Type": str(g.get("periodType", "REG")),
                    })
                l5_df = pd.DataFrame(l5_rows)
                st.dataframe(
                    l5_df.style.map(sl_result, subset=["Result"]),
                    use_container_width=True, hide_index=True,
                )
            else:
                st.info("No completed games yet.")

        with n5_col:
            st.markdown("**Next 5 Games**")
            if not upcoming.empty:
                n5_rows = []
                for _, g in upcoming.iterrows():
                    opp = g["awayTeam"] if g["homeTeam"] == focus_team else g["homeTeam"]
                    venue = "Home" if g["homeTeam"] == focus_team else "Away"
                    date_str = g["gameDate"].strftime("%b %d") if pd.notna(g["gameDate"]) else "—"
                    n5_rows.append({"Date": date_str, "Opponent": opp, "Venue": venue})
                st.dataframe(pd.DataFrame(n5_rows), use_container_width=True, hide_index=True)
            else:
                st.info("No upcoming games scheduled.")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB: Playoff Race
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[1]:
    st.markdown("### 🏆 League-Wide Playoff Race")

    if not standings.empty:
        conf_tab = st.radio("Conference", ["Western", "Western + Eastern"], horizontal=True)
        show_confs = ["Western", "Eastern"] if "Eastern" in conf_tab else ["Western"]

        for conf in show_confs:
            st.markdown(f"#### {conf} Conference")
            conf_mask = standings["conference"].astype(str).str.contains(conf, case=False, na=False)
            conf_df = standings[conf_mask].copy()
            if conf_df.empty:
                continue

            # Add MC sim data
            conf_df["mcPlayoffPct"] = conf_df["teamAbbrev"].map(
                lambda x: season_sim.get(x, {}).get("makePlayoffsPct", "—"),
            )
            conf_df["mcMeanPts"] = conf_df["teamAbbrev"].map(
                lambda x: season_sim.get(x, {}).get("meanFinalPts", "—"),
            )

            display_cols = [
                "teamAbbrev", "points", "wins", "losses", "otLosses",
                "goalDifferential", "regulationWins", "pointPctg",
                "projectedPoints", "projectedRecord", "projectedSeed",
                "projectedOpponent", "playoffOdds", "mcPlayoffPct", "mcMeanPts",
                "homeRecord", "awayRecord", "last10Record",
            ]
            display_cols = [c for c in display_cols if c in conf_df.columns]
            race_df = conf_df[display_cols].sort_values("points", ascending=False).copy()
            race_df = race_df.rename(columns={
                "teamAbbrev": "Team", "points": "Pts", "wins": "W", "losses": "L",
                "otLosses": "OTL", "goalDifferential": "GD", "regulationWins": "RW",
                "pointPctg": "Pts%", "projectedPoints": "Proj Pts",
                "projectedRecord": "Proj Record", "projectedSeed": "Seed",
                "projectedOpponent": "Proj Opp", "playoffOdds": "Odds%",
                "mcPlayoffPct": "MC Odds%", "mcMeanPts": "MC Pts",
                "homeRecord": "Home", "awayRecord": "Away", "last10Record": "L10",
            })

            st.dataframe(
                race_df.style
                .format({"Pts%": "{:.3f}", "Odds%": "{:.1f}"}, na_rep="—")
                .map(sl_odds, subset=["Odds%"]),
                use_container_width=True,
                hide_index=True,
            )

    # Points path for focus team
    if not team_games.empty and "cumulativePoints" in team_games.columns:
        st.markdown(f"### {team_logo_html(focus_team, 24)} Points Path", unsafe_allow_html=True)
        st.plotly_chart(plot_points_path(team_games, proj_pts), use_container_width=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB: Team Comparison
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[2]:
    st.markdown("### ⚔️ Team Comparison — This Season")
    comp1, comp2 = st.columns(2)
    with comp1:
        team_a = st.selectbox("Team A", ALL_TEAM_OPTIONS, index=ALL_TEAM_OPTIONS.index(focus_team), key="comp_a",
                               format_func=lambda x: f"{x} — {TEAMS.get(x, {}).get('name', x)}")
    with comp2:
        default_b = "CGY" if "CGY" in ALL_TEAM_OPTIONS and team_a != "CGY" else ALL_TEAM_OPTIONS[1]
        team_b = st.selectbox("Team B", ALL_TEAM_OPTIONS, index=ALL_TEAM_OPTIONS.index(default_b), key="comp_b",
                               format_func=lambda x: f"{x} — {TEAMS.get(x, {}).get('name', x)}")

    if not standings.empty:
        row_a = standings[standings["teamAbbrev"] == team_a]
        row_b = standings[standings["teamAbbrev"] == team_b]

        if not row_a.empty and not row_b.empty:
            a = row_a.iloc[0]
            b = row_b.iloc[0]

            metrics = [
                ("Record", format_record(int(a.get("wins", 0)), int(a.get("losses", 0)), int(a.get("otLosses", 0))),
                 format_record(int(b.get("wins", 0)), int(b.get("losses", 0)), int(b.get("otLosses", 0)))),
                ("Points", int(a.get("points", 0)), int(b.get("points", 0))),
                ("Projected Points", int(a.get("projectedPoints", 0)), int(b.get("projectedPoints", 0))),
                ("Projected Record", a.get("projectedRecord", "—"), b.get("projectedRecord", "—")),
                ("Goal Differential", int(a.get("goalDifferential", 0)), int(b.get("goalDifferential", 0))),
                ("Regulation Wins", int(a.get("regulationWins", 0)), int(b.get("regulationWins", 0))),
                ("Points %", f"{float(a.get('pointPctg', 0)):.3f}", f"{float(b.get('pointPctg', 0)):.3f}"),
                ("Playoff Odds", f"{float(a.get('playoffOdds', 0)):.0f}%", f"{float(b.get('playoffOdds', 0)):.0f}%"),
                ("Projected Seed", int(a.get("projectedSeed", 0)), int(b.get("projectedSeed", 0))),
                ("Projected Opponent", a.get("projectedOpponent", "—"), b.get("projectedOpponent", "—")),
                ("Home Record", a.get("homeRecord", "—"), b.get("homeRecord", "—")),
                ("Away Record", a.get("awayRecord", "—"), b.get("awayRecord", "—")),
                ("Last 10", a.get("last10Record", "—"), b.get("last10Record", "—")),
                ("Streak", f"{a.get('streakCode', '')} {a.get('streakCount', '')}", f"{b.get('streakCode', '')} {b.get('streakCount', '')}"),
            ]

            comp_df = pd.DataFrame(metrics, columns=["Metric", team_a, team_b])
            st.dataframe(comp_df, use_container_width=True, hide_index=True)

            # MC sim comparison
            st.markdown("#### Monte Carlo Season Simulation Comparison")
            sim_a = season_sim.get(team_a, {})
            sim_b = season_sim.get(team_b, {})
            mc_metrics = [
                ("MC Playoff Odds", f"{sim_a.get('makePlayoffsPct', '—')}%", f"{sim_b.get('makePlayoffsPct', '—')}%"),
                ("MC Mean Final Pts", sim_a.get("meanFinalPts", "—"), sim_b.get("meanFinalPts", "—")),
                ("MC Median Final Pts", sim_a.get("medianFinalPts", "—"), sim_b.get("medianFinalPts", "—")),
                ("MC 10th Pctile Pts", sim_a.get("p10FinalPts", "—"), sim_b.get("p10FinalPts", "—")),
                ("MC 90th Pctile Pts", sim_a.get("p90FinalPts", "—"), sim_b.get("p90FinalPts", "—")),
            ]
            st.dataframe(pd.DataFrame(mc_metrics, columns=["Metric", team_a, team_b]), use_container_width=True, hide_index=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB: Next Game
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[3]:
    st.markdown("### 📊 Next Game Expected Outcome")
    upcoming = schedule[~schedule["isCompleted"]].sort_values("gameDate") if not schedule.empty else pd.DataFrame()

    if not upcoming.empty:
        next_game = upcoming.iloc[0]
        opp = next_game["awayTeam"] if next_game["homeTeam"] == focus_team else next_game["homeTeam"]
        is_home = next_game["homeTeam"] == focus_team
        venue_str = "Home" if is_home else "Away"
        date_str = next_game["gameDate"].strftime("%B %d, %Y") if pd.notna(next_game["gameDate"]) else "TBD"

        ng1, ng2 = st.columns([0.5, 0.5])
        with ng1:
            st.markdown(f"**Date:** {date_str}")
            st.markdown(f"**Venue:** {venue_str}")
            st.markdown(f"**Matchup:** {team_logo_html(focus_team, 28)} vs {team_logo_html(opp, 28)}", unsafe_allow_html=True)

        with ng2:
            # Run game simulation
            home_team = focus_team if is_home else opp
            away_team = opp if is_home else focus_team
            sim_result = simulate_game(home_team, away_team, standings, team_games if is_home else None, team_games if not is_home else None, n_sims=MC_SIMULATIONS)

            st.markdown(f"**Projected Score:** {sim_result['projectedScore']}")
            st.markdown(f"**Score Range:** {sim_result['scoreRange']}")
            team_win_pct = sim_result["homeWinPct"] if is_home else sim_result["awayWinPct"]
            opp_win_pct = sim_result["awayWinPct"] if is_home else sim_result["homeWinPct"]
            team_reg_win = sim_result["homeRegWinPct"] if is_home else sim_result["awayRegWinPct"]

            sl_conf = stoplight_for_value(team_win_pct, 55, 45)
            st.markdown(f"**{focus_team} Win Prob:** {team_win_pct:.1f}% {team_logo_html(focus_team, 16)}", unsafe_allow_html=True)
            st.markdown(f"**{opp} Win Prob:** {opp_win_pct:.1f}% {team_logo_html(opp, 16)}", unsafe_allow_html=True)
            st.markdown(f"**Regulation Win:** {team_reg_win:.1f}%")
            st.markdown(f"**OT Probability:** {sim_result['otPct']:.1f}%")
            st.markdown(f"**Confidence:** {sim_result['confidence']}")

        # Distribution chart
        st.plotly_chart(
            plot_game_sim_histogram(sim_result["homeGoalDist"], sim_result["awayGoalDist"], home_team, away_team),
            use_container_width=True,
        )

        st.markdown("#### Simulation Drivers")
        st.markdown(f"- Home expected goals: **{sim_result['homeXG']:.2f}**")
        st.markdown(f"- Away expected goals: **{sim_result['awayXG']:.2f}**")
        st.markdown(f"- Based on {sim_result['nSims']:,} simulations using team strength, home/away splits, momentum, and goal profiles")
    else:
        st.info("No upcoming games found.")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB: Shot Maps
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[4]:
    st.markdown("### 🎯 Shot & Goal Heat Maps")
    if not shot_events_view.empty:
        # Separate by shot type
        team_shots = shot_events_view[shot_events_view["isTeamShot"]]
        opp_shots = shot_events_view[~shot_events_view["isTeamShot"]]

        # Goals vs shots
        team_goals = team_shots[team_shots["eventType"].str.contains("goal", case=False, na=False)]
        team_on_goal = team_shots[team_shots["eventType"].str.contains("shot", case=False, na=False)]
        team_missed = team_shots[team_shots["eventType"].str.contains("miss", case=False, na=False)]
        team_blocked = team_shots[team_shots["eventType"].str.contains("block", case=False, na=False)]

        opp_goals = opp_shots[opp_shots["eventType"].str.contains("goal", case=False, na=False)]
        opp_on_goal = opp_shots[opp_shots["eventType"].str.contains("shot", case=False, na=False)]

        st.markdown(f"#### Offensive Shot Maps — {team_logo_html(focus_team, 20)}", unsafe_allow_html=True)
        o1, o2 = st.columns(2)
        with o1:
            if not team_shots.empty:
                st.plotly_chart(plot_rink_heatmap(team_shots, f"{focus_team} All Shot Attempts"), use_container_width=True)
        with o2:
            if not team_goals.empty:
                st.plotly_chart(plot_rink_heatmap(team_goals, f"{focus_team} Goals Scored"), use_container_width=True)

        st.markdown(f"#### Defensive Shot Maps — Against {team_logo_html(focus_team, 20)}", unsafe_allow_html=True)
        d1, d2 = st.columns(2)
        with d1:
            if not opp_shots.empty:
                st.plotly_chart(plot_rink_heatmap(opp_shots, "Opponent All Shot Attempts"), use_container_width=True)
        with d2:
            if not opp_goals.empty:
                st.plotly_chart(plot_rink_heatmap(opp_goals, "Opponent Goals Against"), use_container_width=True)

        # Zone summary
        st.markdown("#### Zone Summary")
        if not shot_events_view.empty and "zone" in shot_events_view.columns:
            zone_summary = shot_events_view.groupby(["isTeamShot", "zone"], as_index=False).size()
            zone_pivot = zone_summary.pivot(index="zone", columns="isTeamShot", values="size").fillna(0).reset_index()
            if len(zone_pivot.columns) == 3:
                zone_pivot.columns = ["Zone", "Against", "For"]
            st.dataframe(zone_pivot, use_container_width=True, hide_index=True)
    else:
        st.info("No shot data available for the selected filters.")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB: Player Ratings
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[5]:
    st.markdown("### ⭐ Player Rating Trends")
    if not player_games.empty:
        # Player progression chart
        if player_selected:
            st.plotly_chart(plot_player_progress(player_games, player_selected), use_container_width=True)

        # Player snapshot
        latest = (
            player_games.sort_values(["playerName", "gameDate", "gameId"])
            .groupby("playerName", as_index=False)
            .tail(1)
        )
        display_player_cols = ["playerName", "positionGroup", "rollingGrade", "consistencyScore",
                                "recent5AvgPoints", "seasonAvgPoints", "trendFlag", "toi_min",
                                "rolling5Toi", "toiFlag"]
        display_player_cols = [c for c in display_player_cols if c in latest.columns]
        latest_display = latest[display_player_cols].rename(columns={
            "playerName": "Player", "positionGroup": "Pos", "rollingGrade": "Grade",
            "consistencyScore": "Consistency", "recent5AvgPoints": "R5 Pts",
            "seasonAvgPoints": "Avg Pts", "trendFlag": "Trend", "toi_min": "TOI",
            "rolling5Toi": "R5 TOI", "toiFlag": "TOI Flag",
        })

        st.markdown("#### Current Ratings — Top 15")
        top15 = latest_display.sort_values("Grade", ascending=False).head(15)
        st.dataframe(
            top15.style
            .format({"Grade": "{:.1f}", "Consistency": "{:.1f}", "R5 Pts": "{:.2f}", "Avg Pts": "{:.2f}", "TOI": "{:.1f}", "R5 TOI": "{:.1f}"}, na_rep="—")
            .map(sl_grade, subset=["Grade", "Consistency"]),
            use_container_width=True,
            hide_index=True,
        )

        # Forwards, Defensemen, Goalies breakdown
        for pos_label, pos_code in [("Forwards", "F"), ("Defensemen", "D"), ("Goalies", "G")]:
            pos_df = latest_display[latest_display["Pos"] == pos_code].sort_values("Grade", ascending=False)
            if not pos_df.empty:
                st.markdown(f"#### {pos_label}")
                st.dataframe(
                    pos_df.style
                    .format({"Grade": "{:.1f}", "Consistency": "{:.1f}", "R5 Pts": "{:.2f}", "Avg Pts": "{:.2f}", "TOI": "{:.1f}", "R5 TOI": "{:.1f}"}, na_rep="—")
                    .map(sl_grade, subset=["Grade", "Consistency"]),
                    use_container_width=True,
                    hide_index=True,
                )

        # Ice Time tracking
        st.markdown("#### Ice Time Tracking")
        toi_cols = ["playerName", "positionGroup", "toi_min", "rolling5Toi", "seasonAvgToi",
                    "toiDeviation", "toiFlag"]
        toi_cols = [c for c in toi_cols if c in latest.columns]
        if toi_cols:
            toi_df = latest[toi_cols].rename(columns={
                "playerName": "Player", "positionGroup": "Pos", "toi_min": "Last TOI",
                "rolling5Toi": "R5 TOI", "seasonAvgToi": "Season Avg TOI",
                "toiDeviation": "Deviation", "toiFlag": "Flag",
            }).sort_values("Last TOI", ascending=False)
            st.dataframe(
                toi_df.style.format({"Last TOI": "{:.1f}", "R5 TOI": "{:.1f}", "Season Avg TOI": "{:.1f}", "Deviation": "{:.2f}"}, na_rep="—"),
                use_container_width=True, hide_index=True,
            )
    else:
        st.info("No player data available.")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB: Game Simulation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[6]:
    st.markdown("### 🎲 Monte Carlo Game Simulation")
    st.markdown("Choose any two teams and venue to simulate a game using this season's data.")

    gs1, gs2, gs3 = st.columns(3)
    with gs1:
        sim_home = st.selectbox("Home Team", ALL_TEAM_OPTIONS, index=ALL_TEAM_OPTIONS.index(focus_team), key="sim_home",
                                 format_func=lambda x: f"{x} — {TEAMS.get(x, {}).get('name', x)}")
    with gs2:
        sim_default_away = "CGY" if "CGY" in ALL_TEAM_OPTIONS and sim_home != "CGY" else ALL_TEAM_OPTIONS[1]
        sim_away = st.selectbox("Away Team", ALL_TEAM_OPTIONS, index=ALL_TEAM_OPTIONS.index(sim_default_away), key="sim_away",
                                 format_func=lambda x: f"{x} — {TEAMS.get(x, {}).get('name', x)}")
    with gs3:
        n_sims_choice = st.selectbox("Simulations", [1000, 5000, 10000], index=2)

    if st.button("🎲 Run Simulation", type="primary"):
        with st.spinner(f"Simulating {n_sims_choice:,} games..."):
            sim_result = simulate_game(sim_home, sim_away, standings, n_sims=n_sims_choice)

        sr1, sr2 = st.columns(2)
        with sr1:
            st.markdown(f"#### {team_logo_html(sim_home, 28)} {sim_home} (Home)", unsafe_allow_html=True)
            st.metric("Win Probability", f"{sim_result['homeWinPct']:.1f}%")
            st.metric("Regulation Win", f"{sim_result['homeRegWinPct']:.1f}%")
            st.metric("Expected Goals", f"{sim_result['homeGoalsMean']:.2f}")

        with sr2:
            st.markdown(f"#### {team_logo_html(sim_away, 28)} {sim_away} (Away)", unsafe_allow_html=True)
            st.metric("Win Probability", f"{sim_result['awayWinPct']:.1f}%")
            st.metric("Regulation Win", f"{sim_result['awayRegWinPct']:.1f}%")
            st.metric("Expected Goals", f"{sim_result['awayGoalsMean']:.2f}")

        st.markdown(f"**Projected Score:** {sim_result['projectedScore']}")
        st.markdown(f"**Score Range:** {sim_result['scoreRange']}")
        st.markdown(f"**OT Probability:** {sim_result['otPct']:.1f}%")
        st.markdown(f"**Confidence:** {sim_result['confidence']}")

        st.plotly_chart(
            plot_game_sim_histogram(sim_result["homeGoalDist"], sim_result["awayGoalDist"], sim_home, sim_away),
            use_container_width=True,
        )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB: Game Log
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[7]:
    st.markdown("### 📋 Season Schedule & Game Log")

    if not schedule.empty:
        sched_display = schedule.copy()
        opp_col = np.where(sched_display["homeTeam"] == focus_team, sched_display["awayTeam"], sched_display["homeTeam"])
        venue_col = np.where(sched_display["homeTeam"] == focus_team, "Home", "Away")
        team_score_col = np.where(sched_display["homeTeam"] == focus_team, sched_display["homeScore"], sched_display["awayScore"])
        opp_score_col = np.where(sched_display["homeTeam"] == focus_team, sched_display["awayScore"], sched_display["homeScore"])
        result_col = np.where(
            ~sched_display["isCompleted"], "Upcoming",
            np.where(team_score_col > opp_score_col, "W", np.where(team_score_col == opp_score_col, "OTL", "L")),
        )
        full_sched = pd.DataFrame({
            "Date": sched_display["gameDate"].dt.strftime("%b %d"),
            "Venue": venue_col,
            "Opponent": opp_col,
            "Score": np.where(sched_display["isCompleted"], team_score_col.astype(str) + "–" + opp_score_col.astype(str), "—"),
            "Result": result_col,
        })
        st.dataframe(
            full_sched.style.map(sl_result, subset=["Result"]),
            use_container_width=True, hide_index=True,
        )

    if not team_games.empty:
        st.markdown("### Team Game Log")
        game_log_cols = ["gameDate", "opponent", "venue", "teamScore", "oppScore", "result",
                         "goalDiff", "shotDiff", "momentumScore"]
        game_log_cols = [c for c in game_log_cols if c in team_games.columns]
        st.dataframe(
            team_games[game_log_cols].style
            .format({"momentumScore": "{:.1f}", "shotDiff": "{:.1f}"}, na_rep="—")
            .map(sl_result, subset=["result"])
            .map(sl_momentum, subset=["momentumScore"] if "momentumScore" in game_log_cols else []),
            use_container_width=True, hide_index=True,
        )

    if not player_games.empty and player_selected:
        st.markdown(f"### Player Game Log — {player_selected}")
        pview = player_games[player_games["playerName"] == player_selected]
        plog_cols = ["gameDate", "goals", "assists", "points", "shots", "toi_min", "gameGrade", "rollingGrade", "trendFlag"]
        plog_cols = [c for c in plog_cols if c in pview.columns]
        st.dataframe(
            pview[plog_cols].style
            .format({"toi_min": "{:.1f}", "gameGrade": "{:.1f}", "rollingGrade": "{:.1f}"}, na_rep="—")
            .map(sl_grade, subset=["gameGrade", "rollingGrade"] if "gameGrade" in plog_cols else []),
            use_container_width=True, hide_index=True,
        )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB: Data Health
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tabs[8]:
    st.markdown("### 🔧 Data Health Panel")

    if health.degraded:
        st.warning("⚠️ Some data sources are degraded. See details below.")

    health_rows = health.summary_rows()
    if health_rows:
        health_df = pd.DataFrame(health_rows)
        st.dataframe(health_df, use_container_width=True, hide_index=True)

    if health.warnings:
        st.markdown("#### Warnings")
        for w in health.warnings:
            st.markdown(f"- ⚠️ {w}")

    st.markdown("#### Season State")
    st.markdown(f"- **Mode:** {season_state.replace('_', ' ').title()}")
    st.markdown(f"- **Focus Team:** {focus_team}")
    st.markdown(f"- **Season:** {SEASON[:4]}–{SEASON[4:]}")
    st.markdown(f"- **Teams Loaded:** {len(standings) if not standings.empty else 0}")
    st.markdown(f"- **Games Parsed:** {len(team_games) if not team_games.empty else 0}")
    st.markdown(f"- **Players Tracked:** {player_games['playerName'].nunique() if not player_games.empty else 0}")
    st.markdown(f"- **Shot Events:** {len(shot_events) if not shot_events.empty else 0}")
    st.markdown(f"- **MC Simulations:** {'✅ Available' if season_sim else '❌ Unavailable'}")
