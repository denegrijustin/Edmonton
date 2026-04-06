"""Compare tab (Tab 4) — side-by-side team comparison."""

from typing import Any, Dict, List, Tuple

import streamlit as st

from models.projections import compute_outlook
from providers.metrics_provider import compute_team_metrics
from ui.components import kpi_html, logo_card_html
from utils.formatters import fmt_record, safe_format
from utils.stoplights import stoplight


def render(
    all_teams: List[str],
    standings_df,
    team_metrics_dict: Dict[str, Dict],
    team_name_map: Dict[str, str],
) -> None:
    """Render the Compare tab content."""
    cmp_ac, cmp_bc = st.columns(2)
    with cmp_ac:
        team_a_sel = st.selectbox("Team A", all_teams, index=0, key="cmp_a")
    with cmp_bc:
        _b_default = 1 if len(all_teams) > 1 else 0
        team_b_sel = st.selectbox("Team B", all_teams, index=_b_default, key="cmp_b")

    ma = team_metrics_dict.get(team_a_sel, compute_team_metrics(team_a_sel, standings_df))
    mb = team_metrics_dict.get(team_b_sel, compute_team_metrics(team_b_sel, standings_df))
    oa = compute_outlook(team_a_sel, standings_df, team_metrics_dict)
    ob = compute_outlook(team_b_sel, standings_df, team_metrics_dict)

    # Logo headers
    hdr_a, hdr_vs, hdr_b = st.columns([2, 1, 2])
    with hdr_a:
        st.markdown(
            logo_card_html(
                team_a_sel,
                team_name_map.get(team_a_sel, team_a_sel),
                fmt_record(ma["wins"], ma["losses"], ma["otl"]),
            ),
            unsafe_allow_html=True,
        )
    with hdr_vs:
        st.markdown(
            "<div style='text-align:center;padding:22px 0;font-size:1.4rem;font-weight:800;color:#64748b;'>VS</div>",
            unsafe_allow_html=True,
        )
    with hdr_b:
        st.markdown(
            logo_card_html(
                team_b_sel,
                team_name_map.get(team_b_sel, team_b_sel),
                fmt_record(mb["wins"], mb["losses"], mb["otl"]),
            ),
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Mirrored comparison rows
    def _cmp_rows(
        label: str,
        val_a: Any,
        val_b: Any,
        good: float,
        bad: float,
        hib: bool = True,
        fmt_str: str = "{}",
    ) -> Tuple[str, str, str, str, str]:
        va_s = safe_format(fmt_str, val_a, str(val_a))
        vb_s = safe_format(fmt_str, val_b, str(val_b))
        try:
            sl_a = stoplight(float(val_a), good, bad, hib)
            sl_b = stoplight(float(val_b), good, bad, hib)
        except Exception:
            sl_a = sl_b = "⚪"
        return label, sl_a, va_s, vb_s, sl_b

    cmp_data = [
        _cmp_rows("Current Points", ma["points"], mb["points"], 90, 70, True, "{:.0f}"),
        _cmp_rows("Proj. Points", oa["projected_points"], ob["projected_points"], 95, 80, True, "{:.0f}"),
        _cmp_rows("Playoff Odds %", oa["playoff_odds"], ob["playoff_odds"], 70, 45, True, "{:.0f}"),
        _cmp_rows("Goal Differential", ma["goalDifferential"], mb["goalDifferential"], 10, -10, True, "{:+.0f}"),
        _cmp_rows("GF / Game", ma["gf_per_game"], mb["gf_per_game"], 3.2, 2.8, True, "{:.2f}"),
        _cmp_rows("GA / Game", ma["ga_per_game"], mb["ga_per_game"], 2.5, 3.0, False, "{:.2f}"),
        _cmp_rows("Momentum", ma["momentum"], mb["momentum"], 55, 45, True, "{:.0f}"),
        _cmp_rows("Last 10 GF/G", ma["last10_gf_per_game"], mb["last10_gf_per_game"], 3.2, 2.8, True, "{:.2f}"),
        _cmp_rows("Last 10 GA/G", ma["last10_ga_per_game"], mb["last10_ga_per_game"], 2.5, 3.0, False, "{:.2f}"),
        _cmp_rows(
            "Last 10 Record",
            ma["l10W"] * 2 + ma["l10OTL"],
            mb["l10W"] * 2 + mb["l10OTL"],
            14, 10, True, "{:.0f} pts",
        ),
    ]

    # Column headers
    hc_a, hc_mid, hc_b = st.columns([3, 3, 3])
    hc_a.markdown(f"<div style='text-align:right;font-weight:700;color:#1d4ed8;'>{team_a_sel}</div>", unsafe_allow_html=True)
    hc_mid.markdown("<div style='text-align:center;font-weight:700;color:#64748b;'>Metric</div>", unsafe_allow_html=True)
    hc_b.markdown(f"<div style='text-align:left;font-weight:700;color:#dc2626;'>{team_b_sel}</div>", unsafe_allow_html=True)

    for _lbl, _sla, _va, _vb, _slb in cmp_data:
        _ca, _cb, _cc = st.columns([3, 3, 3])
        _ca.markdown(
            f"<div style='text-align:right;padding:4px 8px;font-size:0.95rem;'>{_sla} <b>{_va}</b></div>",
            unsafe_allow_html=True,
        )
        _cb.markdown(
            f"<div style='text-align:center;padding:4px 8px;font-size:0.82rem;color:#64748b;font-weight:600;'>{_lbl}</div>",
            unsafe_allow_html=True,
        )
        _cc.markdown(
            f"<div style='text-align:left;padding:4px 8px;font-size:0.95rem;'><b>{_vb}</b> {_slb}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    opp_a_col, opp_b_col = st.columns(2)
    with opp_a_col:
        st.markdown(f"**{team_a_sel} Projected Opponent**")
        _opp_a = oa.get("projected_opponent")
        if _opp_a:
            st.markdown(
                logo_card_html(_opp_a, _opp_a, team_name_map.get(_opp_a, "")),
                unsafe_allow_html=True,
            )
        else:
            st.markdown("<span class='muted'>Not projected for playoffs</span>", unsafe_allow_html=True)
    with opp_b_col:
        st.markdown(f"**{team_b_sel} Projected Opponent**")
        _opp_b = ob.get("projected_opponent")
        if _opp_b:
            st.markdown(
                logo_card_html(_opp_b, _opp_b, team_name_map.get(_opp_b, "")),
                unsafe_allow_html=True,
            )
        else:
            st.markdown("<span class='muted'>Not projected for playoffs</span>", unsafe_allow_html=True)
