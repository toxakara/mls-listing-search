from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Protocol

from app.listings.domain.filters import ListingFilter
from app.listings.domain.models import Listing
from app.listings.domain.ranking import RelevanceScore


class ListingsUnavailableError(Exception):
    """The storage can't be read right now: a missing or broken file, a database that is down.

    Unlike a bug, this is expected to pass, so the API tells the user to try again later.
    """


class ListingRepository(Protocol):
    """Storage behind the search. Swap JSON for a database or a search engine by implementing this."""

    def find(self, filters: ListingFilter) -> Iterable[Listing]:
        """Every listing that matches `filters`, in any order.

        Ranking, duplicate merging and paging are not the repository's job: pages must be cut
        after duplicates are merged, so the service needs the whole match set.

        Raises `ListingsUnavailableError` when the storage can't be read.
        """
        ...


class Ranking(Protocol):
    """Relevance formula behind the search. Swap or tune the scoring by implementing this."""

    def score(self, listing: Listing, target_budget: float | None, today: date) -> RelevanceScore:
        """Scores on a 0-100 scale. The service sorts by them and breaks ties itself."""
        ...
