"""CSS styles for the Streamlit dashboard."""

import streamlit as st

DASHBOARD_CSS = """
<style>
.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
    max-width: 1450px;
}
.kpi-card {
    background: #ffffff;
    border: 1px solid rgba(15,23,42,.08);
    border-radius: 16px;
    padding: 16px 18px;
    box-shadow: 0 8px 24px rgba(15,23,42,.05);
    min-height: 110px;
}
.kpi-label {
    color: #64748b;
    font-size: 0.88rem;
    margin-bottom: .35rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .03em;
}
.kpi-value {
    color: #0f172a;
    font-size: 1.9rem;
    font-weight: 800;
    line-height: 1.1;
}
.kpi-sub {
    color: #475569;
    font-size: 0.88rem;
    margin-top: .25rem;
}
.panel {
    background: #ffffff;
    border: 1px solid rgba(15,23,42,.08);
    border-radius: 18px;
    padding: 14px 16px 6px 16px;
    box-shadow: 0 8px 24px rgba(15,23,42,.05);
}
.section-title {
    font-size: 1.25rem;
    font-weight: 800;
    color: #0f172a;
    margin: 0 0 .45rem 0;
}
.muted { color: #64748b; font-size: 0.95rem; }
.stTabs [data-baseweb="tab-list"] { gap: .5rem; }
.stTabs [data-baseweb="tab"] {
    height: 44px;
    border-radius: 12px;
    padding-left: 14px;
    padding-right: 14px;
    background: #f8fafc;
    border: 1px solid rgba(15,23,42,.06);
}
.stTabs [aria-selected="true"] {
    background: #eff6ff !important;
    border: 1px solid rgba(37,99,235,.18) !important;
}
div[data-testid="stHorizontalBlock"] > div { overflow: visible !important; }
.prob-bar-wrap {
    background: #e2e8f0;
    border-radius: 6px;
    height: 20px;
    overflow: hidden;
    margin: 3px 0 6px 0;
}
.prob-bar-fill {
    height: 100%;
    border-radius: 6px;
    display: flex;
    align-items: center;
    padding-left: 8px;
    font-size: 0.78rem;
    font-weight: 700;
    color: #fff;
    white-space: nowrap;
    min-width: 32px;
}
</style>
"""


def inject_css() -> None:
    """Inject dashboard CSS into the current Streamlit page."""
    st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)
