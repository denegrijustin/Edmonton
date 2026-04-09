"""Playoff Race view — position, odds, clinch scenarios, and competitor table."""

import streamlit as st
import pandas as pd

from config.settings import GAMES_IN_SEASON
from services.mode_state import AppMode
from services.odds_engine import compute_team_playoff_odds
from services.series_tracker import build_bracket_state
from models.projections import compute_outlook
from ui.components import kpi_html, prob_bar_html
from utils.formatters import fmt_pct, fmt_number, fmt_signed_int
from utils.logos import logo_url
from utils.streamlit_keys import mk_key
from utils.validators import safe_numeric, safe_int


_PAGE = "playoff_race"


def _logo_img(abbrev: str, size: int = 28) -> str:
    return (
        f"<img src='{logo_url(abbrev)}' width='{size}' height='{size}' "
        f"style='object-fit:contain;vertical-align:middle;'/>"
    )


def _team_row(standings_df, abbrev):
    if standings_df is None or standings_df.empty:
        return None
    match = standings_df[standings_df["teamAbbrev"] == abbrev]
    return match.iloc[0] if not match.empty else None


# ── Main render ───────────────────────────────────────────────────────────────

def render(
    selected_team, sel_metrics, sel_outlook, standings_df,
    team_metrics_dict, team_name_map, app_mode,
    sim_results=None, playoff_series=None,
):
    """Render the Playoff Race tab."""
    try:
        _render_inner(
            selected_team, sel_metrics, sel_outlook, standings_df,
            team_metrics_dict, team_name_map, app_mode,
            sim_results, playoff_series,
        )
    except Exception as exc:
        st.error(f"Playoff Race view could not be rendered: {exc}")


