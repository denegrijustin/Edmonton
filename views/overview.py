"""Overview view — team identity, status, recent results, and playoff context."""

import streamlit as st

from config.settings import GAMES_IN_SEASON
from services.mode_state import AppMode
from services.playoff_state import get_team_playoff_record, get_team_series
from services.series_tracker import compute_series_state
from services.simulation import simulate_playoff_series, SIM_DEPTHS
from services.player_impact import compute_player_impact, get_top_impact_players
from ui.components import (
    kpi_html, safe_kpi, logo_card_html, result_card_html, upcoming_card_html,
)
from utils.formatters import fmt_pct, fmt_record, fmt_signed_int, fmt_number
from utils.logos import logo_url
from utils.streamlit_keys import mk_key
from utils.validators import safe_numeric, safe_int


# ── Helpers ───────────────────────────────────────────────────────────────────

_PAGE = "overview"

_RESULT_COLORS = {"W": "#22c55e", "L": "#ef4444", "OTL": "#f59e0b", "O": "#f59e0b"}


def _heat_cell(label: str, color: str) -> str:
    """One small colored cell for a heat-strip."""
    return (
        f"<span style='display:inline-block;width:24px;height:22px;"
        f"line-height:22px;text-align:center;font-size:0.7rem;font-weight:700;"
        f"border-radius:4px;margin:1px;color:#fff;background:{color};'>"
        f"{label}</span>"
    )


def _team_row(standings_df, team_abbrev):
    """Return the row from standings_df for the selected team, or None."""
    if standings_df is None or standings_df.empty:
        return None
    match = standings_df[standings_df["teamAbbrev"] == team_abbrev]
    return match.iloc[0] if not match.empty else None


# ── Main render ───────────────────────────────────────────────────────────────

def render(
    selected_team,
    sel_name,
    sel_metrics,
    sel_outlook,
    sel_schedule,
    sel_tg,
    standings_df,
    team_metrics_dict,
    team_name_map,
    app_mode,
    playoff_series=None,
):
    """Render the Overview tab."""
    try:
        _render_inner(
            selected_team, sel_name, sel_metrics, sel_outlook,
            sel_schedule, sel_tg, standings_df, team_metrics_dict,
            team_name_map, app_mode, playoff_series,
        )
    except Exception as exc:
        st.error(f"Overview could not be rendered: {exc}")


