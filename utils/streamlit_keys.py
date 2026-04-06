"""Centralised Streamlit element-key generation.

Provides deterministic, unique ``key=`` values for Streamlit widgets and
charts so that ``StreamlitDuplicateElementId`` errors cannot occur when the
same component type is reused across tabs, columns, or loops.

Key pattern
-----------
``{page}__{component}__{detail}``

All segments are lower-cased and non-alphanumeric characters are replaced
with underscores so the resulting key is safe to pass directly to any
Streamlit widget.

Usage example
-------------
>>> from utils.streamlit_keys import mk_key
>>> st.plotly_chart(fig, key=mk_key("trends", "chart", "rolling_5"))
>>> st.dataframe(df,   key=mk_key("trends", "dataframe", "game_log"))
"""

import re
from typing import Any

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: Any) -> str:
    """Return a lowercase, underscored slug from *text*."""
    return _SLUG_RE.sub("_", str(text).lower()).strip("_")


def mk_key(page: str, component: str, detail: str = "") -> str:
    """Build a unique Streamlit element key.

    Parameters
    ----------
    page : str
        Tab or page name (e.g. ``"trends"``, ``"overview"``).
    component : str
        Widget type (e.g. ``"chart"``, ``"dataframe"``, ``"selectbox"``).
    detail : str, optional
        Additional disambiguating segment such as team abbreviation, chart
        purpose, or time-frame (e.g. ``"rolling_5"``, ``"edm_goal_diff"``).

    Returns
    -------
    str
        Deterministic key in the form ``page__component__detail`` (or
        ``page__component`` when *detail* is empty).
    """
    parts = [_slug(page), _slug(component)]
    if detail:
        parts.append(_slug(detail))
    return "__".join(parts)
