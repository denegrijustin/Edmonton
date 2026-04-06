"""Playoff Race / Season Outlook tab — state-aware rendering.

Handles three season phases:
- REGULAR_SEASON: simulation-based odds, rankings, projected standings
- PLAYOFFS: bracket view with series records and win probabilities
- OFFSEASON: final standings summary
"""

from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from config.settings import PLAYOFF_BRACKET_MAP
from models.projections import (
    build_playoff_projection_table,
    get_seed_prob_distribution,
)
from providers.odds_provider import compute_consensus_odds
from ui.components import kpi_html, logo_card_html, prob_bar_html
from utils.formatters import fmt_number, fmt_pct, fmt_signed_int
from utils.logos import logo_url
from utils.state_detection import SeasonState
from utils.stoplights import stoplight


def render(
    selected_team: str,
    sel_metrics: Dict[str, Any],
    sel_outlook: Dict[str, Any],
    standings_df: pd.DataFrame,
    team_metrics_dict: Dict[str, Dict],
    team_name_map: Dict[str, str],
    season_state: SeasonState = SeasonState.REGULAR_SEASON,
    sim_results: Optional[Dict[str, Any]] = None,
    playoff_series: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Render the Season Outlook tab content."""

    if season_state == SeasonState.PLAYOFFS:
        _render_playoffs(
            selected_team, sel_metrics, sel_outlook, standings_df,
            team_metrics_dict, team_name_map, playoff_series or [],
        )
    elif season_state == SeasonState.OFFSEASON:
        _render_offseason(selected_team, standings_df, team_name_map)
    else:
        _render_regular_season(
            selected_team, sel_metrics, sel_outlook, standings_df,
            team_metrics_dict, team_name_map, sim_results,
        )


# ---------------------------------------------------------------------------
# Regular season view
# ---------------------------------------------------------------------------

def _render_regular_season(
    selected_team: str,
    sel_metrics: Dict[str, Any],
    sel_outlook: Dict[str, Any],
    standings_df: pd.DataFrame,
    team_metrics_dict: Dict[str, Dict],
    team_name_map: Dict[str, str],
    sim_results: Optional[Dict[str, Any]],
) -> None:
    st.markdown("### 🏒 REGULAR SEASON OUTLOOK")

    conf_name = sel_outlook.get("conference") or ""

    # ── KPI row ──────────────────────────────────────────────────────────────
    _pr1, _pr2, _pr3, _pr4 = st.columns(4)

    _conf_rank_val = sel_outlook.get("conference_rank")
    _pr1.markdown(
        kpi_html(
            "Conf. Rank",
            f"#{_conf_rank_val}" if _conf_rank_val else "—",
            f"{sel_metrics.get('points', 0)} pts",
        ),
        unsafe_allow_html=True,
    )
    _pr2.markdown(
        kpi_html("Proj. Points", str(sel_outlook.get("projected_points", "—")), "End-of-season pace"),
        unsafe_allow_html=True,
    )
    _pr3.markdown(
        kpi_html(
            "Proj. Seed",
            f"#{sel_outlook.get('projected_seed')}" if sel_outlook.get("projected_seed") else "Outside top 8",
            f"{conf_name} Conference",
        ),
        unsafe_allow_html=True,
    )

    # Use sim-based odds if available, otherwise fall back to proxy model
    sim_playoff_odds = None
    if sim_results and selected_team in sim_results.get("playoff_odds", {}):
        sim_playoff_odds = sim_results["playoff_odds"][selected_team]

    display_odds = sim_playoff_odds if sim_playoff_odds is not None else sel_outlook.get("playoff_odds", 0)
    _sl_pl = stoplight(display_odds, 70, 45)
    odds_sub = "Monte Carlo simulation" if sim_playoff_odds is not None else "Internal proxy model"
    _pr4.markdown(
        kpi_html("Playoff Odds", f"{_sl_pl} {display_odds:.0f}%", odds_sub),
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ── Simulation-based odds section ────────────────────────────────────────
    if sim_results:
        _render_sim_odds_section(selected_team, sel_outlook, sim_results, team_name_map)
    else:
        _render_proxy_odds_section(selected_team, sel_outlook)

    st.markdown("---")

    # ── Projected opponent + seed distribution ────────────────────────────────
    pl_left, pl_right = st.columns([1, 2])
    with pl_left:
        st.markdown("**🎯 Projected First-Round Opponent**")
        _pl_opp = sel_outlook.get("projected_opponent")
        if _pl_opp:
            st.markdown(
                logo_card_html(_pl_opp, _pl_opp, team_name_map.get(_pl_opp, "")),
                unsafe_allow_html=True,
            )
            seed_probs = get_seed_prob_distribution(selected_team, standings_df)
            if seed_probs and sel_outlook.get("projected_seed"):
                cur_seed = int(sel_outlook["projected_seed"])
                alt_seed_num = PLAYOFF_BRACKET_MAP.get(
                    max(1, cur_seed - 1) if cur_seed > 1 else cur_seed + 1
                )
                if alt_seed_num and not standings_df.empty:
                    mask_c = standings_df["conference"].astype(str).str.contains(
                        conf_name, case=False, na=False
                    )
                    cdf = standings_df[mask_c].copy()
                    cdf["points"] = pd.to_numeric(cdf["points"], errors="coerce").fillna(0)
                    cdf_sorted = cdf.sort_values("points", ascending=False).reset_index(drop=True)
                    if alt_seed_num <= len(cdf_sorted):
                        alt_opp = cdf_sorted.iloc[alt_seed_num - 1]["teamAbbrev"]
                        if alt_opp != _pl_opp:
                            st.markdown(
                                "<div style='margin-top:8px;font-size:0.82rem;color:#64748b;'>2nd most likely:</div>",
                                unsafe_allow_html=True,
                            )
                            st.markdown(
                                logo_card_html(
                                    str(alt_opp), str(alt_opp),
                                    team_name_map.get(str(alt_opp), ""),
                                ),
                                unsafe_allow_html=True,
                            )
        else:
            st.markdown(
                "<span class='muted'>Not currently projected for playoffs</span>",
                unsafe_allow_html=True,
            )

    with pl_right:
        st.markdown("**📊 Seed Probability Distribution**")
        # Use sim-based seed odds if available
        if sim_results and selected_team in sim_results.get("seed_odds", {}):
            sim_seeds = sim_results["seed_odds"][selected_team]
            seed_probs = {int(k): float(v) for k, v in sim_seeds.items()}
            source_note = "Monte Carlo simulation"
        else:
            seed_probs = get_seed_prob_distribution(selected_team, standings_df)
            source_note = "Heuristic model"

        if seed_probs:
            seed_colors_map = {
                1: "#f59e0b", 2: "#3b82f6", 3: "#3b82f6",
                4: "#22c55e", 5: "#22c55e",
                6: "#94a3b8", 7: "#94a3b8", 8: "#ef4444",
            }
            prob_html_str = ""
            for _s in range(1, 9):
                _p = seed_probs.get(_s, 0)
                _c = seed_colors_map.get(_s, "#94a3b8")
                prob_html_str += prob_bar_html(f"Seed #{_s}", _p, _c)
            st.markdown(prob_html_str, unsafe_allow_html=True)
            st.caption(source_note)
        else:
            st.info("Seed probability distribution unavailable.")

    st.markdown("---")

    # ── Conference standings & simulation projection ──────────────────────────
    st.markdown(f"### {conf_name} Conference — Standings & Projection")

    if sim_results and not sim_results.get("projected_final_standings", pd.DataFrame()).empty:
        _render_sim_standings_table(selected_team, conf_name, sim_results, standings_df)
    elif not standings_df.empty and conf_name:
        _render_proxy_standings_table(selected_team, conf_name, standings_df)
    else:
        st.info("Conference standings data unavailable.")


def _render_sim_odds_section(
    selected_team: str,
    sel_outlook: Dict[str, Any],
    sim_results: Dict[str, Any],
    team_name_map: Dict[str, str],
) -> None:
    """Show simulation-based odds summary."""
    st.markdown("### 📊 Season Simulation Results")

    playoff_pct = sim_results.get("playoff_odds", {}).get(selected_team, 0)
    div_title_pct = sim_results.get("division_title_odds", {}).get(selected_team, 0)
    wc_pct = sim_results.get("wild_card_odds", {}).get(selected_team, 0)
    lfr = sim_results.get("likely_final_ranking", {}).get(selected_team, {})
    proj_pts = lfr.get("proj_pts", sel_outlook.get("projected_points", "—"))
    pts_range = f"P10: {lfr.get('proj_pts_p10', '—')} | P90: {lfr.get('proj_pts_p90', '—')}"

    c1, c2, c3, c4 = st.columns(4)
    sl_pl = stoplight(playoff_pct, 70, 45)
    c1.markdown(
        kpi_html("Playoff Odds", f"{sl_pl} {playoff_pct:.0f}%", "Monte Carlo sim"),
        unsafe_allow_html=True,
    )
    sl_div = stoplight(div_title_pct, 40, 15)
    c2.markdown(
        kpi_html("Division Title", f"{sl_div} {div_title_pct:.0f}%", "Win division"),
        unsafe_allow_html=True,
    )
    sl_wc = stoplight(wc_pct, 40, 15)
    c3.markdown(
        kpi_html("Wild Card", f"{sl_wc} {wc_pct:.0f}%", "Via wild card slot"),
        unsafe_allow_html=True,
    )
    c4.markdown(
        kpi_html("Proj. Points", str(proj_pts), pts_range),
        unsafe_allow_html=True,
    )


def _render_proxy_odds_section(
    selected_team: str,
    sel_outlook: Dict[str, Any],
) -> None:
    """Show proxy model odds (no sim data available)."""
    st.markdown("### 🏒 Playoff Odds — Internal Model")
    internal_odds = sel_outlook.get("playoff_odds", 0)
    consensus = compute_consensus_odds(internal_odds, [])
    c_odds = consensus.get("consensus_odds")
    c1, c2 = st.columns(2)
    sl_int = stoplight(internal_odds, 70, 45)
    c1.markdown(
        kpi_html("Internal Model", f"{sl_int} {internal_odds:.0f}%", "Based on pace + GD + gap"),
        unsafe_allow_html=True,
    )
    if c_odds is not None:
        sl_c = stoplight(c_odds, 70, 45)
        c2.markdown(
            kpi_html("Model Estimate", f"{sl_c} {c_odds:.0f}%", "Proxy formula"),
            unsafe_allow_html=True,
        )


def _render_sim_standings_table(
    selected_team: str,
    conf_name: str,
    sim_results: Dict[str, Any],
    standings_df: pd.DataFrame,
) -> None:
    """Render the simulation-based projected standings table."""
    proj_df = sim_results["projected_final_standings"].copy()

    # Filter to conference
    if conf_name and "conference" in proj_df.columns:
        mask = proj_df["conference"].astype(str).str.contains(conf_name, case=False, na=False)
        proj_df = proj_df[mask].copy()

    if proj_df.empty:
        _render_proxy_standings_table(selected_team, conf_name, standings_df)
        return

    # Enrich with current standings info
    if not standings_df.empty:
        cols_needed = ["teamAbbrev", "teamName", "wins", "losses", "otLosses", "points", "division"]
        merge_df = standings_df[
            [c for c in cols_needed if c in standings_df.columns]
        ].copy()
        proj_df = proj_df.merge(merge_df, on="teamAbbrev", how="left")

    proj_df = proj_df.sort_values("proj_pts", ascending=False).reset_index(drop=True)
    proj_df["Rank"] = proj_df.index + 1
    proj_df["Playoff"] = proj_df["playoff_odds"].apply(
        lambda x: "✅ IN" if x >= 50 else ("🟡 EDGE" if x >= 25 else "❌ OUT")
    )

    def _hl(row: pd.Series):
        base = [""] * len(row)
        if row.get("teamAbbrev") == selected_team:
            return ["background-color:#eff6ff;font-weight:bold"] * len(row)
        if row.get("playoff_odds", 0) >= 50:
            return ["background-color:#f0fdf4"] * len(row)
        return base

    display_cols = ["Rank", "teamAbbrev", "proj_pts", "proj_pts_p10", "proj_pts_p90", "playoff_odds", "Playoff"]
    rename = {
        "teamAbbrev": "Team",
        "proj_pts": "Proj Pts",
        "proj_pts_p10": "P10",
        "proj_pts_p90": "P90",
        "playoff_odds": "Playoff %",
    }
    avail = [c for c in display_cols if c in proj_df.columns]
    st.dataframe(
        proj_df[avail].rename(columns=rename).style.apply(_hl, axis=1),
        use_container_width=True,
        hide_index=True,
    )


def _render_proxy_standings_table(
    selected_team: str,
    conf_name: str,
    standings_df: pd.DataFrame,
) -> None:
    from models.projections import build_playoff_projection_table

    proj_tbl = build_playoff_projection_table(standings_df, conf_name)
    if proj_tbl.empty:
        st.info("Conference standings data unavailable.")
        return

    proj_tbl["Playoff"] = proj_tbl["in_playoffs"].map({True: "✅ IN", False: "❌ OUT"})

    def _hl_team(row: pd.Series):
        if row.get("teamAbbrev") == selected_team:
            return ["background-color:#eff6ff;font-weight:bold"] * len(row)
        if row.get("in_playoffs"):
            return ["background-color:#f0fdf4"] * len(row)
        return [""] * len(row)

    disp_cols = ["conf_rank", "teamAbbrev", "teamName", "Record", "points", "proj_pts", "division", "Playoff"]
    st.dataframe(
        proj_tbl[disp_cols]
        .rename(columns={
            "conf_rank": "Rank", "teamAbbrev": "Team", "teamName": "Name",
            "points": "Pts", "proj_pts": "Proj Pts", "division": "Division",
        })
        .style.apply(_hl_team, axis=1),
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------------------------
# Playoffs view
# ---------------------------------------------------------------------------

def _render_playoffs(
    selected_team: str,
    sel_metrics: Dict[str, Any],
    sel_outlook: Dict[str, Any],
    standings_df: pd.DataFrame,
    team_metrics_dict: Dict[str, Dict],
    team_name_map: Dict[str, str],
    playoff_series: List[Dict[str, Any]],
) -> None:
    st.markdown("### 🏆 PLAYOFF BRACKET OUTLOOK")

    if not playoff_series:
        st.info("Playoff bracket data is not yet available.")
        _render_regular_season(
            selected_team, sel_metrics, sel_outlook, standings_df,
            team_metrics_dict, team_name_map, None,
        )
        return

    # Group series by round
    rounds: Dict[int, List[Dict[str, Any]]] = {}
    for s in playoff_series:
        r = s.get("round", 1)
        rounds.setdefault(r, []).append(s)

    round_labels = {1: "First Round", 2: "Second Round", 3: "Conference Finals", 4: "Stanley Cup Finals"}

    for rnd in sorted(rounds.keys()):
        st.markdown(f"#### {round_labels.get(rnd, f'Round {rnd}')}")
        series_in_round = rounds[rnd]
        cols = st.columns(min(len(series_in_round), 4))

        for i, s in enumerate(series_in_round):
            top = s.get("topSeed", "")
            bot = s.get("bottomSeed", "")
            tw = s.get("topSeedWins", 0)
            bw = s.get("bottomSeedWins", 0)
            status = s.get("seriesStatus", "")
            next_game = s.get("nextGameDate", "")

            col = cols[i % len(cols)]
            with col:
                # Compute series win probability
                sim_note = ""
                try:
                    from models.playoff_series_sim import simulate_series  # noqa: PLC0415
                    ma = team_metrics_dict.get(top, {})
                    mb = team_metrics_dict.get(bot, {})
                    if ma and mb:
                        sr = simulate_series(
                            top, bot,
                            {top: ma, bot: mb},
                            wins_a=tw, wins_b=bw,
                            n_sims=200,
                        )
                        top_pct = sr["team_a_wins_prob"] * 100
                        bot_pct = sr["team_b_wins_prob"] * 100
                        sim_note = f"Sim: {top} {top_pct:.0f}% · {bot} {bot_pct:.0f}%"
                except Exception:
                    sim_note = ""

                hl_top = "font-weight:bold;" if top == selected_team else ""
                hl_bot = "font-weight:bold;" if bot == selected_team else ""
                next_str = f"Next: {next_game}" if next_game else ""

                st.markdown(
                    f"""
<div style="border:1px solid #e2e8f0;border-radius:8px;padding:10px;margin-bottom:8px;">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
    <img src="{logo_url(top)}" width="28" height="28" style="object-fit:contain;" />
    <span style="{hl_top}font-size:0.95rem;">{top}</span>
    <span style="margin-left:auto;font-weight:700;font-size:1.1rem;">{tw}</span>
  </div>
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
    <img src="{logo_url(bot)}" width="28" height="28" style="object-fit:contain;" />
    <span style="{hl_bot}font-size:0.95rem;">{bot}</span>
    <span style="margin-left:auto;font-weight:700;font-size:1.1rem;">{bw}</span>
  </div>
  {f'<div style="font-size:0.78rem;color:#64748b;">{status}</div>' if status else ''}
  {f'<div style="font-size:0.75rem;color:#94a3b8;">{next_str}</div>' if next_str else ''}
  {f'<div style="font-size:0.75rem;color:#3b82f6;margin-top:4px;">{sim_note}</div>' if sim_note else ''}
</div>
""",
                    unsafe_allow_html=True,
                )

    # Full bracket simulation button
    st.markdown("---")
    if st.button("🎲 Simulate Full Bracket", key="sim_bracket_btn"):
        with st.spinner("Simulating bracket…"):
            try:
                from models.playoff_series_sim import simulate_full_bracket  # noqa: PLC0415
                bracket_results = simulate_full_bracket(playoff_series, team_metrics_dict, n_sims=1000)
                if bracket_results:
                    st.markdown("#### Cup Odds (1,000 simulations)")
                    res_df = pd.DataFrame([
                        {
                            "Team": t,
                            "Cup %": v["cup_odds"],
                            "Finals %": v["finals_odds"],
                            "Conf Finals %": v["conf_finals_odds"],
                        }
                        for t, v in bracket_results.items()
                        if v["cup_odds"] > 0 or v["next_round_odds"] > 0
                    ]).sort_values("Cup %", ascending=False)
                    st.dataframe(res_df, use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"Bracket simulation failed: {e}")


# ---------------------------------------------------------------------------
# Offseason view
# ---------------------------------------------------------------------------

def _render_offseason(
    selected_team: str,
    standings_df: pd.DataFrame,
    team_name_map: Dict[str, str],
) -> None:
    st.markdown("### 🏁 SEASON COMPLETE")
    st.info("The regular season and playoffs have concluded.")

    if standings_df.empty:
        return

    standings_df = standings_df.copy()
    for col in ["points", "wins", "losses", "otLosses", "gamesPlayed"]:
        if col in standings_df.columns:
            standings_df[col] = pd.to_numeric(standings_df[col], errors="coerce").fillna(0)

    final = standings_df.sort_values("points", ascending=False).reset_index(drop=True)
    final["Rank"] = final.index + 1

    def _hl(row):
        if row.get("teamAbbrev") == selected_team:
            return ["background-color:#eff6ff;font-weight:bold"] * len(row)
        return [""] * len(row)

    cols = ["Rank", "teamAbbrev", "teamName", "points", "wins", "losses", "otLosses", "conference", "division"]
    avail = [c for c in cols if c in final.columns]
    rename = {
        "teamAbbrev": "Team", "teamName": "Name", "points": "Pts",
        "wins": "W", "losses": "L", "otLosses": "OTL",
        "conference": "Conf", "division": "Division",
    }
    st.dataframe(
        final[avail].rename(columns=rename).style.apply(_hl, axis=1),
        use_container_width=True,
        hide_index=True,
    )
