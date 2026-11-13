"""Telling a misspelled city from one that no listing is in."""

from __future__ import annotations

from collections.abc import Iterable
from difflib import get_close_matches

# Typos of the sample cities score 0.91 or more; unrelated names like "Atlantis" score 0.5 or less.
_SIMILARITY_CUTOFF = 0.75


def closest_city(city: str, known_cities: Iterable[str]) -> str | None:
    """The known city that `city` most likely misspells, or None when no city is close enough."""
    by_key = {known.strip().casefold(): known.strip() for known in known_cities}
    matches = get_close_matches(city.strip().casefold(), by_key, n=1, cutoff=_SIMILARITY_CUTOFF)
    return by_key[matches[0]] if matches else None
