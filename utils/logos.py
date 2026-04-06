"""Team logo URL helpers."""


def logo_url(abbrev: str) -> str:
    """Return the NHL CDN SVG logo URL for a team abbreviation."""
    return f"https://assets.nhle.com/logos/nhl/svg/{abbrev}_light.svg"
