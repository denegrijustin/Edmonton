"""Compare tab (Tab 4) — side-by-side team comparison using CSS grid."""

from typing import Any, Dict, List, Tuple

import streamlit as st

from models.projections import compute_outlook
from providers.metrics_provider import compute_team_metrics
from ui.components import logo_card_html
from utils.formatters import fmt_record, safe_format
from utils.logos import logo_url
from utils.stoplights import stoplight


# CSS grid layout for the comparison table
_GRID_CSS = """
<style>
.cmp-grid {
  display: grid;
  grid-template-columns: 1fr 140px 1fr;
  gap: 0;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  font-family: inherit;
}
.cmp-grid .cmp-header {
  background: #f8fafc;
  font-weight: 700;
  font-size: 0.95rem;
  padding: 10px 12px;
  border-bottom: 2px solid #e2e8f0;
}
.cmp-grid .cmp-left  { text-align: right; }
.cmp-grid .cmp-mid   { text-align: center; background: #f8fafc; }
.cmp-grid .cmp-right { text-align: left; }
.cmp-grid .cmp-row-left  {
  text-align: right;
  padding: 6px 8px;
  font-size: 0.93rem;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: middle;
}
.cmp-grid .cmp-row-mid {
  text-align: center;
  padding: 6px 8px;
  font-size: 0.80rem;
  color: #64748b;
  font-weight: 600;
  background: #f8fafc;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: middle;
}
.cmp-grid .cmp-row-right {
  text-align: left;
  padding: 6px 8px;
  font-size: 0.93rem;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: middle;
}
@media (max-width: 640px) {
  .cmp-grid .cmp-row-left,
  .cmp-grid .cmp-row-right { font-size: 0.82rem; }
  .cmp-grid .cmp-row-mid   { font-size: 0.72rem; }
}
</style>
"""


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

    # ── Logo headers ──────────────────────────────────────────────────────────
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

    # ── CSS grid comparison table ─────────────────────────────────────────────
    # Metric definitions: (label, val_a, val_b, good, bad, higher_is_better, fmt_str)
    metrics_def = [
        ("Current Points",    ma["points"],                       mb["points"],                       90,  70,  True,  "{:.0f}"),
        ("Proj. Points",      oa["projected_points"],             ob["projected_points"],             95,  80,  True,  "{:.0f}"),
        ("Playoff Odds %",    oa["playoff_odds"],                 ob["playoff_odds"],                 70,  45,  True,  "{:.0f}"),
        ("Goal Differential", ma["goalDifferential"],             mb["goalDifferential"],             10,  -10, True,  "{:+.0f}"),
        ("GF / Game",         ma["gf_per_game"],                  mb["gf_per_game"],                  3.2, 2.8, True,  "{:.2f}"),
        ("GA / Game",         ma["ga_per_game"],                  mb["ga_per_game"],                  2.5, 3.0, False, "{:.2f}"),
        ("Momentum",          ma["momentum"],                     mb["momentum"],                     55,  45,  True,  "{:.0f}"),
        ("Last 10 GF/G",      ma["last10_gf_per_game"],           mb["last10_gf_per_game"],           3.2, 2.8, True,  "{:.2f}"),
        ("Last 10 GA/G",      ma["last10_ga_per_game"],           mb["last10_ga_per_game"],           2.5, 3.0, False, "{:.2f}"),
        ("Last 10 Pts",       ma["l10W"] * 2 + ma["l10OTL"],     mb["l10W"] * 2 + mb["l10OTL"],     14,  10,  True,  "{:.0f} pts"),
    ]

    def _fmt_val(fmt_str: str, val: Any) -> str:
        return safe_format(fmt_str, val, str(val) if val is not None else "—")

    def _sl(val: Any, good: float, bad: float, hib: bool) -> str:
        try:
            return stoplight(float(val), good, bad, hib)
        except Exception:
            return "⚪"

    # Build the HTML grid
    rows_html = ""
    for label, va, vb, good, bad, hib, fmt in metrics_def:
        va_s = _fmt_val(fmt, va)
        vb_s = _fmt_val(fmt, vb)
        sl_a = _sl(va, good, bad, hib)
        sl_b = _sl(vb, good, bad, hib)
        rows_html += (
            f"<div class='cmp-row-left'>{sl_a} <b>{va_s}</b></div>"
            f"<div class='cmp-row-mid'>{label}</div>"
            f"<div class='cmp-row-right'><b>{vb_s}</b> {sl_b}</div>"
        )

    grid_html = f"""
{_GRID_CSS}
<div class="cmp-grid">
  <div class="cmp-header cmp-left" style="color:#1d4ed8;">{team_a_sel}</div>
  <div class="cmp-header cmp-mid">Metric</div>
  <div class="cmp-header cmp-right" style="color:#dc2626;">{team_b_sel}</div>
  {rows_html}
</div>
"""
    st.markdown(grid_html, unsafe_allow_html=True)

    st.markdown("---")

    # ── Projected opponents ───────────────────────────────────────────────────
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
