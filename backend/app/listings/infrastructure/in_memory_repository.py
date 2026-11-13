from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path

from pydantic import TypeAdapter

from app.listings.application.ports import ListingsUnavailableError
from app.listings.domain.filters import ListingFilter
from app.listings.domain.models import Listing

DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "sample_listings.json"


def load_listings(path: Path = DATA_PATH) -> tuple[Listing, ...]:
    """Reads and validates a feed file; one bad record rejects the whole file."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    listings = tuple(TypeAdapter(list[Listing]).validate_python(raw))
    if len({(listing.source, listing.id) for listing in listings}) != len(listings):
        raise ValueError("Dataset contains duplicate (source, id) keys")
    return listings


class InMemoryListingRepository:
    """Keeps every listing in memory and filters in Python. Right for a file of this size."""

    def __init__(self, listings: Iterable[Listing]) -> None:
        self._listings = tuple(listings)

    def find(self, filters: ListingFilter) -> Iterator[Listing]:
        return (listing for listing in self._listings if filters.matches(listing))


class JsonFileListingRepository:
    """Listings from a feed file, read on the first search and then kept in memory.

    A missing or broken file doesn't stop the app: searches raise `ListingsUnavailableError`, and
    each one reads the file again, so the API recovers on its own once the file is fixed.
    """

    def __init__(self, path: Path = DATA_PATH) -> None:
        self._path = path
        self._loaded: InMemoryListingRepository | None = None

    def find(self, filters: ListingFilter) -> Iterator[Listing]:
        return self._repository().find(filters)

    def _repository(self) -> InMemoryListingRepository:
        # Two first searches at once may both read the file; both get the same data, so that's harmless.
        if self._loaded is None:
            try:
                self._loaded = InMemoryListingRepository(load_listings(self._path))
            except (OSError, ValueError) as error:
                # ValueError covers broken JSON, a record that fails validation and duplicate keys.
                raise ListingsUnavailableError(f"Cannot read {self._path}: {error}") from error
        return self._loaded
