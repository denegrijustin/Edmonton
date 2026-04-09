"""Comparison view — side-by-side team stat comparison with heat maps."""

import streamlit as st
import pandas as pd

from ui.components import kpi_html, logo_card_html
from utils.formatters import fmt_pct, fmt_signed_int, fmt_number, fmt_record
from utils.logos import logo_url
from utils.streamlit_keys import mk_key
from utils.validators import safe_numeric, safe_int


_PAGE = "comparison"


def _logo_img(abbrev: str, size: int = 36) -> str:
    return (
        f"<img src='{logo_url(abbrev)}' width='{size}' height='{size}' "
        f"style='object-fit:contain;vertical-align:middle;'/>"
    )


def _heat_color(val_a: float, val_b: float, higher_is_better: bool = True) -> tuple:
    """Return (color_a, color_b) based on who is better."""
    if val_a == val_b:
        return ("#f1f5f9", "#f1f5f9")
    if higher_is_better:
        better_a = val_a > val_b
    else:
        better_a = val_a < val_b
    if better_a:
        return ("#bbf7d0", "#fecaca")
    return ("#fecaca", "#bbf7d0")


def _get_metrics(abbrev: str, standings_df, team_metrics_dict):
    """Build a metrics dict for comparison from available data."""
    m = team_metrics_dict.get(abbrev, {}) if team_metrics_dict else {}
    row = None
    if standings_df is not None and not standings_df.empty:
        match = standings_df[standings_df["teamAbbrev"] == abbrev]
        if not match.empty:
            row = match.iloc[0]

    return {
        "abbrev": abbrev,
        "wins": safe_int(m.get("wins") or (row.get("wins") if row is not None else 0)),
        "losses": safe_int(m.get("losses") or (row.get("losses") if row is not None else 0)),
        "otl": safe_int(m.get("otl") or (row.get("otLosses") if row is not None else 0)),
        "points": safe_int(m.get("points") or (row.get("points") if row is not None else 0)),
        "gp": safe_int(m.get("gamesPlayed") or (row.get("gamesPlayed") if row is not None else 0)),
        "gf_pg": safe_numeric(m.get("gf_per_game")),
        "ga_pg": safe_numeric(m.get("ga_per_game")),
        "l10_gf": safe_numeric(m.get("last10_gf_per_game")),
        "l10_ga": safe_numeric(m.get("last10_ga_per_game")),
        "gd": safe_int(m.get("goalDifferential") or (row.get("goalDifferential") if row is not None else 0)),
        "momentum": safe_numeric(m.get("momentum")),
        "l10w": safe_int(m.get("l10W") or (row.get("l10Wins") if row is not None else 0)),
        "l10l": safe_int(m.get("l10L") or (row.get("l10Losses") if row is not None else 0)),
        "l10o": safe_int(m.get("l10OTL") or (row.get("l10OtLosses") if row is not None else 0)),
        "pts_pct": safe_numeric(
            (row.get("pointPctg") if row is not None else 0)
        ),
    }


def _stat_row(label, val_a, val_b, fmt_fn, higher_is_better=True):
    """Render a single comparison row as HTML."""
    a = safe_numeric(val_a)
    b = safe_numeric(val_b)
    ca, cb = _heat_color(a, b, higher_is_better)
    return (
        f"<tr>"
        f"<td style='padding:5px 8px;background:{ca};text-align:center;"
        f"font-weight:600;'>{fmt_fn(val_a)}</td>"
        f"<td style='padding:5px 8px;text-align:center;font-weight:700;'>{label}</td>"
        f"<td style='padding:5px 8px;background:{cb};text-align:center;"
        f"font-weight:600;'>{fmt_fn(val_b)}</td>"
        f"</tr>"
    )


# ── Main render ───────────────────────────────────────────────────────────────

def render(all_teams, standings_df, team_metrics_dict, team_name_map):
    """Render the Comparison tab."""
    try:
        _render_inner(all_teams, standings_df, team_metrics_dict, team_name_map)
    except Exception as exc:
        st.error(f"Comparison view could not be rendered: {exc}")


