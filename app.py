from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ── Constants ──────────────────────────────────────────────────────────────────
BASE = "https://api-web.nhle.com/v1"
SEASON = "20252026"
TIMEOUT = 30
DEFAULT_TEAM = "EDM"
GAMES_IN_SEASON = 82
LEAGUE_AVG_GPG = 3.1


def logo_url(abbrev: str) -> str:
    return f"https://assets.nhle.com/logos/nhl/svg/{abbrev}_light.svg"


# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NHL Intelligence Dashboard",
    page_icon="🏒",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
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
    """,
    unsafe_allow_html=True,
)


# ── Utility functions ──────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_json(url: str) -> Dict[str, Any]:
    try:
        r = requests.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as exc:
        st.warning(f"API request failed ({url}): {exc}", icon="⚠️")
        return {}
    except Exception as exc:
        st.warning(f"Unexpected error fetching {url}: {exc}", icon="⚠️")
        return {}


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


def zscore(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    std = s.std(ddof=0)
    if std == 0 or np.isnan(std):
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - s.mean()) / std


def points_from_result(row: pd.Series) -> int:
    if row["result"] == "W":
        return 2
    if row["result"] == "OTL":
        return 1
    return 0


def fmt_record(w: int, l: int, otl: int) -> str:
    return f"{w}-{l}" if otl == 0 else f"{w}-{l}-{otl}"


# ── UI helper functions ────────────────────────────────────────────────────────
def stoplight(value: float, good_threshold: float, bad_threshold: float, higher_is_better: bool = True) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "⚪"
    if higher_is_better:
        if v >= good_threshold:
            return "🟢"
        elif v >= bad_threshold:
            return "🟡"
        else:
            return "🔴"
    else:
        if v <= good_threshold:
            return "🟢"
        elif v <= bad_threshold:
            return "🟡"
        else:
            return "🔴"


def logo_card_html(abbrev: str, label: str, sublabel: str = "") -> str:
    url = logo_url(abbrev)
    return (
        f"<div style='text-align:center;padding:10px 8px;background:#f8fafc;"
        f"border-radius:12px;border:1px solid #e2e8f0;min-width:80px;'>"
        f"<img src='{url}' width='52' height='52' style='object-fit:contain;'/>"
        f"<div style='font-weight:700;font-size:0.85rem;margin-top:4px;'>{label}</div>"
        f"<div style='font-size:0.75rem;color:#64748b;'>{sublabel}</div>"
        f"</div>"
    )


def kpi_html(label: str, value: str, sub: str = "") -> str:
    return (
        f"<div class='kpi-card'>"
        f"<div class='kpi-label'>{label}</div>"
        f"<div class='kpi-value'>{value}</div>"
        f"<div class='kpi-sub'>{sub}</div>"
        f"</div>"
    )


def prob_bar_html(label: str, pct: float, color: str = "#3b82f6") -> str:
    pct_c = max(0.0, min(100.0, float(pct)))
    return (
        f"<div style='margin-bottom:4px;'>"
        f"<div style='font-size:0.82rem;font-weight:600;margin-bottom:1px;'>{label}</div>"
        f"<div class='prob-bar-wrap'>"
        f"<div class='prob-bar-fill' style='width:{pct_c:.0f}%;background:{color};'>"
        f"{pct_c:.1f}%</div></div></div>"
    )


def result_card_html(abbrev: str, result: str, score: str, sub: str) -> str:
    color = "#22c55e" if result == "W" else "#ef4444" if result == "L" else "#f59e0b"
    url = logo_url(abbrev)
    return (
        f"<div style='text-align:center;padding:8px;background:#f8fafc;"
        f"border-radius:12px;border:2px solid {color};'>"
        f"<img src='{url}' width='42' height='42' style='object-fit:contain;'/>"
        f"<div style='font-weight:800;font-size:1.05rem;color:{color};'>{result}</div>"
        f"<div style='font-size:0.82rem;font-weight:600;'>{score}</div>"
        f"<div style='font-size:0.72rem;color:#64748b;'>{sub}</div>"
        f"</div>"
    )


def upcoming_card_html(abbrev: str, sub1: str, sub2: str) -> str:
    url = logo_url(abbrev)
    return (
        f"<div style='text-align:center;padding:8px;background:#f8fafc;"
        f"border-radius:12px;border:1px solid #e2e8f0;'>"
        f"<img src='{url}' width='42' height='42' style='object-fit:contain;'/>"
        f"<div style='font-weight:700;font-size:0.85rem;margin-top:4px;'>{abbrev}</div>"
        f"<div style='font-size:0.75rem;color:#64748b;'>{sub1}</div>"
        f"<div style='font-size:0.72rem;color:#94a3b8;'>{sub2}</div>"
        f"</div>"
    )


# ── DataFrame stoplight helpers ────────────────────────────────────────────────
def _sl_grade(val: float) -> str:
    if pd.isna(val):
        return ""
    if val >= 70:
        return "background-color:#dcfce7;color:#166534"
    if val >= 50:
        return "background-color:#fef9c3;color:#713f12"
    return "background-color:#fee2e2;color:#991b1b"


def _sl_momentum(val: float) -> str:
    if pd.isna(val):
        return ""
    if val > 55:
        return "background-color:#dcfce7;color:#166534"
    if val >= 45:
        return "background-color:#fef9c3;color:#713f12"
    return "background-color:#fee2e2;color:#991b1b"


def _sl_result(val: str) -> str:
    if val == "W":
        return "background-color:#dcfce7;color:#166534"
    if val == "OTL":
        return "background-color:#fef9c3;color:#713f12"
    if val == "L":
        return "background-color:#fee2e2;color:#991b1b"
    return ""


# ── Data loading functions ─────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_standings() -> pd.DataFrame:
    data = get_json(f"{BASE}/standings/now")
    raw = data.get("standings", data if isinstance(data, list) else [])
    rows = []
    for team in raw:
        flat = flatten_dict(team)
        rows.append(
            {
                "teamName": first_non_null(flat, ["teamName.default", "teamCommonName.default", "teamName"]),
                "teamAbbrev": first_non_null(flat, ["teamAbbrev.default", "teamAbbrev", "abbrev"]),
                "conference": first_non_null(flat, ["conferenceName", "conferenceAbbrev"]),
                "division": first_non_null(flat, ["divisionName", "divisionAbbrev"]),
                "gamesPlayed": first_non_null(flat, ["gamesPlayed"]),
                "points": first_non_null(flat, ["points"]),
                "wins": first_non_null(flat, ["wins"]),
                "losses": first_non_null(flat, ["losses"]),
                "otLosses": first_non_null(flat, ["otLosses"]),
                "goalFor": first_non_null(flat, ["goalFor", "goalsFor"]),
                "goalAgainst": first_non_null(flat, ["goalAgainst", "goalsAgainst"]),
                "goalDifferential": first_non_null(flat, ["goalDifferential"]),
                "pointPctg": first_non_null(flat, ["pointPctg", "pointsPctg"]),
                "conferenceSequence": first_non_null(flat, ["conferenceSequence"]),
                "divisionSequence": first_non_null(flat, ["divisionSequence"]),
                "wildcardSequence": first_non_null(flat, ["wildcardSequence"]),
                "l10Wins": first_non_null(flat, ["l10Wins"]),
                "l10Losses": first_non_null(flat, ["l10Losses"]),
                "l10OtLosses": first_non_null(flat, ["l10OtLosses"]),
            }
        )
    df = pd.DataFrame(rows)
    numeric_cols = [
        "gamesPlayed", "points", "wins", "losses", "otLosses",
        "goalFor", "goalAgainst", "goalDifferential",
        "conferenceSequence", "divisionSequence", "wildcardSequence",
        "l10Wins", "l10Losses", "l10OtLosses",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def get_schedule(team: str = DEFAULT_TEAM, season: str = SEASON) -> pd.DataFrame:
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
                        "isCompleted": game_state in {"OFF", "FINAL", "OVER", "DONE"}
                        or (away_score is not None and home_score is not None),
                    }
                )
    df = pd.DataFrame(games).drop_duplicates(subset=["gameId"])
    if df.empty:
        return df
    return df.sort_values(["gameDate", "gameId"]).reset_index(drop=True)


@st.cache_data(ttl=3600, show_spinner=False)
def get_boxscore(game_id: int) -> Dict[str, Any]:
    return get_json(f"{BASE}/gamecenter/{game_id}/boxscore")


def extract_team_game(game_row: pd.Series, box: Dict[str, Any], team_abbrev: str) -> Dict[str, Any]:
    flat = flatten_dict(box)
    away_score = first_non_null(flat, ["awayTeam.score"], game_row.get("awayScore"))
    home_score = first_non_null(flat, ["homeTeam.score"], game_row.get("homeScore"))
    away_shots = first_non_null(flat, ["awayTeam.sog", "awayTeam.shotsOnGoal"])
    home_shots = first_non_null(flat, ["homeTeam.sog", "homeTeam.shotsOnGoal"])

    is_home = game_row["homeTeam"] == team_abbrev
    team_score = home_score if is_home else away_score
    opp_score = away_score if is_home else home_score
    opponent = game_row["awayTeam"] if is_home else game_row["homeTeam"]

    ts = pd.to_numeric(team_score, errors="coerce")
    os_ = pd.to_numeric(opp_score, errors="coerce")

    if pd.isna(ts) or pd.isna(os_):
        result = "?"
    elif ts > os_:
        result = "W"
    elif ts < os_:
        result = "L"
    else:
        result = "OTL"

    return {
        "gameId": int(game_row["gameId"]),
        "gameDate": game_row["gameDate"],
        "venue": "Home" if is_home else "Away",
        "opponent": opponent,
        "teamScore": ts,
        "oppScore": os_,
        "result": result,
        "goalDiff": float((ts or 0) - (os_ or 0)),
        "teamShots": pd.to_numeric(home_shots if is_home else away_shots, errors="coerce"),
        "oppShots": pd.to_numeric(away_shots if is_home else home_shots, errors="coerce"),
    }


@st.cache_data(ttl=3600, show_spinner=True)
def build_team_games(team: str = DEFAULT_TEAM) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load schedule + boxscores for a single team; return (schedule, team_games)."""
    schedule = get_schedule(team)
    if schedule.empty:
        return schedule, pd.DataFrame()

    completed = schedule[schedule["isCompleted"]]
    rows = []
    for _, g in completed.iterrows():
        try:
            box = get_boxscore(int(g["gameId"]))
            rows.append(extract_team_game(g, box, team))
        except Exception:
            continue

    if not rows:
        return schedule, pd.DataFrame()

    tg = pd.DataFrame(rows).sort_values(["gameDate", "gameId"]).reset_index(drop=True)
    tg["gameNumber"] = np.arange(1, len(tg) + 1)
    tg["pointsEarned"] = tg.apply(points_from_result, axis=1)
    tg["cumulativePoints"] = tg["pointsEarned"].cumsum()
    tg["rolling3GoalDiff"] = tg["goalDiff"].rolling(3, min_periods=1).mean()
    tg["rolling5GoalDiff"] = tg["goalDiff"].rolling(5, min_periods=1).mean()
    tg["rolling10GoalDiff"] = tg["goalDiff"].rolling(10, min_periods=1).mean()
    tg["rolling5GoalsFor"] = tg["teamScore"].rolling(5, min_periods=1).mean()
    tg["rolling5GoalsAgainst"] = tg["oppScore"].rolling(5, min_periods=1).mean()
    tg["rolling10GoalsFor"] = tg["teamScore"].rolling(10, min_periods=1).mean()
    tg["rolling10GoalsAgainst"] = tg["oppScore"].rolling(10, min_periods=1).mean()
    tg["rolling5Points"] = tg["pointsEarned"].rolling(5, min_periods=1).sum()
    tg["rolling10Points"] = tg["pointsEarned"].rolling(10, min_periods=1).sum()

    # Momentum composite
    rolling_gd = tg["rolling3GoalDiff"].fillna(0)
    diff5 = (tg["rolling5GoalsFor"] - tg["rolling5GoalsAgainst"]).fillna(0)
    shot_diff = (tg["teamShots"] - tg["oppShots"]).rolling(3, min_periods=1).mean().fillna(0)
    tg["momentumScore"] = (
        0.45 * zscore(rolling_gd).fillna(0)
        + 0.30 * zscore(diff5).fillna(0)
        + 0.25 * zscore(shot_diff).fillna(0)
    ) * 10 + 50

    return schedule, tg


