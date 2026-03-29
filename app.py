from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

BASE = "https://api-web.nhle.com/v1"
TEAM_TRI = "EDM"
TEAM_NAME = "Edmonton Oilers"
SEASON = "20252026"
TIMEOUT = 30

st.set_page_config(
    page_title="Oilers Trends Dashboard",
    page_icon="🏒",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------- Styling ----------
st.markdown(
    """
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
        font-size: 2rem;
        font-weight: 800;
        line-height: 1.1;
    }
    .kpi-sub {
        color: #475569;
        font-size: 0.92rem;
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
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- Utils ----------
@st.cache_data(ttl=3600, show_spinner=False)
def get_json(url: str) -> Dict[str, Any]:
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def safe_get(obj: Any, path: List[Any], default=None):
    cur = obj
    try:
        for p in path:
            cur = cur[p]
        return cur
    except Exception:
        return default


def flatten_dict(obj: Any, parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    items: Dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else str(k)
            items.update(flatten_dict(v, new_key, sep))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            new_key = f"{parent_key}{sep}{i}" if parent_key else str(i)
            items.update(flatten_dict(v, new_key, sep))
    else:
        items[parent_key] = obj
    return items


def first_non_null(d: Dict[str, Any], keys: List[str], default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def parse_mmss(val: Any) -> float:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return np.nan
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val)
    if ":" in s:
        try:
            mm, ss = s.split(":")
            return int(mm) + int(ss) / 60
        except Exception:
            return np.nan
    try:
        return float(s)
    except Exception:
        return np.nan


def format_record(team_games: pd.DataFrame) -> str:
    wins = int((team_games["result"] == "W").sum())
    losses = int((team_games["result"] == "L").sum())
    otl = int((team_games["result"] == "OTL").sum()) if "OTL" in team_games["result"].values else 0
    return f"{wins}-{losses}" if otl == 0 else f"{wins}-{losses}-{otl}"


def points_from_result(row: pd.Series) -> int:
    if row["result"] == "W":
        return 2
    if row["result"] == "OTL":
        return 1
    return 0


def zscore(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    std = s.std(ddof=0)
    if std == 0 or np.isnan(std):
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - s.mean()) / std


def classify_zone(x: float, y: float) -> str:
    if pd.isna(x) or pd.isna(y):
        return "Unknown"
    ax = abs(x)
    ay = abs(y)
    if ax <= 20 and ay <= 10:
        return "Net Front"
    if ax <= 35 and ay <= 20:
        return "Slot"
    if ax <= 69 and ay <= 22:
        return "Circle / Inner Lane"
    if ax <= 89 and ay <= 42:
        return "Perimeter"
    return "Outer / Point"


def opponent_from_row(row: pd.Series) -> str:
    return row["awayTeam"] if row["homeTeam"] == TEAM_TRI else row["homeTeam"]


def draw_rink(fig: go.Figure):
    # Simplified offensive/defensive rink overlay
    fig.update_xaxes(range=[-100, 100], showgrid=False, zeroline=False, visible=False)
    fig.update_yaxes(range=[-42.5, 42.5], showgrid=False, zeroline=False, visible=False, scaleanchor="x", scaleratio=1)
    shapes = [
        dict(type="rect", x0=-89, x1=89, y0=-42.5, y1=42.5, line=dict(color="#cbd5e1", width=2)),
        dict(type="line", x0=0, x1=0, y0=-42.5, y1=42.5, line=dict(color="#e2e8f0", width=2)),
        dict(type="line", x0=-25, x1=-25, y0=-42.5, y1=42.5, line=dict(color="#e2e8f0", width=1)),
        dict(type="line", x0=25, x1=25, y0=-42.5, y1=42.5, line=dict(color="#e2e8f0", width=1)),
        dict(type="circle", x0=-22, x1=22, y0=-22, y1=22, line=dict(color="#e2e8f0", width=1)),
    ]
    fig.update_layout(shapes=shapes, plot_bgcolor="#ffffff", paper_bgcolor="#ffffff", margin=dict(l=0, r=0, t=40, b=0))


# ---------- Data Pull ----------
@st.cache_data(ttl=3600, show_spinner=False)
def get_schedule(team: str = TEAM_TRI, season: str = SEASON) -> pd.DataFrame:
    data = get_json(f"{BASE}/club-schedule-season/{team}/{season}")
    games: List[Dict[str, Any]] = []
    containers = []
    if isinstance(data, dict):
        if isinstance(data.get("games"), list):
            containers.append(data["games"])
        if isinstance(data.get("gameWeek"), list):
            for wk in data["gameWeek"]:
                if isinstance(wk, dict) and isinstance(wk.get("games"), list):
                    containers.append(wk["games"])
    for game_list in containers:
        for g in game_list:
            flat = flatten_dict(g)
            game_id = first_non_null(flat, ["id", "gameId"])
            game_date = first_non_null(flat, ["gameDate", "startTimeUTC", "startTime"])
            away = first_non_null(flat, ["awayTeam.abbrev"])
            home = first_non_null(flat, ["homeTeam.abbrev"])
            away_score = first_non_null(flat, ["awayTeam.score", "awayScore"])
            home_score = first_non_null(flat, ["homeTeam.score", "homeScore"])
            game_state = str(first_non_null(flat, ["gameState", "gameScheduleState"], "")).upper()
            game_type = first_non_null(flat, ["gameType"])
            if game_id:
                games.append(
                    {
                        "gameId": int(game_id),
                        "gameDate": pd.to_datetime(game_date, errors="coerce"),
                        "awayTeam": away,
                        "homeTeam": home,
                        "awayScore": away_score,
                        "homeScore": home_score,
                        "gameState": game_state,
                        "gameType": game_type,
                        "isCompleted": game_state in {"OFF", "FINAL", "OVER", "DONE"} or (away_score is not None and home_score is not None),
                    }
                )
    df = pd.DataFrame(games).drop_duplicates(subset=["gameId"])
    if df.empty:
        return df
    df = df.sort_values(["gameDate", "gameId"]).reset_index(drop=True)
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def get_standings() -> pd.DataFrame:
    data = get_json(f"{BASE}/standings/now")
    raw = data.get("standings", data if isinstance(data, list) else [])
    rows = []
    for team in raw:
        flat = flatten_dict(team)
        rows.append(
            {
                "teamName": first_non_null(flat, ["teamName.default", "teamCommonName.default", "teamAbbrev.default", "teamName"]),
                "teamAbbrev": first_non_null(flat, ["teamAbbrev.default", "teamAbbrev", "abbrev"]),
                "conference": first_non_null(flat, ["conferenceName", "conferenceAbbrev"]),
                "division": first_non_null(flat, ["divisionName", "divisionAbbrev"]),
                "gamesPlayed": first_non_null(flat, ["gamesPlayed"]),
                "points": first_non_null(flat, ["points"]),
                "goalDifferential": first_non_null(flat, ["goalDifferential"]),
                "wins": first_non_null(flat, ["wins"]),
                "losses": first_non_null(flat, ["losses"]),
                "otLosses": first_non_null(flat, ["otLosses"]),
                "pointPctg": first_non_null(flat, ["pointPctg", "pointsPctg"]),
                "conferenceSequence": first_non_null(flat, ["conferenceSequence"]),
                "wildcardSequence": first_non_null(flat, ["wildcardSequence"]),
            }
        )
    return pd.DataFrame(rows)


@st.cache_data(ttl=3600, show_spinner=False)
def get_roster(team: str = TEAM_TRI, season: str = SEASON) -> pd.DataFrame:
    data = get_json(f"{BASE}/roster/{team}/{season}")
    rows = []
    mapping = {
        "forwards": "F",
        "defensemen": "D",
        "goalies": "G",
        "skaters": "S",
    }
    for sec, pos in mapping.items():
        for p in data.get(sec, []) or []:
            rows.append(
                {
                    "playerId": p.get("id") or p.get("playerId"),
                    "playerName": " ".join(
                        x for x in [safe_get(p, ["firstName", "default"]), safe_get(p, ["lastName", "default"])] if x
                    ).strip(),
                    "position": pos,
                    "sweaterNumber": p.get("sweaterNumber"),
                }
            )
    return pd.DataFrame(rows).drop_duplicates(subset=["playerId", "playerName"])


@st.cache_data(ttl=3600, show_spinner=False)
def get_boxscore(game_id: int) -> Dict[str, Any]:
    return get_json(f"{BASE}/gamecenter/{game_id}/boxscore")


@st.cache_data(ttl=3600, show_spinner=False)
def get_play_by_play(game_id: int) -> Dict[str, Any]:
    return get_json(f"{BASE}/gamecenter/{game_id}/play-by-play")


def extract_team_game(game_row: pd.Series, box: Dict[str, Any]) -> Dict[str, Any]:
    flat = flatten_dict(box)
    away_score = first_non_null(flat, ["awayTeam.score"], game_row["awayScore"])
    home_score = first_non_null(flat, ["homeTeam.score"], game_row["homeScore"])
    away_shots = first_non_null(flat, ["awayTeam.sog", "awayTeam.shotsOnGoal", "awayTeam.teamStats.shotsOnGoal"])
    home_shots = first_non_null(flat, ["homeTeam.sog", "homeTeam.shotsOnGoal", "homeTeam.teamStats.shotsOnGoal"])
    away_faceoff = first_non_null(flat, ["awayTeam.faceoffWinningPctg", "awayTeam.teamStats.faceoffWinningPctg"])
    home_faceoff = first_non_null(flat, ["homeTeam.faceoffWinningPctg", "homeTeam.teamStats.faceoffWinningPctg"])
    away_pp = first_non_null(flat, ["awayTeam.powerPlayConversion", "awayTeam.teamStats.powerPlayConversion"])
    home_pp = first_non_null(flat, ["homeTeam.powerPlayConversion", "homeTeam.teamStats.powerPlayConversion"])

    is_home = game_row["homeTeam"] == TEAM_TRI
    team_score = home_score if is_home else away_score
    opp_score = away_score if is_home else home_score
    result = "W" if team_score > opp_score else "L"

    return {
        "gameId": int(game_row["gameId"]),
        "gameDate": game_row["gameDate"],
        "gameType": game_row["gameType"],
        "venue": "Home" if is_home else "Away",
        "opponent": opponent_from_row(game_row),
        "teamScore": team_score,
        "oppScore": opp_score,
        "result": result,
        "goalDiff": (team_score or 0) - (opp_score or 0),
        "teamShots": home_shots if is_home else away_shots,
        "oppShots": away_shots if is_home else home_shots,
        "shotDiff": (home_shots - away_shots) if (is_home and home_shots is not None and away_shots is not None) else ((away_shots - home_shots) if (not is_home and away_shots is not None and home_shots is not None) else np.nan),
        "teamFaceoffPct": home_faceoff if is_home else away_faceoff,
        "teamPowerPlay": home_pp if is_home else away_pp,
    }


def get_player_arrays(box: Dict[str, Any]) -> List[Tuple[str, List[Dict[str, Any]]]]:
    out: List[Tuple[str, List[Dict[str, Any]]]] = []
    pbg = box.get("playerByGameStats", {}) if isinstance(box, dict) else {}
    for side in ["awayTeam", "homeTeam"]:
        for group in ["forwards", "defense", "goalies"]:
            arr = safe_get(pbg, [side, group], [])
            if isinstance(arr, list) and arr:
                out.append((side, arr))
    return out


def extract_player_games(game_row: pd.Series, box: Dict[str, Any], roster_df: pd.DataFrame) -> pd.DataFrame:
    roster_ids = set(roster_df["playerId"].dropna().astype(int).tolist()) if not roster_df.empty else set()
    roster_names = set(roster_df["playerName"].dropna().tolist()) if not roster_df.empty else set()
    rows = []
    for side, arr in get_player_arrays(box):
        team_abbrev = game_row["awayTeam"] if side == "awayTeam" else game_row["homeTeam"]
        for p in arr:
            flat = flatten_dict(p)
            pid = first_non_null(flat, ["playerId", "id"])
            fn = first_non_null(flat, ["firstName.default", "firstName"])
            ln = first_non_null(flat, ["lastName.default", "lastName"])
            name = first_non_null(flat, ["name.default", "fullName"], " ".join(x for x in [fn, ln] if x).strip())
            if team_abbrev != TEAM_TRI and pid not in roster_ids and name not in roster_names:
                continue
            rows.append(
                {
                    "gameId": int(game_row["gameId"]),
                    "gameDate": game_row["gameDate"],
                    "playerId": pid,
                    "playerName": name,
                    "position": first_non_null(flat, ["position", "positionCode"]),
                    "goals": first_non_null(flat, ["goals", "g"], 0),
                    "assists": first_non_null(flat, ["assists", "a"], 0),
                    "points": first_non_null(flat, ["points", "p"], 0),
                    "plusMinus": first_non_null(flat, ["plusMinus"], 0),
                    "shots": first_non_null(flat, ["shots", "sog"], 0),
                    "hits": first_non_null(flat, ["hits"], 0),
                    "blockedShots": first_non_null(flat, ["blockedShots", "blocks"], 0),
                    "giveaways": first_non_null(flat, ["giveaways"], 0),
                    "takeaways": first_non_null(flat, ["takeaways"], 0),
                    "faceoffWins": first_non_null(flat, ["faceoffWins", "faceoffsWon"], 0),
                    "faceoffTaken": first_non_null(flat, ["faceoffTaken", "faceoffs"], 0),
                    "toi": first_non_null(flat, ["toi", "timeOnIce"]),
                    "ppToi": first_non_null(flat, ["powerPlayToi", "ppToi"]),
                    "shToi": first_non_null(flat, ["shorthandedToi", "shToi"]),
                    "evToi": first_non_null(flat, ["evenStrengthToi", "evToi"]),
                    "saves": first_non_null(flat, ["saves"]),
                    "goalsAgainst": first_non_null(flat, ["goalsAgainst"]),
                    "shotsAgainst": first_non_null(flat, ["shotsAgainst"]),
                }
            )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for col in ["goals", "assists", "points", "plusMinus", "shots", "hits", "blockedShots", "giveaways", "takeaways", "faceoffWins", "faceoffTaken", "saves", "goalsAgainst", "shotsAgainst"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    for col in ["toi", "ppToi", "shToi", "evToi"]:
        df[f"{col}_min"] = df[col].apply(parse_mmss)
    return df


def extract_goal_events(schedule_df: pd.DataFrame, roster_df: pd.DataFrame) -> pd.DataFrame:
    roster_ids = set(roster_df["playerId"].dropna().astype(int).tolist()) if not roster_df.empty else set()
    events_out: List[Dict[str, Any]] = []
    completed = schedule_df[schedule_df["isCompleted"]]
    for _, g in completed.iterrows():
        try:
            pbp = get_play_by_play(int(g["gameId"]))
        except Exception:
            continue
        plays = pbp.get("plays", pbp.get("gameEvents", [])) if isinstance(pbp, dict) else []
        if not isinstance(plays, list):
            continue
        for ev in plays:
            flat = flatten_dict(ev)
            event_type = str(first_non_null(flat, ["typeDescKey", "eventType", "typeCode"], "")).lower()
            if "goal" not in event_type:
                continue
            x = first_non_null(flat, ["details.xCoord", "xCoord", "x"])
            y = first_non_null(flat, ["details.yCoord", "yCoord", "y"])
            scoring_team = first_non_null(flat, ["details.eventOwnerTeamAbbrev", "teamAbbrev"])
            strength = first_non_null(flat, ["details.strength", "situationCode", "details.situationCode"])
            period = first_non_null(flat, ["periodDescriptor.number", "period"])
            scorer_id = first_non_null(flat, ["details.scoringPlayerId", "details.playerId"])
            on_ice_for = first_non_null(flat, ["details.homeTeamDefendingSide", "details.zoneCode"])

            home_team = g["homeTeam"]
            away_team = g["awayTeam"]
            is_oilers_goal = scoring_team == TEAM_TRI

            # Capture any player ids listed on event payload as a fallback approximation for on-ice linking
            event_player_ids = set()
            for key, val in flat.items():
                if isinstance(val, int) and ("playerId" in key or key.endswith(".id")):
                    event_player_ids.add(val)
            oilers_on_event = bool(roster_ids.intersection(event_player_ids))
            nx = pd.to_numeric(x, errors="coerce")
            ny = pd.to_numeric(y, errors="coerce")

            events_out.append(
                {
                    "gameId": int(g["gameId"]),
                    "gameDate": g["gameDate"],
                    "opponent": opponent_from_row(g),
                    "venue": "Home" if g["homeTeam"] == TEAM_TRI else "Away",
                    "period": period,
                    "x": nx,
                    "y": ny,
                    "teamFor": scoring_team,
                    "isOilersGoal": is_oilers_goal,
                    "strength": str(strength),
                    "scorerId": scorer_id,
                    "zone": classify_zone(nx, ny),
                    "eventHasOilersPlayerId": oilers_on_event,
                    "homeTeam": home_team,
                    "awayTeam": away_team,
                    "rawSideHint": on_ice_for,
                }
            )
    return pd.DataFrame(events_out)


@st.cache_data(ttl=3600, show_spinner=True)
def build_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    schedule = get_schedule()
    roster = get_roster()
    completed = schedule[schedule["isCompleted"]]
    team_rows = []
    player_parts = []
    for _, g in completed.iterrows():
        try:
            box = get_boxscore(int(g["gameId"]))
            team_rows.append(extract_team_game(g, box))
            pg = extract_player_games(g, box, roster)
            if not pg.empty:
                player_parts.append(pg)
        except Exception:
            continue
    team_games = pd.DataFrame(team_rows).sort_values(["gameDate", "gameId"]).reset_index(drop=True)
    player_games = pd.concat(player_parts, ignore_index=True) if player_parts else pd.DataFrame()
    if not team_games.empty:
        team_games["gameNumber"] = np.arange(1, len(team_games) + 1)
        team_games["pointsEarned"] = team_games.apply(points_from_result, axis=1)
        team_games["cumulativePoints"] = team_games["pointsEarned"].cumsum()
        team_games["rolling3GoalDiff"] = team_games["goalDiff"].rolling(3, min_periods=1).mean()
        team_games["rolling5GoalDiff"] = team_games["goalDiff"].rolling(5, min_periods=1).mean()
        team_games["rolling3ShotDiff"] = team_games["shotDiff"].rolling(3, min_periods=1).mean()
        team_games["rolling3GoalsFor"] = team_games["teamScore"].rolling(3, min_periods=1).mean()
        team_games["rolling3GoalsAgainst"] = team_games["oppScore"].rolling(3, min_periods=1).mean()
        team_games["clutchIndex"] = np.where((team_games["goalDiff"].abs() == 1) & (team_games["result"] == "W"), 1, np.where((team_games["goalDiff"].abs() == 1) & (team_games["result"] == "L"), -1, 0))
        team_games["momentumScore"] = (
            0.35 * zscore(team_games["rolling3GoalDiff"]).fillna(0)
            + 0.25 * zscore(team_games["rolling3ShotDiff"]).fillna(0)
            + 0.20 * zscore(team_games["rolling3GoalsFor"] - team_games["rolling3GoalsAgainst"]).fillna(0)
            + 0.20 * zscore(team_games["clutchIndex"].rolling(5, min_periods=1).mean()).fillna(0)
        ) * 10 + 50
    if not player_games.empty:
        player_games = player_games.sort_values(["playerName", "gameDate", "gameId"]).reset_index(drop=True)
        player_games["gameNumberByPlayer"] = player_games.groupby("playerName").cumcount() + 1
        player_games["rolling3Points"] = player_games.groupby("playerName")["points"].transform(lambda s: s.rolling(3, min_periods=1).mean())
        player_games["rolling5Points"] = player_games.groupby("playerName")["points"].transform(lambda s: s.rolling(5, min_periods=1).mean())
        player_games["rolling5Toi"] = player_games.groupby("playerName")["toi_min"].transform(lambda s: s.rolling(5, min_periods=1).mean())
        player_games["shootingPct"] = np.where(player_games["shots"] > 0, player_games["goals"] / player_games["shots"], 0)
        player_games["gamesPlayed"] = player_games.groupby("playerName")["gameId"].transform("count")
        player_games["seasonAvgPoints"] = player_games.groupby("playerName")["points"].transform("mean")
        player_games["recent5AvgPoints"] = player_games.groupby("playerName")["points"].transform(lambda s: s.rolling(5, min_periods=1).mean())
        grade_raw = (
            0.9 * player_games["goals"]
            + 0.7 * player_games["assists"]
            + 0.08 * player_games["shots"]
            + 0.035 * player_games["toi_min"].fillna(0)
            + 0.06 * player_games["takeaways"]
            + 0.04 * player_games["hits"]
            + 0.04 * player_games["blockedShots"]
            - 0.05 * player_games["giveaways"]
            + 0.08 * player_games["plusMinus"]
        )
        player_games["gameGrade"] = (50 + 12 * zscore(grade_raw)).clip(20, 99)
        player_games["rollingGrade"] = player_games.groupby("playerName")["gameGrade"].transform(lambda s: s.rolling(5, min_periods=1).mean())
        player_games["consistencyScore"] = player_games.groupby("playerName")["gameGrade"].transform(lambda s: 100 - s.rolling(10, min_periods=3).std().fillna(0) * 4).clip(40, 100)
        player_games["trendFlag"] = np.select(
            [player_games["recent5AvgPoints"] >= 1.2 * player_games["seasonAvgPoints"], player_games["recent5AvgPoints"] <= 0.8 * player_games["seasonAvgPoints"]],
            ["Heating Up", "Cooling Off"],
            default="Stable",
        )
    goal_events = extract_goal_events(schedule, roster)
    standings = get_standings()
    return schedule, team_games, player_games, goal_events, standings


# ---------- Charts ----------
def plot_team_trend(team_games: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=team_games["gameDate"], y=team_games["rolling3GoalDiff"], mode="lines+markers", name="Rolling 3 Goal Diff"))
    fig.add_trace(go.Scatter(x=team_games["gameDate"], y=team_games["rolling3ShotDiff"], mode="lines+markers", name="Rolling 3 Shot Diff", yaxis="y2"))
    fig.update_layout(
        title="Recent Form Trend",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(title="Goal Diff"),
        yaxis2=dict(title="Shot Diff", overlaying="y", side="right"),
        height=420,
        margin=dict(l=20, r=20, t=50, b=10),
    )
    return fig


def plot_momentum(team_games: pd.DataFrame) -> go.Figure:
    fig = px.line(team_games, x="gameDate", y="momentumScore", markers=True, title="Momentum Score")
    fig.update_layout(template="plotly_white", height=350, margin=dict(l=20, r=20, t=50, b=10))
    fig.add_hline(y=50, line_dash="dash", line_color="#94a3b8")
    return fig


def plot_player_progress(player_games: pd.DataFrame, player_name: str) -> go.Figure:
    df = player_games[player_games["playerName"] == player_name].copy()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["gameDate"], y=df["rollingGrade"], mode="lines+markers", name="Rolling Grade"))
    fig.add_trace(go.Bar(x=df["gameDate"], y=df["points"], name="Points", opacity=.35))
    fig.update_layout(template="plotly_white", height=420, title=f"{player_name} Progression", margin=dict(l=20, r=20, t=50, b=10))
    return fig


def plot_rink_heatmap(df: pd.DataFrame, title: str) -> go.Figure:
    fig = px.density_heatmap(
        df,
        x="x",
        y="y",
        nbinsx=30,
        nbinsy=26,
        color_continuous_scale="YlOrRd",
        title=title,
    )
    draw_rink(fig)
    fig.update_layout(height=500, coloraxis_colorbar_title="Events")
    return fig


# ---------- Outlook ----------
def compute_outlook(team_games: pd.DataFrame, schedule: pd.DataFrame, standings: pd.DataFrame) -> Dict[str, Any]:
    oilers = standings[standings["teamAbbrev"] == TEAM_TRI]
    if oilers.empty:
        current_points = int(team_games["pointsEarned"].sum()) if not team_games.empty else 0
        games_played = len(team_games)
        goal_diff = int(team_games["goalDiff"].sum()) if not team_games.empty else 0
        conference_rank = None
    else:
        current_points = int(pd.to_numeric(oilers.iloc[0]["points"], errors="coerce"))
        games_played = int(pd.to_numeric(oilers.iloc[0]["gamesPlayed"], errors="coerce"))
        goal_diff = int(pd.to_numeric(oilers.iloc[0]["goalDifferential"], errors="coerce"))
        conference_rank = pd.to_numeric(oilers.iloc[0].get("conferenceSequence"), errors="coerce")

    remaining = max(82 - games_played, 0)
    pts_pct = current_points / max(games_played * 2, 1)
    projected_points = current_points + remaining * 2 * pts_pct

    west = standings[standings["conference"].astype(str).str.contains("West", case=False, na=False)].copy()
    if not west.empty:
        west["points"] = pd.to_numeric(west["points"], errors="coerce")
        west = west.sort_values("points", ascending=False)
        cutoff = west.iloc[min(7, len(west)-1)]["points"] if len(west) >= 8 else west["points"].min()
        gap = current_points - cutoff
    else:
        cutoff = np.nan
        gap = np.nan

    # Proxy odds, not official model
    pace_component = max(min((projected_points - 90) / 18, 1), -1)
    diff_component = max(min(goal_diff / 40, 1), -1)
    gap_component = 0 if pd.isna(gap) else max(min(gap / 10, 1), -1)
    odds = round(float(max(min(50 + 22 * pace_component + 14 * diff_component + 14 * gap_component, 99), 1)), 1)

    return {
        "current_points": current_points,
        "games_played": games_played,
        "remaining_games": remaining,
        "projected_points": round(projected_points, 1),
        "conference_rank": None if pd.isna(conference_rank) else int(conference_rank),
        "west_cutoff_points": None if pd.isna(cutoff) else int(cutoff),
        "gap_to_cutoff": None if pd.isna(gap) else int(gap),
        "playoff_odds_proxy": odds,
    }


# ---------- App ----------
try:
    schedule, team_games, player_games, goal_events, standings = build_data()
except Exception as e:
    st.error(f"Data load failed: {e}")
    st.stop()

remaining_games_df = schedule[~schedule["isCompleted"]].sort_values("gameDate")
outlook = compute_outlook(team_games, schedule, standings)

st.title("Edmonton Oilers Trends Dashboard")
st.caption("Lighter UI, streamlined navigation, team trends, player grades, heat maps, and season outlook.")

# KPI row
k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Record</div><div class='kpi-value'>{format_record(team_games)}</div><div class='kpi-sub'>{len(team_games)} games completed</div></div>", unsafe_allow_html=True)
with k2:
    gd = int(team_games["goalDiff"].sum()) if not team_games.empty else 0
    st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Goal Differential</div><div class='kpi-value'>{gd:+d}</div><div class='kpi-sub'>Season to date</div></div>", unsafe_allow_html=True)
with k3:
    ms = team_games["momentumScore"].iloc[-1] if not team_games.empty else np.nan
    st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Momentum</div><div class='kpi-value'>{ms:.1f}</div><div class='kpi-sub'>Latest composite trend</div></div>", unsafe_allow_html=True)
with k4:
    st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Projected Points</div><div class='kpi-value'>{outlook['projected_points']}</div><div class='kpi-sub'>Current pace</div></div>", unsafe_allow_html=True)
with k5:
    st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Playoff Odds Proxy</div><div class='kpi-value'>{outlook['playoff_odds_proxy']}%</div><div class='kpi-sub'>Pace + standings + goal diff</div></div>", unsafe_allow_html=True)

# Filters across top, no sidebar
with st.container():
    c1, c2, c3, c4 = st.columns([1.3, 1.2, 1.2, 1.4])
    with c1:
        window_choice = st.selectbox("Trend Window", [3, 5, 10], index=0)
    with c2:
        venue_filter = st.selectbox("Venue", ["All", "Home", "Away"], index=0)
    with c3:
        strength_filter = st.selectbox("Heat Map Strength", ["All", "5v5", "PP", "SH"], index=0)
    with c4:
        player_options = sorted(player_games["playerName"].dropna().unique().tolist()) if not player_games.empty else []
        default_player = "Connor McDavid" if "Connor McDavid" in player_options else (player_options[0] if player_options else None)
        player_selected = st.selectbox("Player Focus", player_options, index=player_options.index(default_player) if default_player in player_options else 0)

team_games_view = team_games[team_games["venue"] == venue_filter] if venue_filter != "All" else team_games

heat_events = goal_events
if venue_filter != "All" and not heat_events.empty:
    heat_events = heat_events[heat_events["venue"] == venue_filter]
if strength_filter != "All" and not heat_events.empty:
    heat_events = heat_events[heat_events["strength"].astype(str).str.contains(strength_filter, case=False, na=False)]

# Tabs
team_tab, player_tab, heat_tab, outlook_tab, games_tab = st.tabs([
    "Team Trends",
    "Player Grades",
    "Heat Maps",
    "Season Outlook",
    "Game Log",
])

with team_tab:
    lcol, rcol = st.columns([1.35, 1])
    with lcol:
        st.plotly_chart(plot_team_trend(team_games_view if not team_games_view.empty else team_games), use_container_width=True)
    with rcol:
        st.plotly_chart(plot_momentum(team_games_view if not team_games_view.empty else team_games), use_container_width=True)

    st.markdown("### Opponent damage profile")
    if not team_games.empty:
        opp_profile = (
            team_games.groupby("opponent", as_index=False)
            .agg(
                games=("gameId", "count"),
                goalsAgainst=("oppScore", "sum"),
                goalsFor=("teamScore", "sum"),
                avgGoalDiff=("goalDiff", "mean"),
                avgShotsAgainst=("oppShots", "mean"),
            )
        )
        opp_profile["damageIndex"] = (
            0.45 * zscore(opp_profile["goalsAgainst"]).fillna(0)
            + 0.35 * zscore(opp_profile["avgShotsAgainst"]).fillna(0)
            - 0.20 * zscore(opp_profile["avgGoalDiff"]).fillna(0)
        ) * 10 + 50
        st.dataframe(
            opp_profile.sort_values("damageIndex", ascending=False).style.format({"avgGoalDiff": "{:.2f}", "avgShotsAgainst": "{:.1f}", "damageIndex": "{:.1f}"}),
            use_container_width=True,
            hide_index=True,
        )

with player_tab:
    if player_games.empty:
        st.info("No player-game data available.")
    else:
        latest = player_games.sort_values(["playerName", "gameDate", "gameId"]).groupby("playerName", as_index=False).tail(1)
        latest = latest[["playerName", "position", "rollingGrade", "consistencyScore", "recent5AvgPoints", "seasonAvgPoints", "trendFlag", "toi_min"]].rename(columns={"rollingGrade": "Current Grade", "consistencyScore": "Consistency", "recent5AvgPoints": "Recent 5 Avg Pts", "seasonAvgPoints": "Season Avg Pts", "toi_min": "Last TOI"})
        top, bottom = st.columns([1.2, 1])
        with top:
            st.plotly_chart(plot_player_progress(player_games, player_selected), use_container_width=True)
        with bottom:
            selected_latest = latest[latest["playerName"] == player_selected]
            st.markdown("### Player snapshot")
            st.dataframe(selected_latest.style.format({"Current Grade": "{:.1f}", "Consistency": "{:.1f}", "Recent 5 Avg Pts": "{:.2f}", "Season Avg Pts": "{:.2f}", "Last TOI": "{:.1f}"}), use_container_width=True, hide_index=True)
            st.markdown("### Top current grades")
            st.dataframe(latest.sort_values("Current Grade", ascending=False).head(15).style.format({"Current Grade": "{:.1f}", "Consistency": "{:.1f}", "Recent 5 Avg Pts": "{:.2f}", "Season Avg Pts": "{:.2f}", "Last TOI": "{:.1f}"}), use_container_width=True, hide_index=True)

with heat_tab:
    st.markdown("### Goal location heat maps")
    st.caption("Team maps use goal event coordinates. On-ice player maps are best-effort approximations based on event payload player IDs when available.")

    left, right = st.columns(2)
    if heat_events.empty:
        st.info("No goal coordinate data available from play-by-play for the selected filters.")
    else:
        gf = heat_events[heat_events["isOilersGoal"]]
        ga = heat_events[~heat_events["isOilersGoal"]]
        with left:
            st.plotly_chart(plot_rink_heatmap(gf, "Oilers Goals Scored Locations"), use_container_width=True)
        with right:
            st.plotly_chart(plot_rink_heatmap(ga, "Oilers Goals Against Locations"), use_container_width=True)

        st.markdown("### On-ice trend views")
        player_id_lookup = player_games[["playerName", "playerId"]].dropna().drop_duplicates() if not player_games.empty else pd.DataFrame(columns=["playerName", "playerId"])
        selected_pid = None
        if not player_id_lookup.empty and player_selected in player_id_lookup["playerName"].values:
            selected_pid = int(player_id_lookup[player_id_lookup["playerName"] == player_selected]["playerId"].iloc[0])

        if selected_pid is not None:
            player_heat = heat_events[heat_events["scorerId"].eq(selected_pid) | heat_events["eventHasOilersPlayerId"]]
            ph_left, ph_right = st.columns(2)
            with ph_left:
                ph_gf = player_heat[player_heat["isOilersGoal"]]
                if not ph_gf.empty:
                    st.plotly_chart(plot_rink_heatmap(ph_gf, f"{player_selected} On-Ice / Event-Linked Goals For"), use_container_width=True)
                else:
                    st.info("No linked goals-for events found for this player under current filters.")
            with ph_right:
                ph_ga = player_heat[~player_heat["isOilersGoal"]]
                if not ph_ga.empty:
                    st.plotly_chart(plot_rink_heatmap(ph_ga, f"{player_selected} On-Ice / Event-Linked Goals Against"), use_container_width=True)
                else:
                    st.info("No linked goals-against events found for this player under current filters.")

        zone_summary = heat_events.groupby(["isOilersGoal", "zone"], as_index=False).size()
        zone_pivot = zone_summary.pivot(index="zone", columns="isOilersGoal", values="size").fillna(0).reset_index()
        zone_pivot.columns = ["zone", "Goals Against", "Goals For"] if len(zone_pivot.columns) == 3 else zone_pivot.columns
        st.markdown("### Zone summary")
        st.dataframe(zone_pivot, use_container_width=True, hide_index=True)

with outlook_tab:
    a, b, c, d = st.columns(4)
    a.metric("Current points", outlook["current_points"])
    b.metric("Games remaining", outlook["remaining_games"])
    c.metric("Projected points", outlook["projected_points"])
    d.metric("Playoff odds proxy", f"{outlook['playoff_odds_proxy']}%")

    left, right = st.columns([1.2, 1])
    with left:
        if not team_games.empty:
            pts_path = team_games[["gameDate", "cumulativePoints"]]
            pts_path["paceLine82"] = np.linspace(0, outlook["projected_points"], len(pts_path))
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=pts_path["gameDate"], y=pts_path["cumulativePoints"], mode="lines+markers", name="Actual"))
            fig.add_trace(go.Scatter(x=pts_path["gameDate"], y=pts_path["paceLine82"], mode="lines", name="Projected pace", line=dict(dash="dash")))
            fig.update_layout(template="plotly_white", height=380, title="Points Path", margin=dict(l=20, r=20, t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)
    with right:
        st.markdown("### Stretch-run context")
        st.write(
            f"Conference rank: {outlook['conference_rank'] if outlook['conference_rank'] is not None else 'N/A'}"
        )
        st.write(
            f"West cutoff points: {outlook['west_cutoff_points'] if outlook['west_cutoff_points'] is not None else 'N/A'}"
        )
        st.write(
            f"Gap to cutoff: {outlook['gap_to_cutoff'] if outlook['gap_to_cutoff'] is not None else 'N/A'}"
        )
        if not remaining_games_df.empty:
            rem = remaining_games_df.assign(opponent=np.where(remaining_games_df["homeTeam"] == TEAM_TRI, remaining_games_df["awayTeam"], remaining_games_df["homeTeam"]))
            st.markdown("### Remaining schedule")
            st.dataframe(rem[["gameDate", "homeTeam", "awayTeam", "opponent"]].rename(columns={"gameDate": "Date"}), use_container_width=True, hide_index=True)

with games_tab:
    st.markdown("### Team game log")
    if not team_games.empty:
        st.dataframe(team_games.style.format({"teamFaceoffPct": "{:.1f}", "rolling3GoalDiff": "{:.2f}", "rolling3ShotDiff": "{:.2f}", "momentumScore": "{:.1f}"}), use_container_width=True, hide_index=True)
    st.markdown("### Player game log")
    if not player_games.empty:
        pview = player_games[player_games["playerName"] == player_selected]
        st.dataframe(pview[["gameDate", "goals", "assists", "points", "shots", "toi_min", "gameGrade", "rollingGrade", "trendFlag"]].style.format({"toi_min": "{:.1f}", "gameGrade": "{:.1f}", "rollingGrade": "{:.1f}"}), use_container_width=True, hide_index=True)