def _render_inner(all_teams, standings_df, team_metrics_dict, team_name_map):
    if not all_teams or len(all_teams) < 2:
        st.info("Not enough teams available for comparison.")
        return

    sorted_teams = sorted(all_teams)
    cols = st.columns(2)
    with cols[0]:
        team_a = st.selectbox(
            "Team A",
            sorted_teams,
            index=0,
            format_func=lambda t: f"{t} — {team_name_map.get(t, t)}",
            key=mk_key(_PAGE, "team_a"),
        )
    with cols[1]:
        default_b = 1 if len(sorted_teams) > 1 else 0
        team_b = st.selectbox(
            "Team B",
            sorted_teams,
            index=default_b,
            format_func=lambda t: f"{t} — {team_name_map.get(t, t)}",
            key=mk_key(_PAGE, "team_b"),
        )

    if team_a == team_b:
        st.warning("Select two different teams to compare.")
        return

    ma = _get_metrics(team_a, standings_df, team_metrics_dict)
    mb = _get_metrics(team_b, standings_df, team_metrics_dict)

    # ── Logo headers ──────────────────────────────────────────────────────
    hc = st.columns([1, 2, 1])
    hc[0].markdown(
        f"<div style='text-align:center;'>{_logo_img(team_a, 64)}<br/>"
        f"<b>{team_name_map.get(team_a, team_a)}</b></div>",
        unsafe_allow_html=True,
    )
    hc[1].markdown(
        "<div style='text-align:center;font-size:1.3rem;font-weight:800;"
        "padding-top:20px;'>VS</div>",
        unsafe_allow_html=True,
    )
    hc[2].markdown(
        f"<div style='text-align:center;'>{_logo_img(team_b, 64)}<br/>"
        f"<b>{team_name_map.get(team_b, team_b)}</b></div>",
        unsafe_allow_html=True,
    )

    # ── Comparison heat map table ─────────────────────────────────────────
    fmt_f1 = lambda v: f"{safe_numeric(v):.2f}"
    fmt_i = lambda v: str(safe_int(v))
    fmt_si = lambda v: f"{safe_int(v):+d}"
    fmt_p = lambda v: fmt_pct(safe_numeric(v) * 100 if safe_numeric(v) < 1 else safe_numeric(v))
    fmt_m = lambda v: f"{safe_numeric(v):.0f}"

    table = (
        "<table style='width:100%;border-collapse:collapse;font-size:0.85rem;margin-top:12px;'>"
        "<tr style='border-bottom:2px solid #e2e8f0;'>"
        f"<th style='padding:6px;text-align:center;'>{team_a}</th>"
        "<th style='padding:6px;text-align:center;'>Stat</th>"
        f"<th style='padding:6px;text-align:center;'>{team_b}</th></tr>"
    )

    # Record
    table += (
        f"<tr><td style='padding:5px 8px;text-align:center;font-weight:600;'>"
        f"{fmt_record(ma['wins'], ma['losses'], ma['otl'])}</td>"
        f"<td style='padding:5px 8px;text-align:center;font-weight:700;'>Record</td>"
        f"<td style='padding:5px 8px;text-align:center;font-weight:600;'>"
        f"{fmt_record(mb['wins'], mb['losses'], mb['otl'])}</td></tr>"
    )

    table += _stat_row("Points", ma["points"], mb["points"], fmt_i)
    table += _stat_row("Pts %", ma["pts_pct"], mb["pts_pct"], fmt_p)
    table += _stat_row("GF/G", ma["gf_pg"], mb["gf_pg"], fmt_f1)
    table += _stat_row("GA/G", ma["ga_pg"], mb["ga_pg"], fmt_f1, higher_is_better=False)
    table += _stat_row("L10 GF/G", ma["l10_gf"], mb["l10_gf"], fmt_f1)
    table += _stat_row("L10 GA/G", ma["l10_ga"], mb["l10_ga"], fmt_f1, higher_is_better=False)
    table += _stat_row("Goal Diff", ma["gd"], mb["gd"], fmt_si)
    table += _stat_row("Momentum", ma["momentum"], mb["momentum"], fmt_m)
    table += _stat_row("Last 10", f"{ma['l10w']}-{ma['l10l']}-{ma['l10o']}",
                       f"{mb['l10w']}-{mb['l10l']}-{mb['l10o']}",
                       lambda v: str(v))
    table += "</table>"
    st.markdown(table, unsafe_allow_html=True)

    # ── Why model favors section ──────────────────────────────────────────
    st.markdown("#### Why the Model Favors Each Team")
    reasons_a = _build_reasons(ma, mb, team_name_map.get(team_a, team_a))
    reasons_b = _build_reasons(mb, ma, team_name_map.get(team_b, team_b))

    rc = st.columns(2)
    with rc[0]:
        st.markdown(f"**{team_name_map.get(team_a, team_a)}**")
        for r in reasons_a[:3]:
            st.markdown(f"• {r}")
    with rc[1]:
        st.markdown(f"**{team_name_map.get(team_b, team_b)}**")
        for r in reasons_b[:3]:
            st.markdown(f"• {r}")


def _build_reasons(me, them, name):
    """Generate up to 3 data-backed reasons why a team has an edge."""
    reasons = []
    if me["gf_pg"] > them["gf_pg"]:
        reasons.append(f"Higher scoring ({me['gf_pg']:.2f} vs {them['gf_pg']:.2f} GF/G)")
    if me["ga_pg"] < them["ga_pg"]:
        reasons.append(f"Better defense ({me['ga_pg']:.2f} vs {them['ga_pg']:.2f} GA/G)")
    if me["momentum"] > them["momentum"]:
        reasons.append(f"Stronger recent form (momentum {me['momentum']:.0f} vs {them['momentum']:.0f})")
    if me["gd"] > them["gd"]:
        reasons.append(f"Better goal differential ({me['gd']:+d} vs {them['gd']:+d})")
    if me["points"] > them["points"]:
        reasons.append(f"More points ({me['points']} vs {them['points']})")
    if me["l10_gf"] > them["l10_gf"]:
        reasons.append(f"Scoring more in last 10 ({me['l10_gf']:.2f} GF/G)")
    if not reasons:
        reasons.append("No clear statistical advantage based on available data")
    return reasons
