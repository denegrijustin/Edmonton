"""Internal playoff odds and consensus odds provider."""

from typing import Any, Dict, List, Optional

from utils.validators import validate_probability


def compute_consensus_odds(
    internal_odds: float,
    external_sources: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Merge internal and external playoff odds into a consensus view.

    Parameters
    ----------
    internal_odds : float
        Internal model playoff probability (0-100).
    external_sources : list of dict
        Each dict must have ``"source"`` (str), ``"odds"`` (float 0-100),
        and optionally ``"fresh"`` (bool).

    Returns
    -------
    dict with keys: consensus_odds, spread, sources, n_sources
    """
    valid_odds: List[float] = []

    internal_val = validate_probability(internal_odds)
    if internal_val is not None:
        valid_odds.append(internal_val)

    source_details: List[Dict[str, Any]] = [
        {"source": "Internal Model", "odds": internal_val, "fresh": True}
    ]

    for src in external_sources:
        val = validate_probability(src.get("odds"))
        if val is not None:
            valid_odds.append(val)
            source_details.append(
                {
                    "source": src.get("source", "Unknown"),
                    "odds": val,
                    "fresh": src.get("fresh", True),
                }
            )

    if not valid_odds:
        return {"consensus_odds": None, "spread": 0, "sources": source_details, "n_sources": 0}

    consensus = sum(valid_odds) / len(valid_odds)
    spread = max(valid_odds) - min(valid_odds)
    return {
        "consensus_odds": round(consensus, 1),
        "spread": round(spread, 1),
        "sources": source_details,
        "n_sources": len(valid_odds),
    }
