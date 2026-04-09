"""Bracket view — projected or live playoff bracket with series cards."""

import streamlit as st

from config.settings import PLAYOFF_BRACKET_MAP
from providers.standings_provider import get_standings
from services.mode_state import AppMode
from services.series_tracker import compute_series_state, build_bracket_state
from services.simulation import simulate_full_playoffs, SIM_DEPTHS, get_sim_depth
from ui.components import kpi_html, prob_bar_html
from utils.formatters import fmt_pct
from utils.logos import logo_url
from utils.streamlit_keys import mk_key
from utils.validators import safe_int, safe_numeric


_PAGE = "bracket"


def _logo_img(abbrev: str, size: int = 32) -> str:
    return (
        f"<img src='{logo_url(abbrev)}' width='{size}' height='{size}' "
        f"style='object-fit:contain;vertical-align:middle;'/>"
    )


def _series_card_html(top, bot, top_wins, bot_wins, state_info=None, confidence=None):
    """Render a compact bracket series card."""
    completed = state_info.get("completed", False) if state_info else False
    winner = state_info.get("winner") if state_info else None

    border_color = "#22c55e" if completed else "#3b82f6" if (top_wins or bot_wins) else "#e2e8f0"
    top_bold = "font-weight:800;" if winner == top else ""
    bot_bold = "font-weight:800;" if winner == bot else ""

    html = (
        f"<div style='border:2px solid {border_color};border-radius:10px;"
        f"padding:8px 10px;margin:4px 0;background:#f8fafc;min-width:180px;'>"
        f"<div style='display:flex;align-items:center;justify-content:space-between;"
        f"margin-bottom:4px;'>"
        f"<span>{_logo_img(top, 26)} <span style='{top_bold}'>{top}</span></span>"
        f"<span style='font-weight:700;font-size:1.1rem;'>{top_wins}</span></div>"
        f"<div style='display:flex;align-items:center;justify-content:space-between;'>"
        f"<span>{_logo_img(bot, 26)} <span style='{bot_bold}'>{bot}</span></span>"
        f"<span style='font-weight:700;font-size:1.1rem;'>{bot_wins}</span></div>"
    )

    if completed and winner:
        html += (
            f"<div style='text-align:center;font-size:0.72rem;color:#22c55e;"
            f"font-weight:700;margin-top:4px;'>✅ {winner} advances</div>"
        )
    elif confidence:
        html += (
            f"<div style='text-align:center;font-size:0.72rem;color:#64748b;"
            f"margin-top:4px;'>{confidence}</div>"
        )

    html += "</div>"
    return html


# ── Main render ───────────────────────────────────────────────────────────────

def render(selected_team, team_metrics_dict, team_name_map, app_mode, playoff_series=None):
    """Render the Bracket tab."""
    try:
        _render_inner(selected_team, team_metrics_dict, team_name_map,
                      app_mode, playoff_series)
    except Exception as exc:
        st.error(f"Bracket view could not be rendered: {exc}")


