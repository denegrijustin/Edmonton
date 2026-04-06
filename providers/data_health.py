"""Data health tracking — source status, last refresh, missing fields, fallback mode."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class DataHealth:
    """Tracks data source health for the data health panel."""

    def __init__(self) -> None:
        self._sources: dict[str, dict[str, Any]] = {}
        self._warnings: list[str] = []

    def record(self, source: str, ok: bool, *, error: str | None = None, fields_missing: list[str] | None = None) -> None:
        self._sources[source] = {
            "ok": ok,
            "last_refresh": datetime.now(timezone.utc).isoformat(),
            "error": error,
            "fields_missing": fields_missing or [],
            "fallback": not ok,
        }
        if not ok:
            self._warnings.append(f"{source}: {error or 'unavailable'}")

    @property
    def sources(self) -> dict[str, dict[str, Any]]:
        return dict(self._sources)

    @property
    def warnings(self) -> list[str]:
        return list(self._warnings)

    @property
    def degraded(self) -> bool:
        return any(not s["ok"] for s in self._sources.values())

    def summary_rows(self) -> list[dict[str, Any]]:
        rows = []
        for name, info in self._sources.items():
            rows.append({
                "Source": name,
                "Status": "✅ OK" if info["ok"] else "❌ Down",
                "Last Refresh": info["last_refresh"],
                "Missing Fields": ", ".join(info["fields_missing"]) if info["fields_missing"] else "—",
                "Fallback": "Yes" if info["fallback"] else "No",
            })
        return rows
