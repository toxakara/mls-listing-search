"""Search use case: filter -> score -> merge duplicates -> take one page of the ranking."""

from __future__ import annotations

import heapq
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from math import ceil

from app.listings.application.ports import ListingRepository, Ranking
from app.listings.domain.cities import closest_city
from app.listings.domain.deduplication import PropertyKey, property_key
from app.listings.domain.filters import ALL_STATUSES, ListingFilter
from app.listings.domain.models import Listing
from app.listings.domain.ranking import RelevanceScore

DEFAULT_PAGE_SIZE = 6


class UnknownCityError(Exception):
    """No listing, whatever its status, is in a city matching the search: most likely a typo."""

    def __init__(self, city: str, suggestion: str | None) -> None:
        super().__init__(city)
        self.city = city
        # The known city this one most likely misspells, if any is close enough.
        self.suggestion = suggestion


@dataclass(frozen=True)
class SearchCriteria:
    """Search input, already validated at the HTTP boundary (`SearchQueryDTO`).

    `filters` decide which listings match and go to the repository; the budget and the page
    only shape the ranking and paging done here.
    """

    filters: ListingFilter = field(default_factory=ListingFilter)
    target_budget: float | None = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


@dataclass(frozen=True)
class RankedListing:
    listing: Listing
    score: RelevanceScore
    # The same property as reported by other feeds.
    duplicates: tuple[Listing, ...] = ()


@dataclass(frozen=True)
class SearchResult:
    items: tuple[RankedListing, ...]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        return ceil(self.total / self.page_size)


def utc_today() -> date:
    return datetime.now(UTC).date()


class ListingSearchService:
    """Ranks what the repository found, merges cross-feed duplicates and returns one page."""

    def __init__(
        self,
        repository: ListingRepository,
        ranking: Ranking,
        clock: Callable[[], date] = utc_today,
    ) -> None:
        self._repository = repository
        self._ranking = ranking
        # Injected so tests can score recency against a fixed date.
        self._clock = clock

    def search(self, criteria: SearchCriteria) -> SearchResult:
        """Valid filters that match nothing, or a page past the last one, give an empty page.

        Raises `UnknownCityError` when the city itself matches no listing at all.
        """
        today = self._clock()
        properties = _merge_duplicates(
            RankedListing(listing, self._ranking.score(listing, criteria.target_budget, today))
            for listing in self._repository.find(criteria.filters)
        )
        if not properties and criteria.filters.city:
            self._ensure_city_exists(criteria.filters.city)
        start = (criteria.page - 1) * criteria.page_size
        # Only the properties up to the end of this page need ordering, so a bounded heap
        # replaces sorting all of them: O(M log k) instead of O(M log M).
        ranked = heapq.nsmallest(start + criteria.page_size, properties, key=_rank_order)
        return SearchResult(
            items=tuple(ranked[start:]),
            total=len(properties),
            page=criteria.page,
            page_size=criteria.page_size,
        )

    def _ensure_city_exists(self, city: str) -> None:
        # Asked only when a search comes back empty, so a normal search pays nothing for it.
        anywhere_in_city = ListingFilter(city=city, statuses=ALL_STATUSES)
        if next(iter(self._repository.find(anywhere_in_city)), None) is None:
            raise UnknownCityError(city, suggestion=self._closest_known_city(city))

    def _closest_known_city(self, city: str) -> str | None:
        every_listing = ListingFilter(statuses=ALL_STATUSES)
        return closest_city(city, {listing.city for listing in self._repository.find(every_listing)})


def _rank_order(item: RankedListing) -> tuple[float, int, str, str]:
    """Best score first; ties go to the newer listing, then to (source, id) so order is stable."""
    listing = item.listing
    return (-item.score.relevance, -listing.listed_date.toordinal(), listing.source, listing.id)


def _merge_duplicates(scored: Iterable[RankedListing]) -> list[RankedListing]:
    """One entry per property, in no particular order: its best-ranked record, others attached.

    Ranking properties by their best record afterwards gives the same order as ranking every
    record first and keeping the first one seen for each property.
    """
    groups: defaultdict[PropertyKey, list[RankedListing]] = defaultdict(list)
    for item in scored:
        groups[property_key(item.listing)].append(item)
    return [_best_of(group) for group in groups.values()]


def _best_of(group: list[RankedListing]) -> RankedListing:
    # A group holds about one record per feed, so sorting it costs next to nothing.
    best, *others = sorted(group, key=_rank_order)
    return replace(best, duplicates=tuple(other.listing for other in others))