def _render_inner(selected_team, team_metrics_dict, team_name_map,
                  app_mode, playoff_series):

    # ── Live bracket (playoffs active) ────────────────────────────────────
    if app_mode == AppMode.PLAYOFFS and playoff_series:
        st.markdown("#### Live Playoff Bracket")
        bracket = build_bracket_state(playoff_series)

        if not bracket:
            st.info("No active playoff series data available.")
            return

        # Group by round
        rounds = {}
        for s in bracket:
            rd = s.get("round", 1)
            rounds.setdefault(rd, []).append(s)

        for rd_num in sorted(rounds.keys()):
            rd_label = {1: "First Round", 2: "Second Round", 3: "Conference Finals",
                        4: "Stanley Cup Final"}.get(rd_num, f"Round {rd_num}")
            st.markdown(f"##### {rd_label}")
            series_list = rounds[rd_num]
            cols = st.columns(max(len(series_list), 1))
            for i, s in enumerate(series_list):
                top = s.get("topSeed", "???")
                bot = s.get("bottomSeed", "???")
                tw = safe_int(s.get("topSeedWins"))
                bw = safe_int(s.get("bottomSeedWins"))
                state = compute_series_state(s)
                cols[i].markdown(
                    _series_card_html(top, bot, tw, bw, state),
                    unsafe_allow_html=True,
                )

        # Simulate full bracket button
        st.markdown("---")
        depth_choice = st.selectbox(
            "Simulation Depth",
            list(SIM_DEPTHS.keys()),
            index=1,
            key=mk_key(_PAGE, "sim_depth"),
        )
        if st.button("Simulate Full Bracket *(Simulated)*",
                      key=mk_key(_PAGE, "sim_bracket_btn")):
            n = get_sim_depth(depth_choice)
            with st.spinner("Running bracket simulation…"):
                results = simulate_full_playoffs(playoff_series, team_metrics_dict, n_sims=n)
            if results:
                st.markdown("##### Simulated Advancement Probabilities")
                rows_html = (
                    "<table style='width:100%;border-collapse:collapse;font-size:0.82rem;'>"
                    "<tr style='border-bottom:2px solid #e2e8f0;'>"
                    "<th style='padding:4px 6px;text-align:left;'>Team</th>"
                    "<th style='padding:4px 6px;'>Next Round</th>"
                    "<th style='padding:4px 6px;'>Conf Finals</th>"
                    "<th style='padding:4px 6px;'>Finals</th>"
                    "<th style='padding:4px 6px;'>Cup</th></tr>"
                )
                for team, odds in sorted(results.items(),
                                         key=lambda x: x[1].get("cup_odds", 0),
                                         reverse=True):
                    hl = "background:#eff6ff;" if team == selected_team else ""
                    nr = safe_numeric(odds.get("next_round_odds"))
                    cf = safe_numeric(odds.get("conf_finals_odds"))
                    fi = safe_numeric(odds.get("finals_odds"))
                    cu = safe_numeric(odds.get("cup_odds"))
                    rows_html += (
                        f"<tr style='{hl}border-bottom:1px solid #f1f5f9;'>"
                        f"<td style='padding:4px 6px;'>{_logo_img(team, 22)} {team}</td>"
                        f"<td style='padding:4px 6px;text-align:center;'>{fmt_pct(nr)}</td>"
                        f"<td style='padding:4px 6px;text-align:center;'>{fmt_pct(cf)}</td>"
                        f"<td style='padding:4px 6px;text-align:center;'>{fmt_pct(fi)}</td>"
                        f"<td style='padding:4px 6px;text-align:center;font-weight:700;'>"
                        f"{fmt_pct(cu)}</td>"
                        f"</tr>"
                    )
                rows_html += "</table>"
                st.markdown(rows_html, unsafe_allow_html=True)
            else:
                st.warning("Simulation returned no results.")
        return

    # ── Projected bracket (pre-playoffs) ──────────────────────────────────
    st.markdown("#### Projected Playoff Bracket *(Projected)*")
    st.caption("Based on current standings — seeds may change as the season progresses.")

    if not team_metrics_dict:
        st.info("Team metrics unavailable for bracket projection.")
        return

    # Build projected matchups from bracket map
    # We need conference standings to project seeds
    standings = get_standings()
    if standings is None or standings.empty:
        st.info("Standings data unavailable for bracket projection.")
        return

    for conf in sorted(standings["conference"].dropna().unique()):
        conf_df = standings[standings["conference"] == conf].sort_values("conferenceSequence")
        top8 = conf_df.head(8)
        if len(top8) < 8:
            st.info(f"Not enough teams for {conf} bracket projection.")
            continue

        st.markdown(f"##### {conf}")
        teams_list = top8["teamAbbrev"].tolist()

        matchups = []
        for seed, opp_seed in PLAYOFF_BRACKET_MAP.items():
            if seed < opp_seed and seed <= 4:
                a = teams_list[seed - 1] if seed <= len(teams_list) else "???"
                b = teams_list[opp_seed - 1] if opp_seed <= len(teams_list) else "???"
                matchups.append((seed, a, opp_seed, b))

        cols = st.columns(max(len(matchups), 1))
        for i, (sa, a, sb, b) in enumerate(matchups):
            cols[i].markdown(
                _series_card_html(a, b, 0, 0,
                                  confidence=f"#{sa} vs #{sb} (Projected)"),
                unsafe_allow_html=True,
            )
