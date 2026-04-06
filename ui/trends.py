"""Trends tab (Tab 2) — rolling trends, game log, upcoming schedule."""

from typing import Any, Dict

import pandas as pd
import streamlit as st

from ui.charts import (
    plot_goal_diff_trend,
    plot_momentum,
    plot_points_path,
    plot_rolling_trend,
)
from ui.components import result_card_html, upcoming_card_html
from utils.stoplights import sl_momentum, sl_result
from utils.streamlit_keys import mk_key


def render(
    selected_team: str,
    sel_tg: pd.DataFrame,
    sel_schedule: pd.DataFrame,
    sel_outlook: Dict[str, Any],
) -> None:
    """Render the Trends tab content."""
    if sel_tg.empty:
        st.info("No game data available for the selected team.")
        return

    tc1, tc2 = st.columns(2)
    with tc1:
        st.plotly_chart(
            plot_rolling_trend(sel_tg, window=5),
            width="stretch",
            key=mk_key("trends", "chart", "rolling_5"),
        )
    with tc2:
        st.plotly_chart(
            plot_rolling_trend(sel_tg, window=10),
            width="stretch",
            key=mk_key("trends", "chart", "rolling_10"),
        )

    st.plotly_chart(
        plot_goal_diff_trend(sel_tg),
        width="stretch",
        key=mk_key("trends", "chart", "goal_diff"),
    )
    st.plotly_chart(
        plot_points_path(sel_tg, sel_outlook.get("projected_points", 0)),
        width="stretch",
        key=mk_key("trends", "chart", "points_path"),
    )

    # Last 5 results
    st.markdown("### Last 5 Games")
    last5_tr = sel_tg.tail(5)
    lc = st.columns(min(5, max(len(last5_tr), 1)))
    for _i, (_, _row) in enumerate(last5_tr.iterrows()):
        if _i >= 5:
            break
        opp_t = str(_row.get("opponent") or "?")
        res_t = str(_row.get("result") or "?")
        ts_t = int(_row.get("teamScore") or 0)
        os_t = int(_row.get("oppScore") or 0)
        ven_t = str(_row.get("venue") or "")
        raw_dt = _row.get("gameDate")
        date_t = (
            pd.to_datetime(raw_dt).strftime("%b %d")
            if raw_dt is not None and pd.notna(raw_dt)
            else ""
        )
        with lc[_i]:
            st.markdown(
                result_card_html(opp_t, res_t, f"{ts_t}–{os_t}", f"{ven_t} · {date_t}"),
                unsafe_allow_html=True,
            )

    # Next 5 upcoming
    st.markdown("### Next 5 Games")
    if not sel_schedule.empty:
        upcoming5 = (
            sel_schedule[~sel_schedule["isCompleted"]]
            .sort_values("gameDate")
            .head(5)
        )
        if not upcoming5.empty:
            uc = st.columns(min(5, len(upcoming5)))
            for _i, (_, _row) in enumerate(upcoming5.iterrows()):
                if _i >= 5:
                    break
                opp_u = str(
                    _row["awayTeam"] if _row["homeTeam"] == selected_team else _row["homeTeam"]
                )
                ven_u = "Home" if _row["homeTeam"] == selected_team else "Away"
                raw_du = _row.get("gameDate")
                date_u = (
                    pd.to_datetime(raw_du).strftime("%b %d")
                    if raw_du is not None and pd.notna(raw_du)
                    else "TBD"
                )
                with uc[_i]:
                    st.markdown(
                        upcoming_card_html(opp_u, ven_u, date_u),
                        unsafe_allow_html=True,
                    )
        else:
            st.info("No upcoming games found in schedule.")
    else:
        st.info("Schedule data unavailable.")

    # Full game log
    st.markdown("### Full Season Game Log")
    log_df = sel_tg[
        ["gameDate", "venue", "opponent", "teamScore", "oppScore", "result", "goalDiff", "momentumScore"]
    ].copy()
    log_df["gameDate"] = log_df["gameDate"].dt.strftime("%b %d")
    st.dataframe(
        log_df.style.format(
            {"momentumScore": "{:.1f}", "goalDiff": "{:+.0f}"}, na_rep="-"
        )
        .map(sl_result, subset=["result"])
        .map(sl_momentum, subset=["momentumScore"]),
        width="stretch",
        hide_index=True,
        key=mk_key("trends", "dataframe", "game_log"),
    )