# ── League data / metrics ──────────────────────────────────────────────────────
def compute_team_metrics(abbrev: str, standings_df: pd.DataFrame) -> Dict[str, Any]:
    """Derive all team metrics from standings data (no schedule load needed)."""
    defaults: Dict[str, Any] = {
        "abbrev": abbrev,
        "wins": 0, "losses": 0, "otl": 0,
        "points": 0, "gamesPlayed": 1,
        "goalFor": 0, "goalAgainst": 0, "goalDifferential": 0,
        "gf_per_game": LEAGUE_AVG_GPG, "ga_per_game": LEAGUE_AVG_GPG,
        "last10_gf_per_game": LEAGUE_AVG_GPG, "last10_ga_per_game": LEAGUE_AVG_GPG,
        "l10W": 0, "l10L": 0, "l10OTL": 0, "momentum": 50.0,
    }
    if standings_df.empty:
        return defaults

    row = standings_df[standings_df["teamAbbrev"] == abbrev]
    if row.empty:
        return defaults

    r = row.iloc[0]
    gp = max(int(r.get("gamesPlayed") or 1), 1)
    gf = float(r.get("goalFor") or 0)
    ga = float(r.get("goalAgainst") or 0)
    gf_pg = gf / gp if gf > 0 else LEAGUE_AVG_GPG
    ga_pg = ga / gp if ga > 0 else LEAGUE_AVG_GPG

    l10w = int(r.get("l10Wins") or 0)
    l10l = int(r.get("l10Losses") or 0)
    l10otl = int(r.get("l10OtLosses") or 0)
    l10_games = l10w + l10l + l10otl
    l10_pts = l10w * 2 + l10otl

    # Proxy last-10 GF/GA from win rate relative to season
    if l10_games >= 5:
        l10_win_rate = l10w / l10_games
    elif gp > 0:
        l10_win_rate = int(r.get("wins") or 0) / gp
    else:
        l10_win_rate = 0.5  # neutral default when no games played yet

    season_win_rate = int(r.get("wins") or 0) / gp
    relative_form = (l10_win_rate - season_win_rate) if season_win_rate > 0 else 0

    last10_gf_pg = max(gf_pg * (1 + relative_form * 0.4), 0.5)
    last10_ga_pg = max(ga_pg * (1 - relative_form * 0.4), 0.5)

    # Momentum from last-10 points pace vs expected (10 pts = average)
    expected_l10_pts = 10.0
    momentum = 50.0 + (l10_pts - expected_l10_pts) * 3.0
    momentum = float(max(20.0, min(80.0, momentum)))

    return {
        "abbrev": abbrev,
        "wins": int(r.get("wins") or 0),
        "losses": int(r.get("losses") or 0),
        "otl": int(r.get("otLosses") or 0),
        "points": int(r.get("points") or 0),
        "gamesPlayed": gp,
        "goalFor": gf,
        "goalAgainst": ga,
        "goalDifferential": float(r.get("goalDifferential") or 0),
        "gf_per_game": round(gf_pg, 3),
        "ga_per_game": round(ga_pg, 3),
        "last10_gf_per_game": round(last10_gf_pg, 3),
        "last10_ga_per_game": round(last10_ga_pg, 3),
        "l10W": l10w,
        "l10L": l10l,
        "l10OTL": l10otl,
        "momentum": round(momentum, 1),
    }


