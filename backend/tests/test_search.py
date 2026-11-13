"""Unit tests for the search use case: fixed date, in-memory repository, no HTTP.

Which listings a filter matches is covered by test_repository_contract.py.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterable
from datetime import date
from pathlib import Path

import pytest

from app.listings.application.ports import ListingsUnavailableError
from app.listings.application.search import (
    ListingSearchService,
    SearchCriteria,
    SearchResult,
    UnknownCityError,
)
from app.listings.domain.deduplication import normalize_address
from app.listings.domain.filters import ListingFilter
from app.listings.domain.models import Listing, ListingStatus
from app.listings.domain.ranking import BudgetRecencyRanking
from app.listings.infrastructure.in_memory_repository import (
    DATA_PATH,
    InMemoryListingRepository,
    JsonFileListingRepository,
    load_listings,
)

TODAY = date(2026, 11, 12)
SAMPLE = load_listings()
ALL_STATUSES: frozenset[ListingStatus] = frozenset({"active", "pending", "sold"})


def make_service(listings: Iterable[Listing] = SAMPLE) -> ListingSearchService:
    return ListingSearchService(
        InMemoryListingRepository(listings), BudgetRecencyRanking(), clock=lambda: TODAY
    )


@pytest.fixture
def service() -> ListingSearchService:
    return make_service()


def keys(result: SearchResult) -> list[tuple[str, str]]:
    return [(item.listing.source, item.listing.id) for item in result.items]


# --- Ranking ---


def test_closer_to_budget_scores_higher() -> None:
    ranking = BudgetRecencyRanking()
    on_budget = ranking.score(SAMPLE[0], 450000, TODAY)
    off_budget = ranking.score(SAMPLE[0], 900000, TODAY)
    assert on_budget.budget == 100
    assert on_budget.relevance > off_budget.relevance


def test_budget_fit_never_goes_below_zero() -> None:
    # |450000 - 200000| / 200000 = 1.25, which would be -25 without the clamp.
    assert BudgetRecencyRanking().score(SAMPLE[0], 200000, TODAY).budget == 0


def test_newer_listing_scores_higher() -> None:
    ranking = BudgetRecencyRanking()
    old = SAMPLE[0].model_copy(update={"listed_date": date(2026, 1, 1)})
    new = SAMPLE[0].model_copy(update={"listed_date": date(2026, 11, 10)})
    assert ranking.score(new, 450000, TODAY).relevance > ranking.score(old, 450000, TODAY).relevance


def test_future_listed_date_counts_as_today() -> None:
    future = SAMPLE[0].model_copy(update={"listed_date": date(2030, 1, 1)})
    assert BudgetRecencyRanking().score(future, None, TODAY).recency == 100


@pytest.mark.parametrize("target_budget", [None, 0.01, 1, 450000, 10_000_000, 1e308])
@pytest.mark.parametrize("listed", [date(1990, 1, 1), TODAY, date(2999, 1, 1)])
def test_scores_stay_between_0_and_100_for_extreme_inputs(target_budget: float | None, listed: date) -> None:
    listing = SAMPLE[0].model_copy(update={"listed_date": listed})
    score = BudgetRecencyRanking().score(listing, target_budget, TODAY)
    for value in (score.relevance, score.recency, score.budget or 0.0):
        assert 0 <= value <= 100


def test_free_listing_is_scored_like_any_other() -> None:
    free = SAMPLE[0].model_copy(update={"price": 0})
    assert BudgetRecencyRanking().score(free, 450000, TODAY).budget == 0


def test_without_budget_relevance_is_recency(service: ListingSearchService) -> None:
    result = service.search(SearchCriteria())
    assert result.items[0].listing.id == "A5"  # the newest active listing
    assert all(
        item.score.budget is None and item.score.relevance == item.score.recency for item in result.items
    )


def test_tied_scores_are_ordered_by_source_then_id() -> None:
    same_score = [
        SAMPLE[0].model_copy(update={"source": "MLS_B", "id": "Z9", "address": "1 Tie St"}),
        SAMPLE[0].model_copy(update={"source": "MLS_B", "id": "A1", "address": "2 Tie St"}),
        SAMPLE[0].model_copy(update={"source": "MLS_A", "id": "A1", "address": "3 Tie St"}),
    ]
    result = make_service(same_score).search(SearchCriteria())
    assert keys(result) == [("MLS_A", "A1"), ("MLS_B", "A1"), ("MLS_B", "Z9")]


def test_tied_scores_prefer_the_newer_listing() -> None:
    # Both are 100% off budget in opposite directions and too old for recency to matter.
    older = SAMPLE[0].model_copy(update={"id": "OLD", "price": 0, "listed_date": date(2000, 1, 1)})
    newer = SAMPLE[0].model_copy(
        update={"id": "NEW", "price": 200000, "listed_date": date(2000, 1, 2), "address": "2 Other St"}
    )
    result = make_service([older, newer]).search(SearchCriteria(target_budget=100000))
    assert [item.listing.id for item in result.items] == ["NEW", "OLD"]


def test_scores_that_round_to_the_same_value_are_ordered_by_the_tie_rule() -> None:
    # Unrounded, OLD scores 70.0 and NEW 69.9993. Both are shown as 70.0, so the newer one goes first.
    on_budget = SAMPLE[0].model_copy(update={"id": "OLD", "price": 100000, "listed_date": date(2000, 1, 1)})
    one_dollar_off = SAMPLE[0].model_copy(
        update={"id": "NEW", "price": 100001, "listed_date": date(2000, 1, 2), "address": "2 Other St"}
    )
    result = make_service([on_budget, one_dollar_off]).search(SearchCriteria(target_budget=100000))
    assert [(item.listing.id, item.score.relevance) for item in result.items] == [
        ("NEW", 70.0),
        ("OLD", 70.0),
    ]


def test_full_ranking_for_a_fixed_budget_and_date(service: ListingSearchService) -> None:
    """Pins the whole order, so any change to the formula shows up as a failing test."""
    result = service.search(SearchCriteria(target_budget=450000, page_size=100))
    assert [(item.listing.id, round(item.score.relevance, 2)) for item in result.items] == [
        ("A1", 83.04),
        ("A5", 80.83),
        ("A3", 75.55),
        ("A6", 75.11),
        ("A2", 71.96),
        ("B10", 60.8),
        ("A4", 58.89),
    ]


# --- Duplicates across feeds ---


@pytest.mark.parametrize(
    "left,right",
    [
        ("123 Main St, Apt 4B", "123 Main Street, Unit 4B"),
        ("456 Oak Ave", "456  oak AVENUE"),
        ("55 Elm Ct", "55 Elm Court"),
        ("9 N Lake Dr #2", "9 North Lake Drive, Suite 2"),
    ],
)
def test_address_spellings_normalize_to_the_same_value(left: str, right: str) -> None:
    assert normalize_address(left) == normalize_address(right)


def test_different_addresses_stay_different() -> None:
    assert normalize_address("22 Birch Ln") != normalize_address("100 Maple Dr")
    assert normalize_address("123 Main St, Apt 4B") != normalize_address("123 Main St, Apt 5B")


def test_duplicates_collapse_into_the_best_ranked_record(service: ListingSearchService) -> None:
    result = service.search(
        SearchCriteria(filters=ListingFilter(statuses=ALL_STATUSES), target_budget=452000, page_size=100)
    )
    merged = {
        (item.listing.id, tuple(duplicate.id for duplicate in item.duplicates))
        for item in result.items
        if item.duplicates
    }
    # B7 is priced exactly on budget, so here it represents the property instead of A1.
    assert merged == {("B7", ("A1",)), ("A2", ("B8",)), ("A3", ("B9",)), ("A5", ("B11",))}
    assert result.total == 8  # 12 records, 4 of them duplicates


def test_only_records_that_passed_the_filters_are_merged(service: ListingSearchService) -> None:
    # B7 (452000) is filtered out by max_price, so A1 has no duplicate in this search.
    result = service.search(SearchCriteria(filters=ListingFilter(max_price=451000, city="Springfield")))
    assert keys(result) == [("MLS_A", "A1")]
    assert result.items[0].duplicates == ()


def test_a_property_in_three_feeds_lists_the_other_records_in_rank_order() -> None:
    # Fed out of rank order; on the same date the price closest to the budget wins.
    house = SAMPLE[0]
    feeds = [
        house.model_copy(update={"source": "MLS_C", "id": "C1", "price": 470000}),
        house,
        house.model_copy(update={"source": "MLS_B", "id": "B1", "price": 460000}),
    ]
    result = make_service(feeds).search(SearchCriteria(target_budget=450000))
    assert result.total == 1
    assert [(item.listing.id, [other.id for other in item.duplicates]) for item in result.items] == [
        ("A1", ["B1", "C1"])
    ]


# --- Pagination ---


def test_pages_cover_every_result_exactly_once(service: ListingSearchService) -> None:
    pages = [
        service.search(SearchCriteria(page=page, page_size=3, target_budget=460000)) for page in (1, 2, 3)
    ]
    assert [len(page.items) for page in pages] == [3, 3, 1]
    assert pages[0].total == 7
    assert pages[0].total_pages == 3
    assert len({key for page in pages for key in keys(page)}) == 7


@pytest.mark.parametrize("page_size", range(1, 10))
def test_pages_in_order_rebuild_the_full_ranking(service: ListingSearchService, page_size: int) -> None:
    """Pages are cut after duplicates are merged, so no page size skips or repeats a property."""
    every_status = ListingFilter(statuses=ALL_STATUSES)

    def page_keys(page: int, size: int) -> list[tuple[str, str]]:
        criteria = SearchCriteria(filters=every_status, target_budget=460000, page=page, page_size=size)
        return keys(service.search(criteria))

    full_ranking = page_keys(1, 100)
    total_pages = service.search(SearchCriteria(filters=every_status, page_size=page_size)).total_pages
    pages = [key for page in range(1, total_pages + 1) for key in page_keys(page, page_size)]
    assert pages == full_ranking
    assert page_keys(total_pages + 1, page_size) == []


def test_page_past_the_end_is_empty_but_keeps_totals(service: ListingSearchService) -> None:
    result = service.search(SearchCriteria(page=4, page_size=3))
    assert result.items == ()
    assert result.total == 7
    assert result.total_pages == 3


# --- Unknown city ---


@pytest.mark.parametrize(
    "city,suggestion",
    [
        ("Atlantis", None),
        ("NYC", None),
        ("Springfieldd", "Springfield"),
        ("Sprngfield", "Springfield"),
        ("Spring field", "Springfield"),
        ("  viena ", "Vienna"),
        # The suggestion comes from every listing, so a city whose only listing is pending counts.
        ("Chantily", "Chantilly"),
    ],
)
def test_city_that_no_listing_has_is_an_error_with_the_closest_city(
    service: ListingSearchService, city: str, suggestion: str | None
) -> None:
    with pytest.raises(UnknownCityError) as error:
        service.search(SearchCriteria(filters=ListingFilter(city=city)))
    assert error.value.suggestion == suggestion


@pytest.mark.parametrize(
    "filters",
    [
        ListingFilter(city="Chantilly"),  # its only listing is pending
        ListingFilter(city="Fairfax", min_price=500000),
        ListingFilter(city="   ", keyword="helipad"),
    ],
)
def test_known_city_with_no_matches_is_an_empty_page(
    service: ListingSearchService, filters: ListingFilter
) -> None:
    assert service.search(SearchCriteria(filters=filters)).total == 0


# --- Data loading ---


def test_sample_file_loads_all_records() -> None:
    assert len(SAMPLE) == 12


def test_duplicate_source_and_id_is_rejected(tmp_path: Path) -> None:
    dataset = tmp_path / "listings.json"
    dataset.write_text("[" + ",".join([SAMPLE[0].model_dump_json(by_alias=True)] * 2) + "]")
    with pytest.raises(ValueError, match="duplicate"):
        load_listings(dataset)


def test_malformed_record_is_rejected(tmp_path: Path) -> None:
    dataset = tmp_path / "listings.json"
    dataset.write_text('[{"id":"A1"}]')
    with pytest.raises(ValueError):
        load_listings(dataset)


@pytest.mark.parametrize("contents", [None, "", "not json", '{"id": "A1"}', '[{"id": "A1"}]'])
def test_missing_or_broken_file_makes_listings_unavailable(tmp_path: Path, contents: str | None) -> None:
    dataset = tmp_path / "listings.json"
    if contents is not None:
        dataset.write_text(contents)
    with pytest.raises(ListingsUnavailableError):
        JsonFileListingRepository(dataset).find(ListingFilter())


def test_file_repository_recovers_once_the_file_is_fixed(tmp_path: Path) -> None:
    dataset = tmp_path / "listings.json"
    repository = JsonFileListingRepository(dataset)
    with pytest.raises(ListingsUnavailableError):
        repository.find(ListingFilter())

    shutil.copy(DATA_PATH, dataset)
    assert len(list(repository.find(ListingFilter(statuses=ALL_STATUSES)))) == 12
