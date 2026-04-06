"""NHL Web API provider with caching, retries, rate-limit handling, and fallback."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests
import streamlit as st

from config.settings import (
    CACHE_TTL,
    HTTP_RETRIES,
    HTTP_RETRY_DELAY,
    HTTP_TIMEOUT,
    NHL_API_BASE,
    SEASON,
)
from utils.helpers import first_non_null, flatten_dict, safe_get, parse_mmss


class NHLApiProvider:
    """Adapter for the public NHL Web API."""

    def __init__(self) -> None:
        self.base = NHL_API_BASE
        self.timeout = HTTP_TIMEOUT
        self.retries = HTTP_RETRIES
        self.retry_delay = HTTP_RETRY_DELAY
        self._health: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------
    def _get_json(self, url: str) -> dict[str, Any]:
        """Fetch JSON with retries and health tracking."""
        last_exc: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                r = requests.get(url, timeout=self.timeout)
                r.raise_for_status()
                self._record_health(url, True)
                return r.json()
            except Exception as exc:
                last_exc = exc
                self._record_health(url, False, str(exc))
                if attempt < self.retries:
                    time.sleep(self.retry_delay * attempt)
        raise last_exc  # type: ignore[misc]

    def _record_health(self, url: str, ok: bool, error: str | None = None) -> None:
        key = url.split("/v1/")[-1].split("/")[0] if "/v1/" in url else url
        self._health[key] = {
            "ok": ok,
            "last_check": datetime.now(timezone.utc).isoformat(),
            "error": error,
        }

    @property
    def health(self) -> dict[str, dict]:
        return dict(self._health)

    # ------------------------------------------------------------------
    # Standings (league-wide, all 32 teams)
    # ------------------------------------------------------------------
    @staticmethod
    @st.cache_data(ttl=CACHE_TTL, show_spinner=False)
    def _fetch_standings() -> list[dict]:
        """Raw standings fetch — cached."""
        provider = NHLApiProvider()
        data = provider._get_json(f"{provider.base}/standings/now")
        raw = data.get("standings", data if isinstance(data, list) else [])
        rows: list[dict] = []
        for team in raw:
            flat = flatten_dict(team)
            rows.append({
                "teamName": first_non_null(flat, ["teamName.default", "teamCommonName.default", "teamAbbrev.default", "teamName"]),
                "teamAbbrev": first_non_null(flat, ["teamAbbrev.default", "teamAbbrev", "abbrev"]),
                "conference": first_non_null(flat, ["conferenceName", "conferenceAbbrev"]),
                "division": first_non_null(flat, ["divisionName", "divisionAbbrev"]),
                "gamesPlayed": first_non_null(flat, ["gamesPlayed"], 0),
                "points": first_non_null(flat, ["points"], 0),
                "wins": first_non_null(flat, ["wins"], 0),
                "losses": first_non_null(flat, ["losses"], 0),
                "otLosses": first_non_null(flat, ["otLosses"], 0),
                "regulationWins": first_non_null(flat, ["regulationWins"], 0),
                "goalDifferential": first_non_null(flat, ["goalDifferential"], 0),
                "goalsFor": first_non_null(flat, ["goalFor"], 0),
                "goalsAgainst": first_non_null(flat, ["goalAgainst"], 0),
                "pointPctg": first_non_null(flat, ["pointPctg", "pointsPctg"], 0.0),
                "conferenceSequence": first_non_null(flat, ["conferenceSequence"]),
                "divisionSequence": first_non_null(flat, ["divisionSequence"]),
                "wildcardSequence": first_non_null(flat, ["wildcardSequence"]),
                "streakCode": first_non_null(flat, ["streakCode"], ""),
                "streakCount": first_non_null(flat, ["streakCount"], 0),
                "homeWins": first_non_null(flat, ["homeWins"], 0),
                "homeLosses": first_non_null(flat, ["homeLosses"], 0),
                "homeOtLosses": first_non_null(flat, ["homeOtLosses"], 0),
                "roadWins": first_non_null(flat, ["roadWins"], 0),
                "roadLosses": first_non_null(flat, ["roadLosses"], 0),
                "roadOtLosses": first_non_null(flat, ["roadOtLosses"], 0),
                "l10Wins": first_non_null(flat, ["l10Wins"], 0),
                "l10Losses": first_non_null(flat, ["l10Losses"], 0),
                "l10OtLosses": first_non_null(flat, ["l10OtLosses"], 0),
            })
        return rows

    def get_standings(self) -> pd.DataFrame:
        rows = self._fetch_standings()
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Schedule (per team)
    # ------------------------------------------------------------------
    @staticmethod
    @st.cache_data(ttl=CACHE_TTL, show_spinner=False)
    def _fetch_schedule(team: str, season: str) -> list[dict]:
        provider = NHLApiProvider()
        data = provider._get_json(f"{provider.base}/club-schedule-season/{team}/{season}")
        games: list[dict] = []
        containers: list[list] = []
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
                period_type = first_non_null(flat, ["periodDescriptor.periodType", "gameOutcome.lastPeriodType"])
                if game_id:
                    games.append({
                        "gameId": int(game_id),
                        "gameDate": str(game_date),
                        "awayTeam": away,
                        "homeTeam": home,
                        "awayScore": away_score,
                        "homeScore": home_score,
                        "gameState": game_state,
                        "gameType": game_type,
                        "periodType": period_type,
                        "isCompleted": game_state in {"OFF", "FINAL", "OVER", "DONE"}
                        or (away_score is not None and home_score is not None),
                    })
        return games

    def get_schedule(self, team: str, season: str = SEASON) -> pd.DataFrame:
        rows = self._fetch_schedule(team, season)
        df = pd.DataFrame(rows).drop_duplicates(subset=["gameId"])
        if df.empty:
            return df
        df["gameDate"] = pd.to_datetime(df["gameDate"], errors="coerce")
        return df.sort_values(["gameDate", "gameId"]).reset_index(drop=True)

    # ------------------------------------------------------------------
    # Roster
    # ------------------------------------------------------------------
    @staticmethod
    @st.cache_data(ttl=CACHE_TTL, show_spinner=False)
    def _fetch_roster(team: str, season: str) -> list[dict]:
        provider = NHLApiProvider()
        data = provider._get_json(f"{provider.base}/roster/{team}/{season}")
        rows: list[dict] = []
        mapping = {"forwards": "F", "defensemen": "D", "goalies": "G"}
        for sec, pos in mapping.items():
            for p in data.get(sec, []) or []:
                rows.append({
                    "playerId": p.get("id") or p.get("playerId"),
                    "playerName": " ".join(
                        x for x in [safe_get(p, ["firstName", "default"]), safe_get(p, ["lastName", "default"])] if x
                    ).strip(),
                    "position": pos,
                    "sweaterNumber": p.get("sweaterNumber"),
                    "headshot": safe_get(p, ["headshot"]),
                })
        return rows

    def get_roster(self, team: str, season: str = SEASON) -> pd.DataFrame:
        rows = self._fetch_roster(team, season)
        return pd.DataFrame(rows).drop_duplicates(subset=["playerId", "playerName"])

    # ------------------------------------------------------------------
    # Boxscore + Play-by-Play
    # ------------------------------------------------------------------
    @staticmethod
    @st.cache_data(ttl=CACHE_TTL, show_spinner=False)
    def _fetch_boxscore(game_id: int) -> dict:
        provider = NHLApiProvider()
        return provider._get_json(f"{provider.base}/gamecenter/{game_id}/boxscore")

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL, show_spinner=False)
    def _fetch_play_by_play(game_id: int) -> dict:
        provider = NHLApiProvider()
        return provider._get_json(f"{provider.base}/gamecenter/{game_id}/play-by-play")

    def get_boxscore(self, game_id: int) -> dict[str, Any]:
        return self._fetch_boxscore(game_id)

    def get_play_by_play(self, game_id: int) -> dict[str, Any]:
        return self._fetch_play_by_play(game_id)

    # ------------------------------------------------------------------
    # Extract team game stats from boxscore
    # ------------------------------------------------------------------
    def extract_team_game(self, game_row: pd.Series, box: dict, team_abbrev: str) -> dict[str, Any]:
        flat = flatten_dict(box)
        away_score = first_non_null(flat, ["awayTeam.score"], game_row.get("awayScore"))
        home_score = first_non_null(flat, ["homeTeam.score"], game_row.get("homeScore"))
        away_shots = first_non_null(flat, ["awayTeam.sog", "awayTeam.shotsOnGoal", "awayTeam.teamStats.shotsOnGoal"])
        home_shots = first_non_null(flat, ["homeTeam.sog", "homeTeam.shotsOnGoal", "homeTeam.teamStats.shotsOnGoal"])
        away_faceoff = first_non_null(flat, ["awayTeam.faceoffWinningPctg", "awayTeam.teamStats.faceoffWinningPctg"])
        home_faceoff = first_non_null(flat, ["homeTeam.faceoffWinningPctg", "homeTeam.teamStats.faceoffWinningPctg"])
        away_pp = first_non_null(flat, ["awayTeam.powerPlayConversion", "awayTeam.teamStats.powerPlayConversion"])
        home_pp = first_non_null(flat, ["homeTeam.powerPlayConversion", "homeTeam.teamStats.powerPlayConversion"])

        is_home = game_row["homeTeam"] == team_abbrev
        team_score = home_score if is_home else away_score
        opp_score = away_score if is_home else home_score

        period_type = game_row.get("periodType")
        if team_score is not None and opp_score is not None:
            if team_score > opp_score:
                result = "W"
            elif period_type and str(period_type).upper() in ("OT", "SO"):
                result = "OTL"
            else:
                result = "L"
        else:
            result = "L"

        opp_abbrev = game_row["awayTeam"] if is_home else game_row["homeTeam"]

        return {
            "gameId": int(game_row["gameId"]),
            "gameDate": game_row["gameDate"],
            "gameType": game_row.get("gameType"),
            "venue": "Home" if is_home else "Away",
            "opponent": opp_abbrev,
            "teamScore": team_score,
            "oppScore": opp_score,
            "result": result,
            "goalDiff": (team_score or 0) - (opp_score or 0),
            "teamShots": home_shots if is_home else away_shots,
            "oppShots": away_shots if is_home else home_shots,
            "shotDiff": self._shot_diff(is_home, home_shots, away_shots),
            "teamFaceoffPct": home_faceoff if is_home else away_faceoff,
            "teamPowerPlay": home_pp if is_home else away_pp,
            "periodType": period_type,
        }

    @staticmethod
    def _shot_diff(is_home: bool, home_shots: Any, away_shots: Any) -> float:
        import numpy as np
        if home_shots is not None and away_shots is not None:
            return (home_shots - away_shots) if is_home else (away_shots - home_shots)
        return np.nan

    # ------------------------------------------------------------------
    # Extract player game stats from boxscore
    # ------------------------------------------------------------------
    def extract_player_games(
        self, game_row: pd.Series, box: dict, roster_df: pd.DataFrame, team_abbrev: str,
    ) -> pd.DataFrame:
        import numpy as np

        roster_ids = set(roster_df["playerId"].dropna().astype(int).tolist()) if not roster_df.empty else set()
        roster_names = set(roster_df["playerName"].dropna().tolist()) if not roster_df.empty else set()
        rows: list[dict] = []
        pbg = box.get("playerByGameStats", {}) if isinstance(box, dict) else {}
        for side in ["awayTeam", "homeTeam"]:
            for group in ["forwards", "defense", "goalies"]:
                arr = safe_get(pbg, [side, group], [])
                if not isinstance(arr, list) or not arr:
                    continue
                side_abbrev = game_row["awayTeam"] if side == "awayTeam" else game_row["homeTeam"]
                for p in arr:
                    flat = flatten_dict(p)
                    pid = first_non_null(flat, ["playerId", "id"])
                    fn = first_non_null(flat, ["firstName.default", "firstName"])
                    ln = first_non_null(flat, ["lastName.default", "lastName"])
                    name = first_non_null(flat, ["name.default", "fullName"], " ".join(x for x in [fn, ln] if x).strip())
                    if side_abbrev != team_abbrev and pid not in roster_ids and name not in roster_names:
                        continue
                    rows.append({
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
                        "pim": first_non_null(flat, ["pim", "penaltyMinutes"], 0),
                        "toi": first_non_null(flat, ["toi", "timeOnIce"]),
                        "ppToi": first_non_null(flat, ["powerPlayToi", "ppToi"]),
                        "shToi": first_non_null(flat, ["shorthandedToi", "shToi"]),
                        "evToi": first_non_null(flat, ["evenStrengthToi", "evToi"]),
                        "saves": first_non_null(flat, ["saves"]),
                        "goalsAgainst": first_non_null(flat, ["goalsAgainst"]),
                        "shotsAgainst": first_non_null(flat, ["shotsAgainst"]),
                    })
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        num_cols = ["goals", "assists", "points", "plusMinus", "shots", "hits",
                    "blockedShots", "giveaways", "takeaways", "faceoffWins",
                    "faceoffTaken", "saves", "goalsAgainst", "shotsAgainst", "pim"]
        for col in num_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        for col in ["toi", "ppToi", "shToi", "evToi"]:
            df[f"{col}_min"] = df[col].apply(parse_mmss)
        return df

    # ------------------------------------------------------------------
    # Extract shot/goal events from play-by-play
    # ------------------------------------------------------------------
    def extract_shot_events(self, schedule_df: pd.DataFrame, team_abbrev: str) -> pd.DataFrame:
        events_out: list[dict] = []
        completed = schedule_df[schedule_df["isCompleted"]]
        for _, g in completed.iterrows():
            try:
                pbp = self.get_play_by_play(int(g["gameId"]))
            except Exception:
                continue
            plays = pbp.get("plays", pbp.get("gameEvents", [])) if isinstance(pbp, dict) else []
            if not isinstance(plays, list):
                continue
            for ev in plays:
                flat = flatten_dict(ev)
                event_type = str(first_non_null(flat, ["typeDescKey", "eventType", "typeCode"], "")).lower()
                if not any(t in event_type for t in ["shot", "goal", "miss", "block"]):
                    continue
                x = pd.to_numeric(first_non_null(flat, ["details.xCoord", "xCoord", "x"]), errors="coerce")
                y = pd.to_numeric(first_non_null(flat, ["details.yCoord", "yCoord", "y"]), errors="coerce")
                shooting_team = first_non_null(flat, ["details.eventOwnerTeamAbbrev", "teamAbbrev"])
                strength = first_non_null(flat, ["details.strength", "situationCode", "details.situationCode"])
                events_out.append({
                    "gameId": int(g["gameId"]),
                    "gameDate": g["gameDate"],
                    "venue": "Home" if g["homeTeam"] == team_abbrev else "Away",
                    "x": x,
                    "y": y,
                    "isTeamShot": shooting_team == team_abbrev,
                    "strength": str(strength) if strength else "",
                    "zone": classify_zone(x, y),
                    "eventType": event_type,
                    "shootingTeam": shooting_team,
                })
        return pd.DataFrame(events_out)
