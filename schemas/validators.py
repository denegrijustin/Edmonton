"""Data schema validators — ensure API data meets expected shapes."""

from __future__ import annotations

import pandas as pd


def validate_standings(df: pd.DataFrame) -> tuple[bool, list[str]]:
    """Validate standings DataFrame has required columns and values."""
    required = ["teamAbbrev", "points", "wins", "losses", "gamesPlayed", "conference", "division"]
    missing = [c for c in required if c not in df.columns]
    issues: list[str] = []
    if missing:
        issues.append(f"Missing columns: {missing}")
    if not df.empty and not missing:
        if (pd.to_numeric(df["points"], errors="coerce") < 0).any():
            issues.append("Negative points found")
        if (pd.to_numeric(df["gamesPlayed"], errors="coerce") > 82).any():
            issues.append("Games played > 82 found")
        if df["teamAbbrev"].isna().any():
            issues.append("Null team abbreviations found")
    return len(issues) == 0, issues


def validate_schedule(df: pd.DataFrame) -> tuple[bool, list[str]]:
    """Validate schedule DataFrame."""
    required = ["gameId", "gameDate", "awayTeam", "homeTeam", "isCompleted"]
    missing = [c for c in required if c not in df.columns]
    issues: list[str] = []
    if missing:
        issues.append(f"Missing columns: {missing}")
    if not df.empty:
        if df["gameId"].duplicated().any():
            issues.append("Duplicate game IDs found")
    return len(issues) == 0, issues


def validate_team_game(row: dict) -> tuple[bool, list[str]]:
    """Validate a single team game record."""
    issues: list[str] = []
    required_keys = ["gameId", "result", "teamScore", "oppScore"]
    for k in required_keys:
        if k not in row or row[k] is None:
            issues.append(f"Missing key: {k}")
    if row.get("result") not in ("W", "L", "OTL", None):
        issues.append(f"Invalid result: {row.get('result')}")
    return len(issues) == 0, issues


def validate_playoff_odds(odds: float) -> tuple[bool, list[str]]:
    """Validate playoff odds are in range [0, 100]."""
    issues: list[str] = []
    if odds < 0 or odds > 100:
        issues.append(f"Playoff odds {odds} outside [0, 100]")
    return len(issues) == 0, issues


def validate_projected_record(wins: int, losses: int, otl: int) -> tuple[bool, list[str]]:
    """Validate projected record is reasonable."""
    issues: list[str] = []
    total = wins + losses + otl
    if total > 82:
        issues.append(f"Total games {total} > 82")
    if wins < 0 or losses < 0 or otl < 0:
        issues.append("Negative record component")
    return len(issues) == 0, issues
