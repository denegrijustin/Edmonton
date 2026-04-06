"""Application-wide constants and configuration."""

BASE = "https://api-web.nhle.com/v1"
SEASON = "20252026"
TIMEOUT = 30
DEFAULT_TEAM = "EDM"
GAMES_IN_SEASON = 82
LEAGUE_AVG_GPG = 3.1  # 2024-25 NHL season average; update each season

# Monte Carlo simulation parameters
SIM_SEASON_WEIGHT = 0.70  # 70% full-season strength
SIM_LAST10_WEIGHT = 0.30  # 30% last-10 form
SIM_HOME_ADV = 0.15       # home ice advantage in expected goals per game

# Playoff bracket: seed → opponent seed
PLAYOFF_BRACKET_MAP = {1: 8, 2: 7, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}
