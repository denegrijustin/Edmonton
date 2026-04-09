"""Schedule view — upcoming games and remaining schedule difficulty."""

import streamlit as st
import pandas as pd

from ui.components import upcoming_card_html, kpi_html
from utils.formatters import fmt_pct, fmt_number
from utils.logos import logo_url
from utils.streamlit_keys import mk_key
from utils.validators import safe_numeric, safe_int


_PAGE = "schedule"


def _logo_img(abbrev: str, size: int = 28) -> str:
    return (
        f"<img src='{logo_url(abbrev)}' width='{size}' height='{size}' "
        f"style='object-fit:contain;vertical-align:middle;'/>"
    )


def _opp_record(opp_abbrev: str, standings_df) -> str:
    """Lookup opponent record from standings."""
    if standings_df is None or standings_df.empty:
        return "—"
    match = standings_df[standings_df["teamAbbrev"] == opp_abbrev]
    if match.empty:
        return "—"
    r = match.iloc[0]
    w = safe_int(r.get("wins"))
    lo = safe_int(r.get("losses"))
    otl = safe_int(r.get("otLosses"))
    return f"{w}-{lo}-{otl}"


def _opp_pts_pct(opp_abbrev: str, standings_df) -> float:
    if standings_df is None or standings_df.empty:
        return 0.0
    match = standings_df[standings_df["teamAbbrev"] == opp_abbrev]
    if match.empty:
        return 0.0
    pp = safe_numeric(match.iloc[0].get("pointPctg"))
    return pp if pp > 1 else pp * 100


# ── Main render ───────────────────────────────────────────────────────────────

def render(selected_team, sel_schedule, standings_df, team_metrics_dict, team_name_map):
    """Render the Schedule tab."""
    try:
        _render_inner(selected_team, sel_schedule, standings_df,
                      team_metrics_dict, team_name_map)
    except Exception as exc:
        st.error(f"Schedule view could not be rendered: {exc}")


def _render_inner(selected_team, sel_schedule, standings_df,
                  team_metrics_dict, team_name_map):
    if sel_schedule is None or sel_schedule.empty:
        st.info("Schedule data is unavailable for this team.")
        return

    # Determine upcoming games
    if "isCompleted" in sel_schedule.columns:
        upcoming = sel_schedule[sel_schedule["isCompleted"] == False].copy()
    elif "gameState" in sel_schedule.columns:
        upcoming = sel_schedule[~sel_schedule["gameState"].isin(["OFF", "FINAL"])].copy()
    else:
        upcoming = pd.DataFrame()

    # ── Upcoming games cards ──────────────────────────────────────────────
    st.markdown("#### Upcoming Games")
    if upcoming.empty:
        st.info("No upcoming games found.")
    else:
        show = upcoming.head(5)
        cols = st.columns(min(len(show), 5))
        for i, (_, g) in enumerate(show.iterrows()):
            home = g.get("homeTeam", "")
            away = g.get("awayTeam", "")
            opp = away if home == selected_team else home
            venue = "Home" if home == selected_team else "Away"
            date_str = str(g.get("gameDate", ""))[:10]
            rec = _opp_record(opp, standings_df)
            cols[i].markdown(
                upcoming_card_html(opp, f"{venue} · {date_str}", f"Opp: {rec}"),
                unsafe_allow_html=True,
            )

    # ── Remaining schedule difficulty ─────────────────────────────────────
    st.markdown("#### Remaining Schedule Difficulty")
    if upcoming.empty:
        st.info("No remaining games to analyze.")
        return

    opp_list = []
    for _, g in upcoming.iterrows():
        home = g.get("homeTeam", "")
        away = g.get("awayTeam", "")
        opp = away if home == selected_team else home
        pp = _opp_pts_pct(opp, standings_df)
        opp_gd = 0
        if standings_df is not None and not standings_df.empty:
            match = standings_df[standings_df["teamAbbrev"] == opp]
            if not match.empty:
                opp_gd = safe_int(match.iloc[0].get("goalDifferential"))
        opp_list.append({"opponent": opp, "pts_pct": pp, "gd": opp_gd})

    if not opp_list:
        return

    opp_df = pd.DataFrame(opp_list)
    avg_pct = opp_df["pts_pct"].mean()

    kc = st.columns(3)
    kc[0].markdown(kpi_html("Remaining Games", str(len(opp_df))), unsafe_allow_html=True)
    kc[1].markdown(kpi_html("Avg Opp Pts%", fmt_pct(avg_pct)), unsafe_allow_html=True)
    avg_gd = opp_df["gd"].mean()
    kc[2].markdown(kpi_html("Avg Opp GD", f"{avg_gd:+.1f}"), unsafe_allow_html=True)

    # Strength heat map table
    st.markdown("**Opponent Strength**")
    rows_html = (
        "<table style='width:100%;border-collapse:collapse;font-size:0.82rem;'>"
        "<tr style='border-bottom:2px solid #e2e8f0;'>"
        "<th style='text-align:left;padding:4px 6px;'>Opponent</th>"
        "<th style='padding:4px 6px;'>Pts%</th>"
        "<th style='padding:4px 6px;'>GD</th>"
        "<th style='padding:4px 6px;'>Strength</th></tr>"
    )
    for _, orow in opp_df.iterrows():
        opp = orow["opponent"]
        pp = orow["pts_pct"]
        gd = orow["gd"]
        # Heat color for strength
        if pp >= 60:
            bg = "#fecaca"
        elif pp >= 50:
            bg = "#fef3c7"
        else:
            bg = "#bbf7d0"
        rows_html += (
            f"<tr style='border-bottom:1px solid #f1f5f9;'>"
            f"<td style='padding:4px 6px;'>{_logo_img(opp, 22)} {team_name_map.get(opp, opp)}</td>"
            f"<td style='padding:4px 6px;text-align:center;'>{pp:.0f}%</td>"
            f"<td style='padding:4px 6px;text-align:center;'>{gd:+d}</td>"
            f"<td style='padding:4px 6px;text-align:center;background:{bg};'>"
            f"{'Hard' if pp >= 60 else 'Medium' if pp >= 50 else 'Easy'}</td>"
            f"</tr>"
        )
    rows_html += "</table>"
    st.markdown(rows_html, unsafe_allow_html=True)