def _render_inner(
    selected_team, sel_metrics, sel_outlook, standings_df,
    team_metrics_dict, team_name_map, app_mode,
    sim_results, playoff_series,
):
    if standings_df is None or standings_df.empty:
        st.info("Standings data is unavailable.")
        return

    # ── Playoffs mode: show current bracket position ──────────────────────
    if app_mode == AppMode.PLAYOFFS and playoff_series:
        st.markdown("#### Current Playoff Position")
        bracket = build_bracket_state(playoff_series)
        team_in = any(
            s.get("topSeed") == selected_team or s.get("bottomSeed") == selected_team
            for s in bracket
        )
        if team_in:
            st.success(f"✅ **{team_name_map.get(selected_team, selected_team)}** is in the playoffs.")
            for s in bracket:
                if s.get("topSeed") == selected_team or s.get("bottomSeed") == selected_team:
                    top = s.get("topSeed", "")
                    bot = s.get("bottomSeed", "")
                    tw = safe_int(s.get("topSeedWins"))
                    bw = safe_int(s.get("bottomSeedWins"))
                    rd = s.get("round", "—")
                    st.markdown(
                        f"{_logo_img(top)} **{top}** {tw} — {bw} **{bot}** {_logo_img(bot)} "
                        f"(Round {rd})",
                        unsafe_allow_html=True,
                    )
        else:
            st.info(f"{team_name_map.get(selected_team, selected_team)} is not in the current playoff bracket.")
        return

    # ── Regular season race ───────────────────────────────────────────────
    row = _team_row(standings_df, selected_team)
    if row is None:
        st.info("Team data not found in standings.")
        return

    conf = row.get("conference", "")
    conf_seq = safe_int(row.get("conferenceSequence"))
    wc_seq = safe_int(row.get("wildcardSequence"))
    pts = safe_int(row.get("points"))
    gp = safe_int(row.get("gamesPlayed"))
    remaining = GAMES_IN_SEASON - gp

    st.markdown("#### Playoff Race Position")

    # KPI row
    kc = st.columns(4)
    kc[0].markdown(kpi_html("Conference Rank", f"#{conf_seq}" if conf_seq else "—"), unsafe_allow_html=True)
    kc[1].markdown(kpi_html("Points", str(pts), f"GP {gp}"), unsafe_allow_html=True)
    kc[2].markdown(kpi_html("Games Remaining", str(remaining)), unsafe_allow_html=True)

    # Points behind/ahead of cutoff
    conf_df = standings_df[standings_df["conference"] == conf].sort_values("conferenceSequence")
    cutoff_row = conf_df[conf_df["conferenceSequence"] == 8]
    if not cutoff_row.empty:
        cutoff_pts = safe_int(cutoff_row.iloc[0].get("points"))
        gap = pts - cutoff_pts
        gap_label = "ahead" if gap > 0 else "behind" if gap < 0 else "on"
        kc[3].markdown(
            kpi_html("Pts vs Cutoff", f"{gap:+d}", f"{abs(gap)} {gap_label} 8th"),
            unsafe_allow_html=True,
        )
    else:
        kc[3].markdown(kpi_html("Pts vs Cutoff", "—"), unsafe_allow_html=True)

    # ── Model-derived odds ────────────────────────────────────────────────
    st.markdown("#### Projected Odds *(Model-derived)*")

    odds_data = None
    if team_metrics_dict:
        try:
            odds_data = compute_team_playoff_odds(selected_team, standings_df, team_metrics_dict)
        except Exception:
            odds_data = None

    outlook = sel_outlook or {}

    po = safe_numeric(odds_data.get("playoff_odds") if odds_data else outlook.get("playoff_odds"))
    do = safe_numeric(odds_data.get("division_odds") if odds_data else None)

    oc = st.columns(2)
    oc[0].markdown(prob_bar_html("Playoff Probability", po, "#3b82f6"), unsafe_allow_html=True)
    oc[1].markdown(prob_bar_html("Division Title Probability", do, "#8b5cf6"), unsafe_allow_html=True)

    # Projected opponent
    proj_opp = outlook.get("projected_opponent")
    if proj_opp:
        st.markdown(
            f"**Likely First-Round Opponent** *(Projected)*: "
            f"{_logo_img(proj_opp, 24)} **{team_name_map.get(proj_opp, proj_opp)}**",
            unsafe_allow_html=True,
        )

    # ── Clinch scenarios ──────────────────────────────────────────────────
    if remaining > 0 and not cutoff_row.empty:
        st.markdown("#### Clinch Scenarios")
        cutoff_pts_val = safe_int(cutoff_row.iloc[0].get("points"))
        cutoff_gp = safe_int(cutoff_row.iloc[0].get("gamesPlayed"))
        cutoff_remaining = GAMES_IN_SEASON - cutoff_gp
        max_cutoff_pts = cutoff_pts_val + cutoff_remaining * 2

        wins_to_clinch = max(0, (max_cutoff_pts - pts + 1 + 1) // 2)
        if wins_to_clinch <= remaining:
            st.markdown(
                f"🏒 **Clinch scenario**: Win **{wins_to_clinch}** of remaining "
                f"**{remaining}** games to guarantee a playoff spot "
                f"(assumes 8th-place team wins all remaining)."
            )
        if pts > max_cutoff_pts:
            st.success("✅ **Clinched playoff spot** — cannot be caught by 8th-place team.")
        elif remaining == 0:
            if conf_seq and conf_seq <= 8:
                st.success("✅ **Season complete — qualified for playoffs.**")
            else:
                st.error("❌ **Season complete — did not qualify.**")

    # ── Competitor table ──────────────────────────────────────────────────
    st.markdown("#### Conference Competitors")
    if conf_df is not None and not conf_df.empty:
        near = conf_df[
            conf_df["conferenceSequence"].between(max(1, conf_seq - 4), conf_seq + 4)
        ].copy() if conf_seq else conf_df.head(10)

        rows_html = (
            "<table style='width:100%;border-collapse:collapse;font-size:0.82rem;'>"
            "<tr style='border-bottom:2px solid #e2e8f0;'>"
            "<th style='padding:4px 6px;text-align:left;'>#</th>"
            "<th style='padding:4px 6px;text-align:left;'>Team</th>"
            "<th style='padding:4px 6px;'>Pts</th>"
            "<th style='padding:4px 6px;'>GP</th>"
            "<th style='padding:4px 6px;'>Rem</th>"
            "</tr>"
        )
        for _, cr in near.iterrows():
            ca = cr.get("teamAbbrev", "")
            cs = safe_int(cr.get("conferenceSequence"))
            cp = safe_int(cr.get("points"))
            cg = safe_int(cr.get("gamesPlayed"))
            cr_rem = GAMES_IN_SEASON - cg
            hl = "background:#eff6ff;font-weight:700;" if ca == selected_team else ""
            rows_html += (
                f"<tr style='{hl}border-bottom:1px solid #f1f5f9;'>"
                f"<td style='padding:4px 6px;'>{cs}</td>"
                f"<td style='padding:4px 6px;'>{_logo_img(ca, 22)} "
                f"{team_name_map.get(ca, ca)}</td>"
                f"<td style='padding:4px 6px;text-align:center;font-weight:600;'>{cp}</td>"
                f"<td style='padding:4px 6px;text-align:center;'>{cg}</td>"
                f"<td style='padding:4px 6px;text-align:center;'>{cr_rem}</td>"
                f"</tr>"
            )
        rows_html += "</table>"
        st.markdown(rows_html, unsafe_allow_html=True)
