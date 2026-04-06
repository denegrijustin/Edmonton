"""Playoff series and full-bracket Monte Carlo simulator."""

import math
import random
from typing import Any, Dict, List, Optional, Tuple

from models.season_sim import compute_win_probability


def simulate_series(
    team_a: str,
    team_b: str,
    metrics_dict: Dict[str, Any],
    wins_a: int = 0,
    wins_b: int = 0,
    games_to_win: int = 4,
    n_sims: int = 1000,
    home_sequence: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Simulate the remainder of a best-of series.

    The standard NHL home-ice schedule for a 7-game series is::

        Game 1: A home, Game 2: A home, Game 3: B home, Game 4: B home,
        Game 5: A home, Game 6: B home, Game 7: A home

    Parameters
    ----------
    team_a, team_b : str
        Team abbreviations. *team_a* is the higher seed (home-ice advantage).
    metrics_dict : dict
        Keyed by team abbreviation; each value is a metrics dict compatible
        with :func:`models.season_sim.compute_win_probability`.
    wins_a, wins_b : int
        Current wins in the series for each team.
    games_to_win : int
        Wins required to clinch (default 4 for best-of-7).
    n_sims : int
        Number of simulation iterations.
    home_sequence : list of str, optional
        Override the home-team sequence. Defaults to the standard NHL 2-2-1-1-1
        pattern with team_a as the home team.

    Returns
    -------
    dict with keys:
        ``team_a_wins_prob`` (float 0-1),
        ``team_b_wins_prob`` (float 0-1),
        ``most_likely_length`` (int, total games in series),
        ``games_remaining_avg`` (float).
    """
    if home_sequence is None:
        # Standard NHL 2-2-1-1-1: A, A, B, B, A, B, A
        home_sequence = [team_a, team_a, team_b, team_b, team_a, team_b, team_a]

    ma = metrics_dict.get(team_a, {})
    mb = metrics_dict.get(team_b, {})

    a_wins_total = 0
    total_games_played = 0
    length_counts: Dict[int, int] = {}
    rng = random.Random()

    for _ in range(n_sims):
        wa, wb = wins_a, wins_b
        game_num = wa + wb  # 0-indexed position in series (already played)

        while wa < games_to_win and wb < games_to_win:
            home_idx = min(game_num, len(home_sequence) - 1)
            home = home_sequence[home_idx]
            home_arg = "a" if home == team_a else "b"
            wp_a = compute_win_probability(ma, mb, home=home_arg)

            if rng.random() < wp_a:
                wa += 1
            else:
                wb += 1
            game_num += 1

        series_length = game_num
        if wa == games_to_win:
            a_wins_total += 1
        total_games_played += series_length
        length_counts[series_length] = length_counts.get(series_length, 0) + 1

    team_a_wins_prob = a_wins_total / n_sims
    most_likely_length = max(length_counts, key=length_counts.get) if length_counts else wins_a + wins_b
    avg_remaining = (total_games_played / n_sims) - (wins_a + wins_b)

    return {
        "team_a_wins_prob": round(team_a_wins_prob, 4),
        "team_b_wins_prob": round(1.0 - team_a_wins_prob, 4),
        "most_likely_length": most_likely_length,
        "games_remaining_avg": round(avg_remaining, 1),
    }


def simulate_full_bracket(
    series_list: List[Dict[str, Any]],
    team_metrics_dict: Dict[str, Any],
    n_sims: int = 1000,
) -> Dict[str, Dict[str, float]]:
    """Simulate every remaining round in the playoff bracket.

    Parameters
    ----------
    series_list : list of dict
        Each dict should have keys compatible with
        :func:`providers.playoff_provider.get_playoff_series_list`:
        ``topSeed``, ``bottomSeed``, ``topSeedWins``, ``bottomSeedWins``,
        ``round``.
    team_metrics_dict : dict
        Team metrics keyed by abbreviation.
    n_sims : int
        Simulation iterations.

    Returns
    -------
    dict of team → {cup_odds, conf_finals_odds, finals_odds, next_round_odds}
        All values are floats in [0, 100].
    """
    if not series_list:
        return {}

    all_teams = set()
    for s in series_list:
        all_teams.add(s.get("topSeed", ""))
        all_teams.add(s.get("bottomSeed", ""))
    all_teams.discard("")

    # Counters
    cup_wins: Dict[str, int] = {t: 0 for t in all_teams}
    conf_finals: Dict[str, int] = {t: 0 for t in all_teams}
    finals: Dict[str, int] = {t: 0 for t in all_teams}
    next_round: Dict[str, int] = {t: 0 for t in all_teams}

    # Group series by round
    rounds: Dict[int, List[Dict[str, Any]]] = {}
    for s in series_list:
        r = s.get("round", 1)
        rounds.setdefault(r, []).append(s)

    max_round = max(rounds.keys()) if rounds else 1
    games_to_win = 4  # best-of-7

    rng = random.Random()

    for _ in range(n_sims):
        # Track survivors: round → list of winners
        active_series = {r: [dict(s) for s in series_list if s.get("round") == r]
                         for r in rounds}
        winners_by_round: Dict[int, List[str]] = {}
        bracket_winners: Dict[str, List[str]] = {}  # conf → winner list

        for rnd in sorted(rounds.keys()):
            round_winners: List[str] = []
            for s in active_series.get(rnd, []):
                ta = s.get("topSeed", "")
                tb = s.get("bottomSeed", "")
                wa = int(s.get("topSeedWins", 0))
                wb = int(s.get("bottomSeedWins", 0))

                if not ta or not tb:
                    continue

                ma = team_metrics_dict.get(ta, {})
                mb = team_metrics_dict.get(tb, {})

                # Quick series simulation (no full n_sims recursion)
                while wa < games_to_win and wb < games_to_win:
                    wp_a = compute_win_probability(ma, mb, home="a")
                    if rng.random() < wp_a:
                        wa += 1
                    else:
                        wb += 1

                winner = ta if wa == games_to_win else tb
                round_winners.append(winner)

            winners_by_round[rnd] = round_winners

        # Determine conference finals, finals, cup
        all_round_winners = [w for rnd, wlist in winners_by_round.items() for w in wlist]
        for rnd in sorted(rounds.keys()):
            wlist = winners_by_round.get(rnd, [])
            if rnd == 3:  # Conference finals
                for w in wlist:
                    if w in conf_finals:
                        conf_finals[w] += 1
            if rnd == 4:  # Stanley Cup Finals appearance
                for w in wlist:
                    if w in finals:
                        finals[w] += 1

        # Cup winner: last surviving team from last round
        last_round = max(winners_by_round.keys()) if winners_by_round else None
        if last_round:
            for w in winners_by_round[last_round]:
                if w in cup_wins:
                    cup_wins[w] += 1

        # Next round = advancing beyond round 1
        for rnd in sorted(rounds.keys()):
            if rnd > min(rounds.keys()):
                for w in winners_by_round.get(rnd, []):
                    if w in next_round:
                        next_round[w] += 1

    scale = 100.0 / n_sims
    return {
        t: {
            "cup_odds": round(cup_wins[t] * scale, 1),
            "conf_finals_odds": round(conf_finals[t] * scale, 1),
            "finals_odds": round(finals[t] * scale, 1),
            "next_round_odds": round(next_round[t] * scale, 1),
        }
        for t in all_teams
    }
