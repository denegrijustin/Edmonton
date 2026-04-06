"""MoneyPuck playoff predictions provider.

Loads league-wide playoff probabilities from MoneyPuck at app startup
and caches them.  Falls back gracefully on parse failure.
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional

import numpy as np
import requests

from config.settings import MONEYPUCK_CACHE_TTL, MONEYPUCK_URL, TIMEOUT
from data.cache import SourceCache
from utils.validators import validate_probability

logger = logging.getLogger(__name__)

# ── Team-abbreviation mapping ─────────────────────────────────────────────────
# MoneyPuck uses full city names or short identifiers on its HTML page.
# Map them to standard 3-letter NHL abbreviations used by the rest of the app.
_MONEYPUCK_TEAM_MAP: Dict[str, str] = {
    "Anaheim": "ANA", "Arizona": "ARI", "Boston": "BOS", "Buffalo": "BUF",
    "Calgary": "CGY", "Carolina": "CAR", "Chicago": "CHI", "Colorado": "COL",
    "Columbus": "CBJ", "Dallas": "DAL", "Detroit": "DET", "Edmonton": "EDM",
    "Florida": "FLA", "Los Angeles": "LAK", "Minnesota": "MIN",
    "Montréal": "MTL", "Montreal": "MTL", "Nashville": "NSH",
    "New Jersey": "NJD", "NY Islanders": "NYI", "NY Rangers": "NYR",
    "New York Islanders": "NYI", "New York Rangers": "NYR",
    "Ottawa": "OTT", "Philadelphia": "PHI", "Pittsburgh": "PIT",
    "San Jose": "SJS", "Seattle": "SEA", "St. Louis": "STL",
    "St Louis": "STL", "Tampa Bay": "TBL", "Toronto": "TOR",
    "Utah": "UTA", "Vancouver": "VAN", "Vegas": "VGK",
    "Washington": "WSH", "Winnipeg": "WPG",
    # Abbreviation-to-abbreviation passthrough
    "ANA": "ANA", "ARI": "ARI", "BOS": "BOS", "BUF": "BUF",
    "CGY": "CGY", "CAR": "CAR", "CHI": "CHI", "COL": "COL",
    "CBJ": "CBJ", "DAL": "DAL", "DET": "DET", "EDM": "EDM",
    "FLA": "FLA", "LAK": "LAK", "L.A.": "LAK", "MIN": "MIN",
    "MTL": "MTL", "NSH": "NSH", "NJD": "NJD", "NYI": "NYI",
    "NYR": "NYR", "OTT": "OTT", "PHI": "PHI", "PIT": "PIT",
    "SJS": "SJS", "S.J.": "SJS", "SEA": "SEA", "STL": "STL",
    "TBL": "TBL", "T.B.": "TBL", "TOR": "TOR", "UTA": "UTA",
    "VAN": "VAN", "VGK": "VGK", "WSH": "WSH", "WPG": "WPG",
}

# Module-level cache
_cache = SourceCache()
_CACHE_KEY = "moneypuck_playoff"


def map_team_name(raw_name: str) -> Optional[str]:
    """Map a MoneyPuck team identifier to a standard NHL abbreviation."""
    if not raw_name:
        return None
    clean = raw_name.strip()
    if clean in _MONEYPUCK_TEAM_MAP:
        return _MONEYPUCK_TEAM_MAP[clean]
    # Try case-insensitive partial match
    lower = clean.lower()
    for key, abbrev in _MONEYPUCK_TEAM_MAP.items():
        if key.lower() == lower:
            return abbrev
    return None


def _parse_predictions_html(html: str) -> List[Dict[str, Any]]:
    """Parse MoneyPuck predictions HTML into a list of team records.

    Extracts rows from the main predictions table.  Each record contains:
    - team_raw: original team name from source
    - team: mapped NHL abbreviation (or None)
    - playoff_pct: playoff probability (0-100)
    - make_playoffs: boolean shorthand
    - presidents_pct: President's Trophy probability (may be None)
    - cup_pct: Stanley Cup probability (may be None)
    """
    rows: List[Dict[str, Any]] = []

    # Strategy: look for table rows containing percentage values
    # MoneyPuck tables use <tr> with <td> cells
    tr_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
    td_pattern = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL | re.IGNORECASE)
    tag_strip = re.compile(r"<[^>]+>")

    for tr_match in tr_pattern.finditer(html):
        tr_content = tr_match.group(1)
        cells = [tag_strip.sub("", td.group(1)).strip() for td in td_pattern.finditer(tr_content)]
        if len(cells) < 2:
            continue

        # First cell is typically team name; look for percentage values
        team_raw = cells[0]
        mapped = map_team_name(team_raw)
        if mapped is None:
            continue

        # Parse numeric cells as probabilities
        probs: List[Optional[float]] = []
        for cell in cells[1:]:
            cell_clean = cell.replace("%", "").replace(",", "").strip()
            try:
                val = float(cell_clean)
                # If value is 0-1 range, convert to percentage
                if 0 <= val <= 1.0 and "." in cell_clean:
                    val *= 100
                probs.append(validate_probability(val))
            except (ValueError, TypeError):
                probs.append(None)

        playoff_pct = probs[0] if probs else None
        if playoff_pct is None:
            continue

        record = {
            "team_raw": team_raw,
            "team": mapped,
            "playoff_pct": playoff_pct,
            "make_playoffs": playoff_pct >= 50.0,
            "presidents_pct": probs[1] if len(probs) > 1 else None,
            "cup_pct": probs[2] if len(probs) > 2 else None,
        }
        rows.append(record)

    return rows


def fetch_moneypuck_predictions() -> Dict[str, Any]:
    """Fetch and parse MoneyPuck playoff predictions for all teams.

    Returns a dict with:
    - teams: dict mapping NHL abbreviation → prediction record
    - timestamp: float (epoch)
    - success: bool
    - error: optional error message
    """
    try:
        resp = requests.get(MONEYPUCK_URL, timeout=TIMEOUT, headers={
            "User-Agent": "Mozilla/5.0 (NHL Dashboard)"
        })
        resp.raise_for_status()
        html = resp.text
    except Exception as exc:
        logger.warning("MoneyPuck fetch failed: %s", exc)
        return {
            "teams": {},
            "timestamp": time.time(),
            "success": False,
            "error": str(exc),
        }

    try:
        rows = _parse_predictions_html(html)
    except Exception as exc:
        logger.warning("MoneyPuck parse failed: %s", exc)
        return {
            "teams": {},
            "timestamp": time.time(),
            "success": False,
            "error": f"Parse error: {exc}",
        }

    teams: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        abbrev = row["team"]
        if abbrev:
            teams[abbrev] = row

    return {
        "teams": teams,
        "timestamp": time.time(),
        "success": len(teams) > 0,
        "error": None if teams else "No teams parsed from source",
    }


def load_moneypuck_cached() -> Dict[str, Any]:
    """Return cached MoneyPuck predictions, refreshing if stale."""
    if _cache.is_fresh(_CACHE_KEY, MONEYPUCK_CACHE_TTL):
        cached = _cache.get(_CACHE_KEY)
        if cached is not None:
            return cached

    result = fetch_moneypuck_predictions()
    if result["success"]:
        _cache.set(_CACHE_KEY, result)
    else:
        # Keep stale cache if available
        cached = _cache.get(_CACHE_KEY)
        if cached is not None:
            cached["_stale"] = True
            return cached
        _cache.set(_CACHE_KEY, result)

    return result


def get_team_playoff_odds(abbrev: str) -> Optional[float]:
    """Get MoneyPuck playoff probability for a single team (from cache)."""
    data = load_moneypuck_cached()
    teams = data.get("teams", {})
    team_data = teams.get(abbrev)
    if team_data is None:
        return None
    return team_data.get("playoff_pct")


def get_all_playoff_odds() -> Dict[str, float]:
    """Return ``{abbrev: playoff_pct}`` for all teams from MoneyPuck."""
    data = load_moneypuck_cached()
    return {
        abbrev: rec["playoff_pct"]
        for abbrev, rec in data.get("teams", {}).items()
        if rec.get("playoff_pct") is not None
    }


def get_source_status() -> Dict[str, Any]:
    """Return source freshness metadata."""
    data = load_moneypuck_cached()
    ts = data.get("timestamp")
    return {
        "source": "MoneyPuck",
        "success": data.get("success", False),
        "stale": data.get("_stale", False),
        "timestamp": ts,
        "team_count": len(data.get("teams", {})),
        "error": data.get("error"),
    }
