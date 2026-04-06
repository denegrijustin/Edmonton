"""Application-wide settings and constants."""

from __future__ import annotations

# NHL API
NHL_API_BASE = "https://api-web.nhle.com/v1"
NHL_STATS_API_BASE = "https://api.nhle.com/stats/rest/en"
SEASON = "20252026"
TOTAL_GAMES = 82

# Default team
DEFAULT_TEAM = "EDM"
DEFAULT_TEAM_NAME = "Edmonton Oilers"
DEFAULT_CONFERENCE = "Western"

# HTTP
HTTP_TIMEOUT = 30
HTTP_RETRIES = 3
HTTP_RETRY_DELAY = 1.0
CACHE_TTL = 3600  # seconds

# Monte Carlo
MC_SIMULATIONS = 10_000

# Stoplight thresholds
STOPLIGHT = {
    "grade": {"green": 70, "yellow": 50},
    "momentum": {"green": 55, "yellow": 45},
    "playoff_odds": {"green": 70, "yellow": 40},
    "save_pct": {"green": 0.915, "yellow": 0.900},
    "goal_diff": {"green": 5, "yellow": -5},
    "confidence": {"green": 0.7, "yellow": 0.4},
    "api_health": {"green": 0.95, "yellow": 0.80},
}

# Stoplight colors
SL_GREEN = "background-color: #dcfce7; color: #166534"
SL_YELLOW = "background-color: #fef9c3; color: #713f12"
SL_RED = "background-color: #fee2e2; color: #991b1b"

# Player rating weights
FORWARD_WEIGHTS = {
    "goals": 0.18,
    "primary_assists": 0.14,
    "secondary_assists": 0.06,
    "shots": 0.08,
    "shot_attempts": 0.04,
    "takeaways": 0.06,
    "hits": 0.03,
    "blocked_shots": 0.03,
    "penalties_drawn": 0.04,
    "penalties_taken": -0.05,
    "giveaways": -0.04,
    "faceoff_pct": 0.05,
    "toi_share": 0.06,
    "defensive_suppression": 0.08,
    "plus_minus_adj": 0.05,
    "consistency": 0.05,
}

DEFENSEMAN_WEIGHTS = {
    "goals": 0.08,
    "primary_assists": 0.10,
    "secondary_assists": 0.05,
    "shots": 0.05,
    "blocked_shots": 0.12,
    "hits": 0.06,
    "takeaways": 0.06,
    "giveaways": -0.06,
    "defensive_suppression": 0.15,
    "toi_share": 0.08,
    "plus_minus_adj": 0.08,
    "penalties_drawn": 0.03,
    "penalties_taken": -0.05,
    "shot_suppression": 0.10,
    "consistency": 0.04,
}

GOALIE_WEIGHTS = {
    "save_pct": 0.25,
    "goals_against_avg": 0.15,
    "high_danger_save_pct": 0.20,
    "recent_form": 0.15,
    "workload": 0.10,
    "consistency": 0.15,
}

# Momentum weights
MOMENTUM_WEIGHTS = {
    "last5_points_pct": 0.20,
    "last10_points_pct": 0.10,
    "goal_diff_trend": 0.15,
    "shot_diff_trend": 0.10,
    "special_teams_trend": 0.10,
    "goalie_form": 0.10,
    "opponent_quality": 0.08,
    "standings_movement": 0.07,
    "points_pct_trend": 0.10,
}
