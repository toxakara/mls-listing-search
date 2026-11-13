"""What every ListingRepository must do with a ListingFilter.

A new storage (Postgres, Elasticsearch, ...) is added to REPOSITORIES below and must pass the same tests,
so switching storage cannot change which listings a search returns.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from itertools import combinations
from typing import Any

import pytest

from app.listings.application.ports import ListingRepository
from app.listings.domain.filters import ListingFilter, keyword_tokens, matches_keyword
from app.listings.domain.models import Listing, ListingStatus
from app.listings.infrastructure.in_memory_repository import InMemoryListingRepository, load_listings

SAMPLE = load_listings()
ALL_STATUSES: frozenset[ListingStatus] = frozenset({"active", "pending", "sold"})

REPOSITORIES: dict[str, Callable[[Iterable[Listing]], ListingRepository]] = {
    "in-memory": InMemoryListingRepository,
}


@pytest.fixture(params=sorted(REPOSITORIES))
def repository(request: pytest.FixtureRequest) -> ListingRepository:
    return REPOSITORIES[request.param](SAMPLE)


def found(repository: ListingRepository, filters: ListingFilter) -> set[str]:
    return {listing.id for listing in repository.find(filters)}


def test_no_constraints_returns_every_listing_with_a_selected_status(repository: ListingRepository) -> None:
    assert found(repository, ListingFilter(statuses=ALL_STATUSES)) == {listing.id for listing in SAMPLE}


def test_status_defaults_to_active(repository: ListingRepository) -> None:
    assert "A7" not in found(repository, ListingFilter())  # A7 is pending
    assert found(repository, ListingFilter(statuses=frozenset({"pending"}))) == {"A7"}


def test_price_and_bedroom_bounds_are_inclusive(repository: ListingRepository) -> None:
    assert found(repository, ListingFilter(min_price=450000, max_price=450000)) == {"A1"}
    assert found(repository, ListingFilter(min_bedrooms=4, statuses=ALL_STATUSES)) == {"A4", "A7"}


def test_city_is_a_trimmed_case_insensitive_substring(repository: ListingRepository) -> None:
    assert found(repository, ListingFilter(city="  sPrInG ")) == {"A1", "B7", "A2", "B8"}


def test_keyword_searches_the_description_only(repository: ListingRepository) -> None:
    assert found(repository, ListingFilter(keyword="Springfield")) == set()
    assert found(repository, ListingFilter(keyword="  METRO ")) == {"A5", "B11"}


def test_a_plural_keyword_finds_the_singular(repository: ListingRepository) -> None:
    assert found(repository, ListingFilter(keyword="pets", statuses=ALL_STATUSES)) == found(
        repository, ListingFilter(keyword="pet", statuses=ALL_STATUSES)
    )
    assert found(repository, ListingFilter(keyword="garages")) == {"B10"}
    assert found(repository, ListingFilter(keyword="kitchens")) == {"A2", "B8"}


def test_filters_are_combined_with_and(repository: ListingRepository) -> None:
    filters = ListingFilter(min_price=440000, max_price=530000, min_bedrooms=3, city="spring")
    assert found(repository, filters) == {"A2", "B8"}


# One value per filter and the listings it matches on its own, read off the sample file by hand.
SINGLE_FILTERS: dict[str, tuple[Any, set[str]]] = {
    "min_price": (450000, {"A1", "B7", "A2", "B8", "A4", "B10", "A5", "B11", "A7"}),
    "max_price": (530000, {"A1", "B7", "A2", "B8", "A3", "B9", "A5", "B11", "A6"}),
    "min_bedrooms": (3, {"A2", "B8", "A4", "B10", "A5", "B11", "A6", "A7"}),
    "city": ("spring", {"A1", "B7", "A2", "B8"}),
    "keyword": ("pet", {"A1", "B7", "A3", "B9", "A4", "A5", "B11", "A6", "A7"}),
    "statuses": (frozenset({"active"}), {listing.id for listing in SAMPLE} - {"A7"}),
}
FILTER_COMBINATIONS = [
    names for size in range(len(SINGLE_FILTERS) + 1) for names in combinations(SINGLE_FILTERS, size)
]


@pytest.mark.parametrize("names", FILTER_COMBINATIONS, ids=lambda names: "+".join(names) or "none")
def test_any_set_of_filters_matches_what_each_filter_matches_alone(
    repository: ListingRepository, names: tuple[str, ...]
) -> None:
    """All 64 subsets of the six filters, from none to all of them.

    The expected result is the intersection of the hand-written single-filter results, so it
    does not depend on the code under test.
    """
    chosen = {name: SINGLE_FILTERS[name][0] for name in names}
    expected = {listing.id for listing in SAMPLE}
    for name in names:
        expected &= SINGLE_FILTERS[name][1]
    assert found(repository, ListingFilter(**{"statuses": ALL_STATUSES, **chosen})) == expected


@pytest.mark.parametrize(
    "filters",
    [
        ListingFilter(min_price=10_000_000),
        ListingFilter(max_price=0),
        ListingFilter(min_price=1e308),
        ListingFilter(min_bedrooms=99),
        ListingFilter(city="Atlantis"),
        ListingFilter(keyword="helipad"),
        ListingFilter(keyword="pet helipad"),
        ListingFilter(statuses=frozenset({"sold"})),
        ListingFilter(statuses=frozenset()),
    ],
)
def test_values_that_match_nothing_give_an_empty_result(
    repository: ListingRepository, filters: ListingFilter
) -> None:
    assert found(repository, filters) == set()


@pytest.mark.parametrize(
    "filters",
    [
        ListingFilter(min_price=0),
        ListingFilter(max_price=1e308),
        ListingFilter(min_bedrooms=0),
        ListingFilter(city=""),
        ListingFilter(city="   "),
        ListingFilter(keyword=""),
        # No letters or digits means no words to look for.
        ListingFilter(keyword="!!! -- %"),
    ],
)
def test_values_that_constrain_nothing_match_every_active_listing(
    repository: ListingRepository, filters: ListingFilter
) -> None:
    assert found(repository, filters) == found(repository, ListingFilter())


@pytest.mark.parametrize(
    "description,keyword,expected",
    [
        ("Pet friendly condo", "pet", True),
        ("Pets allowed", "pet", True),
        ("New carpet throughout", "pet", False),
        ("Fenced yard, pets allowed", "allowed pets", True),
        ("Fenced yard, pets allowed", "pets pool", False),
        ("Anything", "   ", True),
        # Plurals fold onto the singular on both sides.
        ("Pet friendly condo", "pets", True),
        ("New carpet throughout", "pets", False),
        ("Townhome with 2-car garage", "garages", True),
        ("Community amenity center", "amenities", True),
        ("All amenities included", "amenity", True),
        ("Covered porch", "porches", True),
        ("Glass doors", "glasses", True),
        ("Access to the pool", "access", True),
        # A singular finds its plural even where folding changes the plural's stem.
        ("Home theater for movies", "movie", True),
        ("Built-in reading niches", "niche", True),
        ("Close to city buses", "bus", True),
        ("Utilities included", "utility", True),
    ],
)
def test_keyword_tokens_match_word_prefixes(description: str, keyword: str, expected: bool) -> None:
    assert matches_keyword(description, keyword_tokens(keyword)) is expected
