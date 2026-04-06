"""NHL team definitions, logos, divisions, and conferences."""

from __future__ import annotations

# Logo base URL from NHL CDN
_LOGO_BASE = "https://assets.nhle.com/logos/nhl/svg"

TEAMS: dict[str, dict] = {
    "ANA": {"name": "Anaheim Ducks", "city": "Anaheim", "division": "Pacific", "conference": "Western"},
    "BOS": {"name": "Boston Bruins", "city": "Boston", "division": "Atlantic", "conference": "Eastern"},
    "BUF": {"name": "Buffalo Sabres", "city": "Buffalo", "division": "Atlantic", "conference": "Eastern"},
    "CAR": {"name": "Carolina Hurricanes", "city": "Carolina", "division": "Metropolitan", "conference": "Eastern"},
    "CBJ": {"name": "Columbus Blue Jackets", "city": "Columbus", "division": "Metropolitan", "conference": "Eastern"},
    "CGY": {"name": "Calgary Flames", "city": "Calgary", "division": "Pacific", "conference": "Western"},
    "CHI": {"name": "Chicago Blackhawks", "city": "Chicago", "division": "Central", "conference": "Western"},
    "COL": {"name": "Colorado Avalanche", "city": "Colorado", "division": "Central", "conference": "Western"},
    "DAL": {"name": "Dallas Stars", "city": "Dallas", "division": "Central", "conference": "Western"},
    "DET": {"name": "Detroit Red Wings", "city": "Detroit", "division": "Atlantic", "conference": "Eastern"},
    "EDM": {"name": "Edmonton Oilers", "city": "Edmonton", "division": "Pacific", "conference": "Western"},
    "FLA": {"name": "Florida Panthers", "city": "Florida", "division": "Atlantic", "conference": "Eastern"},
    "LAK": {"name": "Los Angeles Kings", "city": "Los Angeles", "division": "Pacific", "conference": "Western"},
    "MIN": {"name": "Minnesota Wild", "city": "Minnesota", "division": "Central", "conference": "Western"},
    "MTL": {"name": "Montréal Canadiens", "city": "Montréal", "division": "Atlantic", "conference": "Eastern"},
    "NJD": {"name": "New Jersey Devils", "city": "New Jersey", "division": "Metropolitan", "conference": "Eastern"},
    "NSH": {"name": "Nashville Predators", "city": "Nashville", "division": "Central", "conference": "Western"},
    "NYI": {"name": "New York Islanders", "city": "New York", "division": "Metropolitan", "conference": "Eastern"},
    "NYR": {"name": "New York Rangers", "city": "New York", "division": "Metropolitan", "conference": "Eastern"},
    "OTT": {"name": "Ottawa Senators", "city": "Ottawa", "division": "Atlantic", "conference": "Eastern"},
    "PHI": {"name": "Philadelphia Flyers", "city": "Philadelphia", "division": "Metropolitan", "conference": "Eastern"},
    "PIT": {"name": "Pittsburgh Penguins", "city": "Pittsburgh", "division": "Metropolitan", "conference": "Eastern"},
    "SEA": {"name": "Seattle Kraken", "city": "Seattle", "division": "Pacific", "conference": "Western"},
    "SJS": {"name": "San Jose Sharks", "city": "San Jose", "division": "Pacific", "conference": "Western"},
    "STL": {"name": "St. Louis Blues", "city": "St. Louis", "division": "Central", "conference": "Western"},
    "TBL": {"name": "Tampa Bay Lightning", "city": "Tampa Bay", "division": "Atlantic", "conference": "Eastern"},
    "TOR": {"name": "Toronto Maple Leafs", "city": "Toronto", "division": "Atlantic", "conference": "Eastern"},
    "UTA": {"name": "Utah Hockey Club", "city": "Utah", "division": "Central", "conference": "Western"},
    "VAN": {"name": "Vancouver Canucks", "city": "Vancouver", "division": "Pacific", "conference": "Western"},
    "VGK": {"name": "Vegas Golden Knights", "city": "Vegas", "division": "Pacific", "conference": "Western"},
    "WPG": {"name": "Winnipeg Jets", "city": "Winnipeg", "division": "Central", "conference": "Western"},
    "WSH": {"name": "Washington Capitals", "city": "Washington", "division": "Metropolitan", "conference": "Eastern"},
}


def _logo_url(abbrev: str, style: str = "dark") -> str:
    return f"{_LOGO_BASE}/{abbrev}_{style}.svg"


TEAM_LOGOS: dict[str, str] = {abbrev: _logo_url(abbrev) for abbrev in TEAMS}

DIVISIONS: dict[str, list[str]] = {
    "Atlantic": [k for k, v in TEAMS.items() if v["division"] == "Atlantic"],
    "Metropolitan": [k for k, v in TEAMS.items() if v["division"] == "Metropolitan"],
    "Central": [k for k, v in TEAMS.items() if v["division"] == "Central"],
    "Pacific": [k for k, v in TEAMS.items() if v["division"] == "Pacific"],
}

CONFERENCES: dict[str, list[str]] = {
    "Eastern": [k for k, v in TEAMS.items() if v["conference"] == "Eastern"],
    "Western": [k for k, v in TEAMS.items() if v["conference"] == "Western"],
}