@st.cache_data(ttl=3600, show_spinner=False)
def build_league_data() -> Tuple[pd.DataFrame, Dict[str, Dict]]:
    standings = get_standings()
    if standings.empty:
        return standings, {}
    metrics: Dict[str, Dict] = {}
    for _, row in standings.iterrows():
        abbrev = row.get("teamAbbrev")
        if abbrev:
            metrics[str(abbrev)] = compute_team_metrics(str(abbrev), standings)
    return standings, metrics


def _project_playoff_seed(
    team_abbrev: str,
    standings_df: pd.DataFrame,
    conf_name: str,
    team_proj_pts: float,
) -> Tuple[Optional[int], Optional[str]]:
    """Project conference seed (1–8) and first-round opponent for a team."""
    mask = standings_df["conference"].astype(str).str.contains(conf_name, case=False, na=False)
    conf = standings_df[mask].copy()
    if conf.empty:
        return None, None

    conf["points"] = pd.to_numeric(conf["points"], errors="coerce").fillna(0)
    conf["gamesPlayed"] = pd.to_numeric(conf["gamesPlayed"], errors="coerce").fillna(0)
    conf["pts_pct"] = conf["points"] / (conf["gamesPlayed"] * 2).clip(lower=1)
    conf["remaining"] = (GAMES_IN_SEASON - conf["gamesPlayed"]).clip(lower=0)
    conf["proj_pts"] = conf["points"] + conf["remaining"] * 2 * conf["pts_pct"]
    conf.loc[conf["teamAbbrev"] == team_abbrev, "proj_pts"] = team_proj_pts

    conf = conf.sort_values("proj_pts", ascending=False).reset_index(drop=True)
    playoff_8 = conf.head(8)["teamAbbrev"].tolist()

    if team_abbrev not in playoff_8:
        return None, None

    seed = playoff_8.index(team_abbrev) + 1
    bracket = {1: 8, 2: 7, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}
    opp_seed = bracket.get(seed)
    opp = playoff_8[opp_seed - 1] if opp_seed and opp_seed <= len(playoff_8) else None
    return seed, opp


def compute_outlook(
    team_abbrev: str,
    standings_df: pd.DataFrame,
    team_metrics_dict: Dict[str, Dict],
) -> Dict[str, Any]:
    metrics = team_metrics_dict.get(team_abbrev, compute_team_metrics(team_abbrev, standings_df))
    cur_pts = metrics.get("points", 0)
    gp = metrics.get("gamesPlayed", 0)
    gd = metrics.get("goalDifferential", 0)

    remaining = max(GAMES_IN_SEASON - gp, 0)
    pts_pct = cur_pts / max(gp * 2, 1)
    proj_pts = cur_pts + remaining * 2 * pts_pct

    # Conference context
    conf_name = ""
    conf_rank_val: Optional[int] = None
    if not standings_df.empty:
        tr = standings_df[standings_df["teamAbbrev"] == team_abbrev]
        if not tr.empty:
            conf_name = str(tr.iloc[0].get("conference") or "")
            cr = tr.iloc[0].get("conferenceSequence")
            try:
                conf_rank_val = int(cr) if cr is not None and not pd.isna(cr) else None
            except Exception:
                conf_rank_val = None

    # Cutoff (8th seed in conference)
    cutoff = gap = np.nan
    if conf_name and not standings_df.empty:
        mask = standings_df["conference"].astype(str).str.contains(conf_name, case=False, na=False)
        c_pts = pd.to_numeric(standings_df.loc[mask, "points"], errors="coerce").sort_values(ascending=False)
        if len(c_pts) >= 8:
            cutoff = float(c_pts.iloc[7])
            gap = float(cur_pts - cutoff)

    # Proxy odds
    pace_c = max(min((proj_pts - 90) / 18, 1.0), -1.0)
    diff_c = max(min(gd / 40, 1.0), -1.0)
    gap_c = 0.0 if pd.isna(gap) else max(min(gap / 10, 1.0), -1.0)
    playoff_odds = round(float(max(min(50 + 22 * pace_c + 14 * diff_c + 14 * gap_c, 99), 1)), 1)

    # Projected record
    proj_wins_add = int(round(remaining * pts_pct * 0.88))
    proj_otl_add = int(round(remaining * pts_pct * 0.12))
    proj_l_add = max(remaining - proj_wins_add - proj_otl_add, 0)
    proj_w = metrics.get("wins", 0) + proj_wins_add
    proj_l = metrics.get("losses", 0) + proj_l_add
    proj_otl = metrics.get("otl", 0) + proj_otl_add

    # Projected seed + opponent
    proj_seed, proj_opp = _project_playoff_seed(team_abbrev, standings_df, conf_name, proj_pts)

    return {
        "current_points": cur_pts,
        "games_played": gp,
        "remaining": remaining,
        "projected_points": round(proj_pts, 1),
        "projected_record": fmt_record(proj_w, proj_l, proj_otl),
        "playoff_odds": playoff_odds,
        "gap_to_cutoff": None if pd.isna(gap) else int(gap),
        "west_cutoff_points": None if pd.isna(cutoff) else int(cutoff),
        "conference_rank": conf_rank_val,
        "projected_seed": proj_seed,
        "projected_opponent": proj_opp,
        "conference": conf_name,
    }


def build_playoff_projection_table(standings_df: pd.DataFrame, conf_name: str) -> pd.DataFrame:
    mask = standings_df["conference"].astype(str).str.contains(conf_name, case=False, na=False)
    conf = standings_df[mask].copy()
    if conf.empty:
        return pd.DataFrame()

    for col in ["points", "gamesPlayed", "wins", "losses", "otLosses"]:
        conf[col] = pd.to_numeric(conf[col], errors="coerce").fillna(0)

    conf["pts_pct"] = conf["points"] / (conf["gamesPlayed"] * 2).clip(lower=1)
    conf["remaining"] = (GAMES_IN_SEASON - conf["gamesPlayed"]).clip(lower=0)
    conf["proj_pts"] = (conf["points"] + conf["remaining"] * 2 * conf["pts_pct"]).round(1)
    conf["Record"] = conf.apply(
        lambda r: fmt_record(int(r["wins"]), int(r["losses"]), int(r["otLosses"])), axis=1
    )
    conf = conf.sort_values("proj_pts", ascending=False).reset_index(drop=True)
    conf["conf_rank"] = conf.index + 1
    conf["in_playoffs"] = conf["conf_rank"] <= 8
    return conf[["teamAbbrev", "teamName", "Record", "points", "proj_pts", "conf_rank", "in_playoffs", "division"]]


def get_seed_prob_distribution(
    team_abbrev: str, standings_df: pd.DataFrame
) -> Dict[int, float]:
    tr = standings_df[standings_df["teamAbbrev"] == team_abbrev]
    if tr.empty:
        return {}
    conf_name = str(tr.iloc[0].get("conference") or "")
    mask = standings_df["conference"].astype(str).str.contains(conf_name, case=False, na=False)
    conf = standings_df[mask].copy()
    conf["points"] = pd.to_numeric(conf["points"], errors="coerce").fillna(0)
    conf["gamesPlayed"] = pd.to_numeric(conf["gamesPlayed"], errors="coerce").fillna(0)
    conf["pts_pct"] = conf["points"] / (conf["gamesPlayed"] * 2).clip(lower=1)
    conf["remaining"] = (GAMES_IN_SEASON - conf["gamesPlayed"]).clip(lower=0)
    conf["proj_pts"] = conf["points"] + conf["remaining"] * 2 * conf["pts_pct"]
    conf = conf.sort_values("proj_pts", ascending=False).reset_index(drop=True)

    team_rank_arr = conf[conf["teamAbbrev"] == team_abbrev].index.tolist()
    if not team_rank_arr:
        return {}
    rank = team_rank_arr[0] + 1

    probs = {seed: max(0.0, 40.0 - abs(seed - rank) * 11.0) for seed in range(1, 9)}
    total = sum(probs.values())
    if total > 0:
        probs = {k: round(v / total * 100, 1) for k, v in probs.items()}
    return probs


