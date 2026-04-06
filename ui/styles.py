"""Shared CSS styling for the dashboard."""

DASHBOARD_CSS = """
<style>
.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
    max-width: 1500px;
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
    font-size: 0.82rem;
    margin-bottom: .25rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .03em;
}
.kpi-value {
    color: #0f172a;
    font-size: 1.8rem;
    font-weight: 800;
    line-height: 1.1;
}
.kpi-sub {
    color: #475569;
    font-size: 0.85rem;
    margin-top: .2rem;
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
.muted {
    color: #64748b;
    font-size: 0.95rem;
}
div[data-testid="stHorizontalBlock"] > div {
    overflow: visible !important;
}
.stTabs [data-baseweb="tab-list"] {
    gap: .5rem;
}
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
.team-logo {
    width: 32px;
    height: 32px;
    vertical-align: middle;
}
.team-logo-lg {
    width: 64px;
    height: 64px;
    vertical-align: middle;
}
.stoplight-dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-right: 4px;
}
.sl-green { background-color: #22c55e; }
.sl-yellow { background-color: #eab308; }
.sl-red { background-color: #ef4444; }
</style>
"""
