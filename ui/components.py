"""Reusable UI components — KPI cards, logos, stoplight badges."""

from __future__ import annotations

import streamlit as st

from config.teams import TEAM_LOGOS, TEAMS


def team_logo_html(abbrev: str, size: int = 32) -> str:
    """Return an img tag for a team logo."""
    url = TEAM_LOGOS.get(abbrev, "")
    alt = TEAMS.get(abbrev, {}).get("name", abbrev)
    return f'<img src="{url}" alt="{alt}" width="{size}" height="{size}" style="vertical-align:middle;">'


def team_logo_with_name(abbrev: str, size: int = 28) -> str:
    """Logo + short name."""
    name = TEAMS.get(abbrev, {}).get("name", abbrev)
    logo = team_logo_html(abbrev, size)
    return f'{logo} <span style="margin-left:6px; font-weight:600;">{name}</span>'


def kpi_card(label: str, value: str, sub: str = "", stoplight_color: str = "") -> str:
    """Return HTML for a KPI card."""
    dot = ""
    if stoplight_color:
        color_map = {"green": "#22c55e", "yellow": "#eab308", "red": "#ef4444"}
        c = color_map.get(stoplight_color, "")
        if c:
            dot = f'<span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:{c}; margin-left:8px;"></span>'
    return f"""<div class='kpi-card'>
        <div class='kpi-label'>{label}</div>
        <div class='kpi-value'>{value}{dot}</div>
        <div class='kpi-sub'>{sub}</div>
    </div>"""


def render_kpi(label: str, value: str, sub: str = "", stoplight_color: str = "") -> None:
    """Render a KPI card in the current Streamlit column."""
    st.markdown(kpi_card(label, value, sub, stoplight_color), unsafe_allow_html=True)


def stoplight_dot(color: str) -> str:
    """Return a colored dot span."""
    color_map = {"green": "#22c55e", "yellow": "#eab308", "red": "#ef4444"}
    c = color_map.get(color, "#94a3b8")
    return f'<span style="color:{c}; font-size:1.2em;">●</span>'


def stoplight_for_value(value: float, green: float, yellow: float, invert: bool = False) -> str:
    """Return stoplight color name for a value."""
    import pandas as pd
    if pd.isna(value):
        return ""
    if invert:
        if value <= yellow:
            return "green"
        if value <= green:
            return "yellow"
        return "red"
    else:
        if value >= green:
            return "green"
        if value >= yellow:
            return "yellow"
        return "red"