# ── Monte Carlo simulation ─────────────────────────────────────────────────────
def monte_carlo_sim(
    team_a_metrics: Dict,
    team_b_metrics: Dict,
    home_team: str = "A",
    n_sims: int = 10000,
) -> Dict[str, Any]:
    SEASON_W = 0.70
    LAST10_W = 0.30
    HOME_ADV = 0.15

    a_attack = SEASON_W * team_a_metrics["gf_per_game"] + LAST10_W * team_a_metrics["last10_gf_per_game"]
    a_defense = SEASON_W * team_a_metrics["ga_per_game"] + LAST10_W * team_a_metrics["last10_ga_per_game"]
    b_attack = SEASON_W * team_b_metrics["gf_per_game"] + LAST10_W * team_b_metrics["last10_gf_per_game"]
    b_defense = SEASON_W * team_b_metrics["ga_per_game"] + LAST10_W * team_b_metrics["last10_ga_per_game"]

    # Expected goals per game via interaction model
    a_lambda = (a_attack / LEAGUE_AVG_GPG) * b_defense
    b_lambda = (b_attack / LEAGUE_AVG_GPG) * a_defense

    # Apply home ice
    if home_team == "A":
        a_lambda = a_lambda + HOME_ADV
        b_lambda = max(b_lambda - HOME_ADV, 0.5)
    else:
        b_lambda = b_lambda + HOME_ADV
        a_lambda = max(a_lambda - HOME_ADV, 0.5)

    a_lambda = max(float(a_lambda), 0.5)
    b_lambda = max(float(b_lambda), 0.5)

    rng = np.random.default_rng()
    a_goals = rng.poisson(a_lambda, n_sims)
    b_goals = rng.poisson(b_lambda, n_sims)

    ties = a_goals == b_goals
    a_wins_reg = a_goals > b_goals
    b_wins_reg = b_goals > a_goals
    ot_a = ties & (rng.random(n_sims) > 0.5)
    ot_b = ties & ~ot_a

    return {
        "a_win_pct": (a_wins_reg.sum() + ot_a.sum()) / n_sims * 100,
        "b_win_pct": (b_wins_reg.sum() + ot_b.sum()) / n_sims * 100,
        "a_reg_win_pct": a_wins_reg.sum() / n_sims * 100,
        "b_reg_win_pct": b_wins_reg.sum() / n_sims * 100,
        "ot_pct": ties.sum() / n_sims * 100,
        "a_avg_goals": float(a_goals.mean()),
        "b_avg_goals": float(b_goals.mean()),
        "a_goals_arr": a_goals,
        "b_goals_arr": b_goals,
        "a_lambda": a_lambda,
        "b_lambda": b_lambda,
    }


# ── Chart functions ────────────────────────────────────────────────────────────
_CHART_LAYOUT = dict(template="plotly_white", margin=dict(l=20, r=20, t=50, b=10))
_SPLINE = dict(shape="spline", smoothing=1.2)


def plot_rolling_trend(tg: pd.DataFrame, window: int = 5) -> go.Figure:
    gf_col = f"rolling{window}GoalsFor"
    ga_col = f"rolling{window}GoalsAgainst"
    pts_col = f"rolling{window}Points"
    fig = go.Figure()
    if gf_col in tg.columns:
        fig.add_trace(
            go.Scatter(
                x=tg["gameDate"], y=tg[gf_col],
                mode="lines+markers",
                name=f"GF ({window}g)",
                line={**_SPLINE, "color": "#22c55e", "width": 2.5},
                marker=dict(size=5),
            )
        )
    if ga_col in tg.columns:
        fig.add_trace(
            go.Scatter(
                x=tg["gameDate"], y=tg[ga_col],
                mode="lines+markers",
                name=f"GA ({window}g)",
                line={**_SPLINE, "color": "#ef4444", "width": 2.5},
                marker=dict(size=5),
            )
        )
    if pts_col in tg.columns:
        fig.add_trace(
            go.Scatter(
                x=tg["gameDate"], y=tg[pts_col],
                mode="lines+markers",
                name=f"Pts ({window}g)", yaxis="y2",
                line={**_SPLINE, "color": "#3b82f6", "width": 2},
                marker=dict(size=4),
            )
        )
    fig.update_layout(
        **_CHART_LAYOUT,
        title=f"Rolling {window}-Game Trend",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(title="Goals"),
        yaxis2=dict(title=f"Points ({window}g)", overlaying="y", side="right"),
        height=370,
    )
    return fig


def plot_goal_diff_trend(tg: pd.DataFrame) -> go.Figure:
    gd = tg["goalDiff"]
    colors = ["#22c55e" if v > 0 else "#ef4444" if v < 0 else "#f59e0b" for v in gd]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=tg["gameDate"], y=gd,
            marker_color=colors, opacity=0.72, name="Goal Diff",
            hovertemplate="<b>%{x|%b %d}</b><br>Goal diff: %{y}<extra></extra>",
        )
    )
    if "rolling5GoalDiff" in tg.columns:
        fig.add_trace(
            go.Scatter(
                x=tg["gameDate"], y=tg["rolling5GoalDiff"],
                mode="lines", name="5-Game Trend",
                line={**_SPLINE, "color": "#1d4ed8", "width": 2.5},
            )
        )
    fig.add_hline(y=0, line_dash="dot", line_color="#94a3b8", line_width=1)
    fig.update_layout(
        **_CHART_LAYOUT,
        title="Goal Differential (per game)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=340,
    )
    return fig


def plot_momentum(tg: pd.DataFrame) -> go.Figure:
    ms = tg["momentumScore"]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=tg["gameDate"], y=ms,
            mode="lines+markers",
            line={**_SPLINE, "color": "#8b5cf6", "width": 2.5},
            marker=dict(
                size=6,
                color=ms,
                colorscale=[
                    [0, "#ef4444"], [0.45, "#ef4444"],
                    [0.45, "#f59e0b"], [0.55, "#f59e0b"],
                    [0.55, "#22c55e"], [1, "#22c55e"],
                ],
                cmin=30, cmax=70, showscale=False,
            ),
            fill="tozeroy",
            fillcolor="rgba(139,92,246,0.07)",
            name="Momentum",
        )
    )
    fig.add_hline(y=50, line_dash="dash", line_color="#94a3b8", line_width=1)
    fig.add_hrect(y0=55, y1=100, fillcolor="#22c55e", opacity=0.04, line_width=0)
    fig.add_hrect(y0=0, y1=45, fillcolor="#ef4444", opacity=0.04, line_width=0)
    fig.update_layout(**_CHART_LAYOUT, title="Momentum Score", height=320)
    return fig


def plot_points_path(tg: pd.DataFrame, projected_points: float) -> go.Figure:
    pts = tg[["gameDate", "cumulativePoints"]].copy()
    pace = np.linspace(0, projected_points, len(pts))
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=pts["gameDate"], y=pts["cumulativePoints"],
            mode="lines+markers", name="Actual",
            line={**_SPLINE, "color": "#3b82f6", "width": 2.5},
            marker=dict(size=5),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=pts["gameDate"], y=pace,
            mode="lines", name="Projected pace",
            line=dict(dash="dash", color="#94a3b8", width=1.5),
        )
    )
    fig.update_layout(**_CHART_LAYOUT, height=360, title="Points Path vs Projected Pace")
    return fig