def _render_inner(
    selected_team, sel_name, sel_metrics, sel_outlook,
    sel_schedule, sel_tg, standings_df, team_metrics_dict,
    team_name_map, app_mode, playoff_series,
):
    row = _team_row(standings_df, selected_team)

    # ── Identity row ──────────────────────────────────────────────────────
    st.markdown("#### Team Overview")
    id_cols = st.columns([1, 3])
    with id_cols[0]:
        st.markdown(
            f"<div style='text-align:center;'>"
            f"<img src='{logo_url(selected_team)}' width='90' height='90' "
            f"style='object-fit:contain;'/>"
            f"<div style='font-weight:800;font-size:1.1rem;margin-top:4px;'>"
            f"{sel_name}</div></div>",
            unsafe_allow_html=True,
        )

    with id_cols[1]:
        if row is not None:
            w = safe_int(row.get("wins"))
            lo = safe_int(row.get("losses"))
            otl = safe_int(row.get("otLosses"))
            pts = safe_int(row.get("points"))
            gp = safe_int(row.get("gamesPlayed"))
            gd = safe_int(row.get("goalDifferential"))
            pp = safe_numeric(row.get("pointPctg"))
            l10w = safe_int(row.get("l10Wins"))
            l10l = safe_int(row.get("l10Losses"))
            l10o = safe_int(row.get("l10OtLosses"))

            k = st.columns(6)
            k[0].markdown(kpi_html("Record", fmt_record(w, lo, otl)), unsafe_allow_html=True)
            k[1].markdown(kpi_html("Points", str(pts), f"GP {gp}"), unsafe_allow_html=True)
            k[2].markdown(kpi_html("Pts %", fmt_pct(pp * 100 if pp < 1 else pp)), unsafe_allow_html=True)
            k[3].markdown(kpi_html("Goal Diff", fmt_signed_int(gd)), unsafe_allow_html=True)
            k[4].markdown(kpi_html("Last 10", f"{l10w}-{l10l}-{l10o}"), unsafe_allow_html=True)
            remaining = GAMES_IN_SEASON - gp if gp else "—"
            k[5].markdown(kpi_html("Remaining", str(remaining)), unsafe_allow_html=True)
        else:
            st.info("Standings data unavailable for this team.")

    # ── Playoff position ──────────────────────────────────────────────────
    if row is not None:
        conf_seq = safe_int(row.get("conferenceSequence"))
        wc_seq = safe_int(row.get("wildcardSequence"))
        div = row.get("division", "")
        if conf_seq and conf_seq <= 8:
            st.success(f"✅ **Playoff position**: Conference #{conf_seq} — {div}")
        elif wc_seq and wc_seq <= 2:
            st.warning(f"🟡 **Wildcard #{wc_seq}** — {div}")
        elif conf_seq:
            st.error(f"❌ **Outside playoffs**: Conference #{conf_seq}")

    # ── Last-10 heat strip ────────────────────────────────────────────────
    if row is not None:
        l10w = safe_int(row.get("l10Wins"))
        l10l = safe_int(row.get("l10Losses"))
        l10o = safe_int(row.get("l10OtLosses"))
        cells = (
            [_heat_cell("W", "#22c55e")] * l10w
            + [_heat_cell("L", "#ef4444")] * l10l
            + [_heat_cell("O", "#f59e0b")] * l10o
        )
        st.markdown(
            f"<div style='margin:6px 0;'><b>Last 10 results:</b> {''.join(cells)}</div>",
            unsafe_allow_html=True,
        )

    # ── Goals heat rows ───────────────────────────────────────────────────
    if sel_tg is not None and not sel_tg.empty:
        recent = sel_tg.tail(10)
        gf_cells = []
        ga_cells = []
        for _, g in recent.iterrows():
            gf = safe_int(g.get("teamScore", 0))
            ga = safe_int(g.get("oppScore", 0))
            gf_color = "#22c55e" if gf >= 4 else "#f59e0b" if gf >= 2 else "#ef4444"
            ga_color = "#22c55e" if ga <= 1 else "#f59e0b" if ga <= 3 else "#ef4444"
            gf_cells.append(_heat_cell(str(gf), gf_color))
            ga_cells.append(_heat_cell(str(ga), ga_color))
        st.markdown(
            f"<div style='margin:4px 0;'><b>Goals For (last {len(recent)}):</b> "
            f"{''.join(gf_cells)}</div>"
            f"<div style='margin:4px 0;'><b>Goals Against (last {len(recent)}):</b> "
            f"{''.join(ga_cells)}</div>",
            unsafe_allow_html=True,
        )

    # ── Playoffs mode overlay ─────────────────────────────────────────────
    if app_mode == AppMode.PLAYOFFS and playoff_series:
        st.markdown("---")
        st.markdown("#### Playoff Status")
        rec = get_team_playoff_record(selected_team, playoff_series)
        ts = get_team_series(selected_team, playoff_series)
        rc = st.columns(2)
        rc[0].markdown(
            kpi_html("Playoff Record", f"{rec.get('wins', 0)}-{rec.get('losses', 0)}"),
            unsafe_allow_html=True,
        )
        if ts:
            state = compute_series_state(ts)
            rc[1].markdown(
                kpi_html("Current Series", state.get("status_text", "—")),
                unsafe_allow_html=True,
            )

            # Series confidence (button-triggered)
            if st.button("Compute Series Confidence (Model-derived)",
                         key=mk_key(_PAGE, "series_conf_btn")):
                a = ts.get("topSeed", "")
                b = ts.get("bottomSeed", "")
                wa = safe_int(ts.get("topSeedWins"))
                wb = safe_int(ts.get("bottomSeedWins"))
                if a and b and team_metrics_dict:
                    res = simulate_playoff_series(a, b, team_metrics_dict,
                                                  wins_a=wa, wins_b=wb, n_sims=500)
                    st.markdown(
                        f"**Model-derived series confidence**: "
                        f"{a} {res.get('team_a_wins_prob', 0):.1%} — "
                        f"{b} {res.get('team_b_wins_prob', 0):.1%}"
                    )

    # ── Next game card ────────────────────────────────────────────────────
    if sel_schedule is not None and not sel_schedule.empty:
        if "isCompleted" in sel_schedule.columns:
            upcoming = sel_schedule[sel_schedule["isCompleted"] == False]
        elif "gameState" in sel_schedule.columns:
            upcoming = sel_schedule[sel_schedule["gameState"] != "OFF"]
        else:
            upcoming = sel_schedule.head(0)
        if not upcoming.empty:
            nxt = upcoming.iloc[0]
            opp_home = nxt.get("homeTeam", "")
            opp_away = nxt.get("awayTeam", "")
            opp = opp_away if opp_home == selected_team else opp_home
            venue = "Home" if opp_home == selected_team else "Away"
            date = str(nxt.get("gameDate", ""))[:10]
            st.markdown("#### Next Game")
            st.markdown(
                upcoming_card_html(opp, f"{venue} · {date}", ""),
                unsafe_allow_html=True,
            )

    # ── Last 5 results ────────────────────────────────────────────────────
    if sel_tg is not None and not sel_tg.empty:
        st.markdown("#### Recent Games")
        last5 = sel_tg.tail(5)
        cols = st.columns(len(last5))
        for i, (_, g) in enumerate(last5.iterrows()):
            opp = g.get("opponent", "???")
            res = g.get("result", "—")
            ts_score = safe_int(g.get("teamScore", 0))
            os_score = safe_int(g.get("oppScore", 0))
            date = str(g.get("gameDate", ""))[:10]
            cols[i].markdown(
                result_card_html(opp, res, f"{ts_score}–{os_score}", date),
                unsafe_allow_html=True,
            )