def plot_sim_histogram(
    a_goals: np.ndarray, b_goals: np.ndarray, team_a: str, team_b: str
) -> go.Figure:
    from collections import Counter

    max_g = int(max(a_goals.max(), b_goals.max(), 8))
    x = list(range(0, max_g + 1))
    n = len(a_goals)
    ca = Counter(a_goals.tolist())
    cb = Counter(b_goals.tolist())
    ya = [ca.get(g, 0) / n * 100 for g in x]
    yb = [cb.get(g, 0) / n * 100 for g in x]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x, y=ya, name=team_a, opacity=0.78, marker_color="#3b82f6"))
    fig.add_trace(go.Bar(x=x, y=yb, name=team_b, opacity=0.78, marker_color="#ef4444"))
    fig.update_layout(
        **_CHART_LAYOUT,
        barmode="group",
        title="Simulated Goals Distribution (10,000 games)",
        xaxis_title="Goals Scored",
        yaxis_title="Frequency (%)",
        height=360,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════════════════

# Load league data at startup
with st.spinner("Loading NHL standings data…"):
    try:
        standings_df, team_metrics_dict = build_league_data()
    except Exception as _e:
        standings_df = pd.DataFrame()
        team_metrics_dict = {}
        st.warning(f"Could not load standings: {_e}")

# Sorted team list; ensure DEFAULT is first if available
all_teams: List[str] = (
    sorted(standings_df["teamAbbrev"].dropna().unique().tolist())
    if not standings_df.empty
    else [DEFAULT_TEAM]
)
if DEFAULT_TEAM in all_teams:
    all_teams = [DEFAULT_TEAM] + [t for t in all_teams if t != DEFAULT_TEAM]

# Team name lookup
team_name_map: Dict[str, str] = {}
if not standings_df.empty:
    for _, _r in standings_df.iterrows():
        ab = _r.get("teamAbbrev")
        nm = _r.get("teamName")
        if ab:
            team_name_map[str(ab)] = str(nm) if nm else str(ab)

# ── Header ─────────────────────────────────────────────────────────────────────
hdr_left, hdr_right = st.columns([4, 1])
with hdr_left:
    st.markdown(
        "<h1 style='margin-bottom:0;font-size:1.75rem;'>🏒 NHL Intelligence Dashboard</h1>",
        unsafe_allow_html=True,
    )
with hdr_right:
    selected_team = st.selectbox(
        "Team",
        all_teams,
        index=0,
        key="global_team",
        label_visibility="collapsed",
    )

sel_name = team_name_map.get(selected_team, selected_team)
sel_metrics = team_metrics_dict.get(selected_team, compute_team_metrics(selected_team, standings_df))
sel_outlook = compute_outlook(selected_team, standings_df, team_metrics_dict)

# Load detailed game data for selected team
with st.spinner(f"Loading {selected_team} game data…"):
    try:
        sel_schedule, sel_tg = build_team_games(selected_team)
    except Exception:
        sel_schedule = pd.DataFrame()
        sel_tg = pd.DataFrame()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_ov, tab_tr, tab_pl, tab_cmp, tab_sim = st.tabs(
    ["📊 Overview", "📈 Trends", "🏆 Playoff Race", "⚖️ Compare", "🎲 Simulate"]
)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
with tab_ov:
    # Identity row
    id_logo, id_stats = st.columns([1, 5])
    with id_logo:
        st.markdown(
            logo_card_html(
                selected_team,
                selected_team,
                f"{sel_metrics.get('gamesPlayed', 0)} GP",
            ),
            unsafe_allow_html=True,
        )
    with id_stats:
        w = sel_metrics.get("wins", 0)
        l = sel_metrics.get("losses", 0)
        otl = sel_metrics.get("otl", 0)
        pts = sel_metrics.get("points", 0)
        gd = sel_metrics.get("goalDifferential", 0)
        odds = sel_outlook.get("playoff_odds", 0)
        proj_pts = sel_outlook.get("projected_points", 0)
        mom = sel_metrics.get("momentum", 50)

        sl_odds = stoplight(odds, 70, 45)
        sl_gd = stoplight(gd, 10, -10)
        sl_mom = stoplight(mom, 55, 45)

        ov_c1, ov_c2, ov_c3, ov_c4, ov_c5 = st.columns(5)
        ov_c1.markdown(
            kpi_html("Record", fmt_record(w, l, otl), f"{pts} pts"), unsafe_allow_html=True
        )
        ov_c2.markdown(
            kpi_html("Proj. Record", sel_outlook.get("projected_record", "—"), f"~{proj_pts} pts"),
            unsafe_allow_html=True,
        )
        ov_c3.markdown(
            kpi_html("Playoff Odds", f"{sl_odds} {odds:.0f}%", "Internal model proxy"),
            unsafe_allow_html=True,
        )
        ov_c4.markdown(
            kpi_html("Goal Diff", f"{sl_gd} {gd:+d}", "Season to date"),
            unsafe_allow_html=True,
        )
        ov_c5.markdown(
            kpi_html("Momentum", f"{sl_mom} {mom:.0f}", "Last 10 composite"),
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Second row: projected opponent | next game | projected seed
    opp_col, ng_col, seed_col = st.columns(3)

    with opp_col:
        st.markdown("**🎯 Projected First-Round Opponent**")
        proj_opp = sel_outlook.get("projected_opponent")
        if proj_opp:
            opp_nm = team_name_map.get(proj_opp, proj_opp)
            st.markdown(logo_card_html(proj_opp, proj_opp, opp_nm), unsafe_allow_html=True)
        else:
            st.markdown("<span class='muted'>Outside playoff picture</span>", unsafe_allow_html=True)

    with ng_col:
        st.markdown("**📅 Next Game**")
        if not sel_schedule.empty:
            upcoming = sel_schedule[~sel_schedule["isCompleted"]].sort_values("gameDate")
            if not upcoming.empty:
                ng = upcoming.iloc[0]
                opp_ng = ng["awayTeam"] if ng["homeTeam"] == selected_team else ng["homeTeam"]
                venue_ng = "Home" if ng["homeTeam"] == selected_team else "Away"
                raw_date = ng.get("gameDate")
                date_ng = (
                    pd.to_datetime(raw_date).strftime("%b %d")
                    if raw_date is not None and pd.notna(raw_date)
                    else "TBD"
                )
                # Quick projected score
                ng_m = team_metrics_dict.get(
                    opp_ng, compute_team_metrics(str(opp_ng), standings_df)
                )
                ng_sim = monte_carlo_sim(sel_metrics, ng_m, home_team="A" if venue_ng == "Home" else "B", n_sims=2000)
                proj_a = round(ng_sim["a_avg_goals"])
                proj_b = round(ng_sim["b_avg_goals"])
                st.markdown(
                    logo_card_html(str(opp_ng), f"vs {opp_ng}", f"{date_ng} · {venue_ng}"),
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"**Projected:** `{selected_team} {proj_a} – {proj_b} {opp_ng}`"
                )
            else:
                st.markdown("<span class='muted'>No upcoming games found</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span class='muted'>Schedule unavailable</span>", unsafe_allow_html=True)

    with seed_col:
        st.markdown("**🏅 Projected Playoff Seed**")
        proj_seed = sel_outlook.get("projected_seed")
        conf_str = sel_outlook.get("conference", "Conference") or "Conference"
        if proj_seed:
            st.markdown(
                kpi_html(conf_str, f"#{proj_seed} Seed", "Based on current pace"),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                kpi_html("Playoff Status", "Outside Top 8", "Not currently projected in"),
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # Recent 5 games row
    st.markdown("### Last 5 Games")
    if not sel_tg.empty:
        last5 = sel_tg.tail(5)
        rcols = st.columns(5)
        for _i, (_, _row) in enumerate(last5.iterrows()):
            opp_r = str(_row.get("opponent") or "?")
            res_r = str(_row.get("result") or "?")
            ts_r = int(_row.get("teamScore") or 0)
            os_r = int(_row.get("oppScore") or 0)
            raw_d = _row.get("gameDate")
            date_r = (
                pd.to_datetime(raw_d).strftime("%b %d")
                if raw_d is not None and pd.notna(raw_d)
                else ""
            )
            with rcols[_i]:
                st.markdown(
                    result_card_html(opp_r, res_r, f"{ts_r}–{os_r}", date_r),
                    unsafe_allow_html=True,
                )

        st.markdown("")
        ch1, ch2 = st.columns([1.35, 1])
        with ch1:
            st.plotly_chart(plot_goal_diff_trend(sel_tg), width="stretch")
        with ch2:
            st.plotly_chart(plot_momentum(sel_tg), width="stretch")
    else:
        st.info("No completed game data available yet for this team.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — TRENDS
# ══════════════════════════════════════════════════════════════════════════════
with tab_tr:
    if sel_tg.empty:
        st.info("No game data available for the selected team.")
    else:
        tc1, tc2 = st.columns(2)
        with tc1:
            st.plotly_chart(plot_rolling_trend(sel_tg, window=5), width="stretch")
        with tc2:
            st.plotly_chart(plot_rolling_trend(sel_tg, window=10), width="stretch")

        st.plotly_chart(plot_goal_diff_trend(sel_tg), width="stretch")
        st.plotly_chart(
            plot_points_path(sel_tg, sel_outlook.get("projected_points", 0)),
            width="stretch",
        )

        # Last 5 results
        st.markdown("### Last 5 Games")
        last5_tr = sel_tg.tail(5)
        lc = st.columns(min(5, max(len(last5_tr), 1)))
        for _i, (_, _row) in enumerate(last5_tr.iterrows()):
            if _i >= 5:
                break
            opp_t = str(_row.get("opponent") or "?")
            res_t = str(_row.get("result") or "?")
            ts_t = int(_row.get("teamScore") or 0)
            os_t = int(_row.get("oppScore") or 0)
            ven_t = str(_row.get("venue") or "")
            raw_dt = _row.get("gameDate")
            date_t = (
                pd.to_datetime(raw_dt).strftime("%b %d")
                if raw_dt is not None and pd.notna(raw_dt)
                else ""
            )
            with lc[_i]:
                st.markdown(
                    result_card_html(opp_t, res_t, f"{ts_t}–{os_t}", f"{ven_t} · {date_t}"),
                    unsafe_allow_html=True,
                )

        # Next 5 upcoming
        st.markdown("### Next 5 Games")
        if not sel_schedule.empty:
            upcoming5 = (
                sel_schedule[~sel_schedule["isCompleted"]]
                .sort_values("gameDate")
                .head(5)
            )
            if not upcoming5.empty:
                uc = st.columns(min(5, len(upcoming5)))
                for _i, (_, _row) in enumerate(upcoming5.iterrows()):
                    if _i >= 5:
                        break
                    opp_u = str(
                        _row["awayTeam"] if _row["homeTeam"] == selected_team else _row["homeTeam"]
                    )
                    ven_u = "Home" if _row["homeTeam"] == selected_team else "Away"
                    raw_du = _row.get("gameDate")
                    date_u = (
                        pd.to_datetime(raw_du).strftime("%b %d")
                        if raw_du is not None and pd.notna(raw_du)
                        else "TBD"
                    )
                    with uc[_i]:
                        st.markdown(
                            upcoming_card_html(opp_u, ven_u, date_u),
                            unsafe_allow_html=True,
                        )
            else:
                st.info("No upcoming games found in schedule.")
        else:
            st.info("Schedule data unavailable.")

        # Full game log
        st.markdown("### Full Season Game Log")
        log_df = sel_tg[
            ["gameDate", "venue", "opponent", "teamScore", "oppScore", "result", "goalDiff", "momentumScore"]
        ].copy()
        log_df["gameDate"] = log_df["gameDate"].dt.strftime("%b %d")
        st.dataframe(
            log_df.style.format(
                {"momentumScore": "{:.1f}", "goalDiff": "{:+.0f}"}, na_rep="-"
            )
            .map(_sl_result, subset=["result"])
            .map(_sl_momentum, subset=["momentumScore"]),
            width="stretch",
            hide_index=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — PLAYOFF RACE
# ══════════════════════════════════════════════════════════════════════════════
with tab_pl:
    conf_name = sel_outlook.get("conference") or ""

    # KPI row
    _pr1, _pr2, _pr3, _pr4 = st.columns(4)
    _conf_rank_val = sel_outlook.get("conference_rank")
    _pr1.markdown(
        kpi_html(
            "Conf. Rank",
            f"#{_conf_rank_val}" if _conf_rank_val else "—",
            f"{sel_metrics.get('points', 0)} pts",
        ),
        unsafe_allow_html=True,
    )
    _pr2.markdown(
        kpi_html("Proj. Points", str(sel_outlook.get("projected_points", "—")), "End-of-season pace"),
        unsafe_allow_html=True,
    )
    _pr3.markdown(
        kpi_html(
            "Proj. Seed",
            f"#{sel_outlook.get('projected_seed')}" if sel_outlook.get("projected_seed") else "Outside top 8",
            f"{conf_name} Conference",
        ),
        unsafe_allow_html=True,
    )
    _sl_pl = stoplight(sel_outlook.get("playoff_odds", 0), 70, 45)
    _pr4.markdown(
        kpi_html("Playoff Odds", f"{_sl_pl} {sel_outlook.get('playoff_odds', 0):.0f}%", "Internal proxy model"),
        unsafe_allow_html=True,
    )

    st.markdown("---")

    pl_left, pl_right = st.columns([1, 2])
    with pl_left:
        st.markdown("**🎯 Projected First-Round Opponent**")
        _pl_opp = sel_outlook.get("projected_opponent")
        if _pl_opp:
            st.markdown(
                logo_card_html(_pl_opp, _pl_opp, team_name_map.get(_pl_opp, "")),
                unsafe_allow_html=True,
            )
            # Also show 2nd most likely (seed ±1)
            seed_probs = get_seed_prob_distribution(selected_team, standings_df)
            if seed_probs and sel_outlook.get("projected_seed"):
                cur_seed = int(sel_outlook["projected_seed"])
                bracket_map = {1: 8, 2: 7, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}
                alt_seed_num = bracket_map.get(max(1, cur_seed - 1) if cur_seed > 1 else cur_seed + 1)
                if alt_seed_num and not standings_df.empty:
                    mask_c = standings_df["conference"].astype(str).str.contains(conf_name, case=False, na=False)
                    cdf = standings_df[mask_c].copy()
                    cdf["points"] = pd.to_numeric(cdf["points"], errors="coerce").fillna(0)
                    cdf_sorted = cdf.sort_values("points", ascending=False).reset_index(drop=True)
                    if alt_seed_num <= len(cdf_sorted):
                        alt_opp = cdf_sorted.iloc[alt_seed_num - 1]["teamAbbrev"]
                        if alt_opp != _pl_opp:
                            st.markdown(
                                f"<div style='margin-top:8px;font-size:0.82rem;color:#64748b;'>2nd most likely:</div>",
                                unsafe_allow_html=True,
                            )
                            st.markdown(
                                logo_card_html(str(alt_opp), str(alt_opp), team_name_map.get(str(alt_opp), "")),
                                unsafe_allow_html=True,
                            )
        else:
            st.markdown(
                "<span class='muted'>Not currently projected for playoffs</span>",
                unsafe_allow_html=True,
            )

    with pl_right:
        st.markdown("**📊 Seed Probability Distribution**")
        seed_probs = get_seed_prob_distribution(selected_team, standings_df)
        if seed_probs:
            seed_colors_map = {
                1: "#f59e0b", 2: "#3b82f6", 3: "#3b82f6",
                4: "#22c55e", 5: "#22c55e",
                6: "#94a3b8", 7: "#94a3b8", 8: "#ef4444",
            }
            prob_html_str = ""
            for _s in range(1, 9):
                _p = seed_probs.get(_s, 0)
                _c = seed_colors_map.get(_s, "#94a3b8")
                _label = f"Seed #{_s}"
                prob_html_str += prob_bar_html(_label, _p, _c)
            st.markdown(prob_html_str, unsafe_allow_html=True)
        else:
            st.info("Seed probability distribution unavailable.")

    st.markdown("---")
    st.markdown(f"### {conf_name} Conference Standings & Projection")

    if not standings_df.empty and conf_name:
        proj_tbl = build_playoff_projection_table(standings_df, conf_name)
        if not proj_tbl.empty:
            proj_tbl["Playoff"] = proj_tbl["in_playoffs"].map({True: "✅ IN", False: "❌ OUT"})

            def _hl_team(row: pd.Series) -> List[str]:
                if row.get("teamAbbrev") == selected_team:
                    return ["background-color:#eff6ff;font-weight:bold"] * len(row)
                if row.get("in_playoffs"):
                    return ["background-color:#f0fdf4"] * len(row)
                return [""] * len(row)

            disp_cols = ["conf_rank", "teamAbbrev", "teamName", "Record", "points", "proj_pts", "division", "Playoff"]
            st.dataframe(
                proj_tbl[disp_cols]
                .rename(
                    columns={
                        "conf_rank": "Rank",
                        "teamAbbrev": "Team",
                        "teamName": "Name",
                        "points": "Pts",
                        "proj_pts": "Proj Pts",
                        "division": "Division",
                    }
                )
                .style.apply(_hl_team, axis=1),
                width="stretch",
                hide_index=True,
            )
    else:
        st.info("Conference standings data unavailable.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — COMPARE
# ══════════════════════════════════════════════════════════════════════════════
with tab_cmp:
    cmp_ac, cmp_bc = st.columns(2)
    with cmp_ac:
        team_a_sel = st.selectbox(
            "Team A",
            all_teams,
            index=0,
            key="cmp_a",
        )
    with cmp_bc:
        _b_default = 1 if len(all_teams) > 1 else 0
        team_b_sel = st.selectbox(
            "Team B",
            all_teams,
            index=_b_default,
            key="cmp_b",
        )

    ma = team_metrics_dict.get(team_a_sel, compute_team_metrics(team_a_sel, standings_df))
    mb = team_metrics_dict.get(team_b_sel, compute_team_metrics(team_b_sel, standings_df))
    oa = compute_outlook(team_a_sel, standings_df, team_metrics_dict)
    ob = compute_outlook(team_b_sel, standings_df, team_metrics_dict)

    # Logo headers
    hdr_a, hdr_vs, hdr_b = st.columns([2, 1, 2])
    with hdr_a:
        st.markdown(
            logo_card_html(
                team_a_sel,
                team_name_map.get(team_a_sel, team_a_sel),
                fmt_record(ma["wins"], ma["losses"], ma["otl"]),
            ),
            unsafe_allow_html=True,
        )
    with hdr_vs:
        st.markdown(
            "<div style='text-align:center;padding:22px 0;font-size:1.4rem;font-weight:800;color:#64748b;'>VS</div>",
            unsafe_allow_html=True,
        )
    with hdr_b:
        st.markdown(
            logo_card_html(
                team_b_sel,
                team_name_map.get(team_b_sel, team_b_sel),
                fmt_record(mb["wins"], mb["losses"], mb["otl"]),
            ),
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Mirrored comparison rows
    def _cmp_rows(
        label: str,
        val_a: Any,
        val_b: Any,
        good: float,
        bad: float,
        hib: bool = True,
        fmt_str: str = "{}",
    ) -> Tuple[str, str, str, str, str]:
        try:
            va_s = fmt_str.format(val_a)
            vb_s = fmt_str.format(val_b)
        except Exception:
            va_s, vb_s = str(val_a), str(val_b)
        try:
            sl_a = stoplight(float(val_a), good, bad, hib)
            sl_b = stoplight(float(val_b), good, bad, hib)
        except Exception:
            sl_a = sl_b = "⚪"
        return label, sl_a, va_s, vb_s, sl_b

    cmp_data = [
        _cmp_rows("Current Points", ma["points"], mb["points"], 90, 70, True, "{:.0f}"),
        _cmp_rows("Proj. Points", oa["projected_points"], ob["projected_points"], 95, 80, True, "{:.0f}"),
        _cmp_rows("Playoff Odds %", oa["playoff_odds"], ob["playoff_odds"], 70, 45, True, "{:.0f}"),
        _cmp_rows("Goal Differential", ma["goalDifferential"], mb["goalDifferential"], 10, -10, True, "{:+.0f}"),
        _cmp_rows("GF / Game", ma["gf_per_game"], mb["gf_per_game"], 3.2, 2.8, True, "{:.2f}"),
        _cmp_rows("GA / Game", ma["ga_per_game"], mb["ga_per_game"], 2.5, 3.0, False, "{:.2f}"),
        _cmp_rows("Momentum", ma["momentum"], mb["momentum"], 55, 45, True, "{:.0f}"),
        _cmp_rows("Last 10 GF/G", ma["last10_gf_per_game"], mb["last10_gf_per_game"], 3.2, 2.8, True, "{:.2f}"),
        _cmp_rows("Last 10 GA/G", ma["last10_ga_per_game"], mb["last10_ga_per_game"], 2.5, 3.0, False, "{:.2f}"),
        _cmp_rows(
            "Last 10 Record",
            ma["l10W"] * 2 + ma["l10OTL"],
            mb["l10W"] * 2 + mb["l10OTL"],
            14, 10, True, "{:.0f} pts",
        ),
    ]

    # Column headers
    hc_a, hc_mid, hc_b = st.columns([3, 3, 3])
    hc_a.markdown(f"<div style='text-align:right;font-weight:700;color:#1d4ed8;'>{team_a_sel}</div>", unsafe_allow_html=True)
    hc_mid.markdown("<div style='text-align:center;font-weight:700;color:#64748b;'>Metric</div>", unsafe_allow_html=True)
    hc_b.markdown(f"<div style='text-align:left;font-weight:700;color:#dc2626;'>{team_b_sel}</div>", unsafe_allow_html=True)

    for _lbl, _sla, _va, _vb, _slb in cmp_data:
        _ca, _cb, _cc = st.columns([3, 3, 3])
        _ca.markdown(
            f"<div style='text-align:right;padding:4px 8px;font-size:0.95rem;'>{_sla} <b>{_va}</b></div>",
            unsafe_allow_html=True,
        )
        _cb.markdown(
            f"<div style='text-align:center;padding:4px 8px;font-size:0.82rem;color:#64748b;font-weight:600;'>{_lbl}</div>",
            unsafe_allow_html=True,
        )
        _cc.markdown(
            f"<div style='text-align:left;padding:4px 8px;font-size:0.95rem;'><b>{_vb}</b> {_slb}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    opp_a_col, opp_b_col = st.columns(2)
    with opp_a_col:
        st.markdown(f"**{team_a_sel} Projected Opponent**")
        _opp_a = oa.get("projected_opponent")
        if _opp_a:
            st.markdown(
                logo_card_html(_opp_a, _opp_a, team_name_map.get(_opp_a, "")),
                unsafe_allow_html=True,
            )
        else:
            st.markdown("<span class='muted'>Not projected for playoffs</span>", unsafe_allow_html=True)
    with opp_b_col:
        st.markdown(f"**{team_b_sel} Projected Opponent**")
        _opp_b = ob.get("projected_opponent")
        if _opp_b:
            st.markdown(
                logo_card_html(_opp_b, _opp_b, team_name_map.get(_opp_b, "")),
                unsafe_allow_html=True,
            )
        else:
            st.markdown("<span class='muted'>Not projected for playoffs</span>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — SIMULATE
# ══════════════════════════════════════════════════════════════════════════════
with tab_sim:
    st.markdown("### 🎲 Monte Carlo Game Simulator")
    st.caption(
        "Runs 10,000 simulations using a blended team strength model "
        "(70% season average · 30% last-10 trend) + home ice advantage (+0.15 goals). "
        "Goals modelled with Poisson distribution."
    )

    sim_c1, sim_c2, sim_c3 = st.columns(3)
    with sim_c1:
        sim_a = st.selectbox("Team A", all_teams, index=0, key="sim_a")
    with sim_c2:
        sim_b = st.selectbox(
            "Team B",
            all_teams,
            index=1 if len(all_teams) > 1 else 0,
            key="sim_b",
        )
    with sim_c3:
        home_choice = st.radio("Home Team", [sim_a, sim_b], horizontal=True, key="sim_home")

    home_flag = "A" if home_choice == sim_a else "B"

    sim_ma = team_metrics_dict.get(sim_a, compute_team_metrics(sim_a, standings_df))
    sim_mb = team_metrics_dict.get(sim_b, compute_team_metrics(sim_b, standings_df))

    # Always run; button allows re-seeding
    if st.button("🔄 Re-run Simulation", type="secondary"):
        st.cache_data.clear()

    with st.spinner("Running 10,000 simulations…"):
        sim_res = monte_carlo_sim(sim_ma, sim_mb, home_team=home_flag, n_sims=10000)

    a_win = sim_res["a_win_pct"]
    b_win = sim_res["b_win_pct"]
    ot_pct = sim_res["ot_pct"]
    a_avg = sim_res["a_avg_goals"]
    b_avg = sim_res["b_avg_goals"]
    a_arr = sim_res["a_goals_arr"]
    b_arr = sim_res["b_goals_arr"]
    a_lam = sim_res["a_lambda"]
    b_lam = sim_res["b_lambda"]

    res_left, res_right = st.columns([2, 3])

    with res_left:
        # Team logos with home/away labels
        la_col, vs_col_s, lb_col = st.columns([2, 1, 2])
        with la_col:
            st.markdown(
                logo_card_html(sim_a, sim_a, "🏠 Home" if home_flag == "A" else "✈️ Away"),
                unsafe_allow_html=True,
            )
        with vs_col_s:
            st.markdown(
                "<div style='text-align:center;padding:18px 0;font-weight:800;font-size:1.1rem;'>VS</div>",
                unsafe_allow_html=True,
            )
        with lb_col:
            st.markdown(
                logo_card_html(sim_b, sim_b, "🏠 Home" if home_flag == "B" else "✈️ Away"),
                unsafe_allow_html=True,
            )

        st.markdown("---")
        st.markdown("**Win Probabilities**")
        st.markdown(prob_bar_html(f"{sim_a} wins", a_win, "#3b82f6"), unsafe_allow_html=True)
        st.markdown(prob_bar_html(f"{sim_b} wins", b_win, "#ef4444"), unsafe_allow_html=True)
        st.markdown(prob_bar_html("Goes to OT/SO", ot_pct, "#f59e0b"), unsafe_allow_html=True)

        st.markdown("---")
        proj_a_s = round(a_avg)
        proj_b_s = round(b_avg)
        st.markdown(f"**Projected Score:** `{sim_a} {proj_a_s} – {proj_b_s} {sim_b}`")

        a_lo = int(np.percentile(a_arr, 5))
        a_hi = int(np.percentile(a_arr, 95))
        b_lo = int(np.percentile(b_arr, 5))
        b_hi = int(np.percentile(b_arr, 95))
        st.markdown(
            f"**90% Confidence Range:** "
            f"{sim_a} {a_lo}–{a_hi} goals &nbsp;|&nbsp; {sim_b} {b_lo}–{b_hi} goals"
        )

        # Game script
        winner = sim_a if a_win >= b_win else sim_b
        win_pct_show = max(a_win, b_win)
        if ot_pct > 28:
            script = (
                f"Expect a tight battle. {winner} holds a {win_pct_show:.0f}% edge, "
                f"but {ot_pct:.0f}% of simulations go to overtime."
            )
        elif win_pct_show > 65:
            script = (
                f"{winner} is the clear favourite ({win_pct_show:.0f}%) "
                f"and projected to control this matchup throughout."
            )
        else:
            script = (
                f"Closely contested game. {winner} has a slight edge at {win_pct_show:.0f}%. "
                f"Either team can win on any given night."
            )
        st.info(f"**Most Likely Game Script:** {script}")

    with res_right:
        st.plotly_chart(
            plot_sim_histogram(a_arr, b_arr, sim_a, sim_b),
            width="stretch",
        )

        st.markdown("---")
        st.markdown("**Key Matchup Edges (Team A perspective)**")

        # Compute edges
        gf_edge = sim_ma["gf_per_game"] - sim_mb["gf_per_game"]
        ga_edge = sim_mb["ga_per_game"] - sim_ma["ga_per_game"]
        season_edge = (gf_edge + ga_edge) / 2

        l10_gf_edge = sim_ma["last10_gf_per_game"] - sim_mb["last10_gf_per_game"]
        l10_ga_edge = sim_mb["last10_ga_per_game"] - sim_ma["last10_ga_per_game"]
        l10_edge = (l10_gf_edge + l10_ga_edge) / 2

        home_edge_val = 0.15 if home_flag == "A" else -0.15
        lambda_edge = a_lam - b_lam

        edge_items = [
            ("Season Strength",     season_edge,    0.20, -0.20, True),
            ("Last 10 Momentum",    l10_edge,       0.20, -0.20, True),
            ("Home / Away",         home_edge_val,  0.10, -0.10, True),
            ("Expected Goals (λ)",  lambda_edge,    0.30, -0.30, True),
        ]

        for _elbl, _eval, _eg, _eb, _ehib in edge_items:
            try:
                _esl = stoplight(float(_eval), _eg, _eb, _ehib)
            except Exception:
                _esl = "⚪"
            _dir = "↑ A advantage" if _eval > 0.05 else "↓ B advantage" if _eval < -0.05 else "≈ Even"
            st.markdown(f"{_esl} **{_elbl}:** {_eval:+.3f} — *{_dir}*")

        with st.expander("ℹ️ Model Weighting Logic"):
            st.markdown(
                f"""
**Blended team strength (per team):**
- Season average: **70%** weight
- Last 10 games: **30%** weight

**Team A — {sim_a}**
| Metric | Season | Last 10 | Blended |
|---|---|---|---|
| GF/G | {sim_ma['gf_per_game']:.2f} | {sim_ma['last10_gf_per_game']:.2f} | {(0.7*sim_ma['gf_per_game']+0.3*sim_ma['last10_gf_per_game']):.2f} |
| GA/G | {sim_ma['ga_per_game']:.2f} | {sim_ma['last10_ga_per_game']:.2f} | {(0.7*sim_ma['ga_per_game']+0.3*sim_ma['last10_ga_per_game']):.2f} |

**Team B — {sim_b}**
| Metric | Season | Last 10 | Blended |
|---|---|---|---|
| GF/G | {sim_mb['gf_per_game']:.2f} | {sim_mb['last10_gf_per_game']:.2f} | {(0.7*sim_mb['gf_per_game']+0.3*sim_mb['last10_gf_per_game']):.2f} |
| GA/G | {sim_mb['ga_per_game']:.2f} | {sim_mb['last10_ga_per_game']:.2f} | {(0.7*sim_mb['ga_per_game']+0.3*sim_mb['last10_ga_per_game']):.2f} |

**Expected goals λ:** Team A = {a_lam:.3f} · Team B = {b_lam:.3f}

**Home ice advantage:** +0.15 goals added to home team's λ, −0.15 from away team.

**Simulation:** Poisson(λ) draws × 10,000. Tied games go to OT/SO (50/50 coin flip).
                """
            )
