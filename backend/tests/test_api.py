"""HTTP tests: the real app, called in-process through TestClient."""

from __future__ import annotations

import shutil
from collections.abc import Iterable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.listings.domain.filters import ListingFilter
from app.listings.domain.models import Listing
from app.listings.infrastructure.in_memory_repository import (
    DATA_PATH,
    InMemoryListingRepository,
    JsonFileListingRepository,
    load_listings,
)
from app.main import create_app

UNAVAILABLE = {
    "code": "SERVICE_UNAVAILABLE",
    "message": "Listings are temporarily unavailable. Please try again in a moment.",
    "details": [],
}


def test_search_returns_ranked_items_and_pagination(client: TestClient) -> None:
    response = client.get("/api/listings", params={"city": "RESTON", "pageSize": 1, "targetBudget": 600000})
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"] == {"page": 1, "pageSize": 1, "total": 2, "totalPages": 2}
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert (item["source"], item["id"], item["address"]) == ("MLS_A", "A4", "22 Birch Ln")
    assert (item["price"], item["bedrooms"], item["listedDate"]) == (610000, 4, "2026-09-03")
    # Exact, because the client scores recency against the fixed date in conftest.py.
    assert (item["relevanceScore"], item["budgetScore"], item["recencyScore"]) == (82.62, 98.33, 45.94)


def test_no_matches_is_200_with_empty_items(client: TestClient) -> None:
    # Chantilly is a known city, but its only listing is pending.
    response = client.get("/api/listings", params={"city": "Chantilly"})
    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "pagination": {"page": 1, "pageSize": 6, "total": 0, "totalPages": 0},
    }


def test_page_past_the_end_is_200_with_empty_items(client: TestClient) -> None:
    response = client.get("/api/listings", params={"page": 99, "pageSize": 5})
    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "pagination": {"page": 99, "pageSize": 5, "total": 7, "totalPages": 2},
    }


def test_last_page_can_be_partial(client: TestClient) -> None:
    body = client.get("/api/listings", params={"page": 2, "pageSize": 5}).json()
    assert len(body["items"]) == 2


def test_status_is_repeatable_and_defaults_to_active(client: TestClient) -> None:
    default = client.get("/api/listings", params={"pageSize": 100}).json()
    assert {item["status"] for item in default["items"]} == {"active"}
    both = client.get("/api/listings?status=active&status=pending&pageSize=100").json()
    assert {item["status"] for item in both["items"]} == {"active", "pending"}


def test_duplicates_are_listed_on_the_record_that_represents_them(client: TestClient) -> None:
    items = client.get("/api/listings", params={"targetBudget": 450000}).json()["items"]
    assert (items[0]["source"], items[0]["id"]) == ("MLS_A", "A1")
    assert items[0]["duplicates"] == [{"source": "MLS_B", "id": "B7"}]


def test_budget_score_is_null_without_a_target_budget(client: TestClient) -> None:
    item = client.get("/api/listings").json()["items"][0]
    assert item["budgetScore"] is None
    assert item["relevanceScore"] == item["recencyScore"]


def test_no_filters_returns_every_active_property(client: TestClient) -> None:
    body = client.get("/api/listings", params={"pageSize": 100}).json()
    assert body["pagination"] == {"page": 1, "pageSize": 100, "total": 7, "totalPages": 1}
    assert [item["id"] for item in body["items"]] == ["A5", "A4", "A2", "A3", "A1", "B10", "A6"]


def test_every_filter_at_once(client: TestClient) -> None:
    query = (
        "city=Springfield&keyword=pet&minPrice=400000&maxPrice=460000&minBedrooms=2"
        "&targetBudget=450000&status=active&status=pending&status=sold&page=1&pageSize=4"
    )
    body = client.get(f"/api/listings?{query}").json()
    assert body["pagination"] == {"page": 1, "pageSize": 4, "total": 1, "totalPages": 1}
    assert [(item["id"], item["duplicates"]) for item in body["items"]] == [
        ("A1", [{"source": "MLS_B", "id": "B7"}])
    ]


@pytest.mark.parametrize(
    "query",
    [
        "keyword=helipad",
        "minPrice=10000000",
        "minPrice=1e308",
        "maxPrice=0",
        "minPrice=0&maxPrice=0",
        "minBedrooms=99",
        "status=sold",
        "city=Reston&minBedrooms=5",
        "city=Fairfax&minPrice=500000",
    ],
)
def test_valid_filters_that_match_nothing_are_200_and_empty(client: TestClient, query: str) -> None:
    response = client.get(f"/api/listings?{query}")
    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "pagination": {"page": 1, "pageSize": 6, "total": 0, "totalPages": 0},
    }


@pytest.mark.parametrize(
    "query",
    [
        "minPrice=0",
        "maxPrice=1e308",
        "minPrice=450000&maxPrice=450000",
        "minPrice=399000.5",
        "minBedrooms=0",
        "city=",
        "city=%20%20",
        "keyword=",
        "keyword=%21%21%21",
        "keyword=%27%3B%20DROP%20TABLE--",
        "targetBudget=0.01",
        "targetBudget=1e308",
        "pageSize=1",
        "pageSize=100",
        "page=999999999999999999999999",
        "status=active&status=pending&status=sold",
    ],
)
def test_boundary_values_are_accepted_and_scores_stay_in_range(client: TestClient, query: str) -> None:
    response = client.get(f"/api/listings?{query}")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) <= body["pagination"]["pageSize"]
    for item in body["items"]:
        for score in (item["relevanceScore"], item["recencyScore"], item["budgetScore"] or 0):
            assert 0 <= score <= 100


@pytest.mark.parametrize(
    "params,field",
    [
        ({"pageSize": 0}, "pageSize"),
        ({"pageSize": -5}, "pageSize"),
        ({"pageSize": 101}, "pageSize"),
        ({"page": 0}, "page"),
        ({"minPrice": -1}, "minPrice"),
        ({"maxPrice": -1}, "maxPrice"),
        ({"minPrice": "abc"}, "minPrice"),
        ({"minPrice": "inf"}, "minPrice"),
        ({"minPrice": ""}, "minPrice"),
        ({"minPrice": "1,000"}, "minPrice"),
        ({"maxPrice": "1e400"}, "maxPrice"),
        ({"maxPrice": "-0.01"}, "maxPrice"),
        ({"minBedrooms": -3}, "minBedrooms"),
        ({"minBedrooms": "2.5"}, "minBedrooms"),
        ({"targetBudget": 0}, "targetBudget"),
        ({"targetBudget": -450000}, "targetBudget"),
        ({"targetBudget": "NaN"}, "targetBudget"),
        ({"page": "1.5"}, "page"),
        ({"page": "abc"}, "page"),
        ({"pageSize": "1.5"}, "pageSize"),
        ({"minBedrooms": "1e2"}, "minBedrooms"),
        ({"status": ""}, "status"),
        ({"status": "ACTIVE"}, "status"),
        ({"MINPRICE": "5"}, "MINPRICE"),
        ({"status": "archived"}, "status"),
        ({"status": ["active"] * 4}, "status"),
        ({"city": "x" * 121}, "city"),
        ({"keyword": "x" * 251}, "keyword"),
        ({"unknown": "1"}, "unknown"),
        ({"city": "Atlantis"}, "city"),
    ],
)
def test_invalid_parameter_is_422_naming_the_field(
    client: TestClient, params: dict[str, object], field: str
) -> None:
    response = client.get("/api/listings", params=params)
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "Invalid search parameters"
    assert [detail["field"] for detail in body["details"]] == [field]


@pytest.mark.parametrize(
    "query,message",
    [
        ("minPrice=abc", "Enter a number, for example 450000."),
        ("maxPrice=1e400", "Enter a number, for example 450000."),
        ("minBedrooms=2.5", "Enter a whole number, for example 3."),
        ("page=" + "9" * 5000, "Enter a smaller number."),
        ("minPrice=-1", "Enter 0 or more."),
        ("targetBudget=0", "Enter a number above 0."),
        ("pageSize=101", "Enter 100 or less."),
        ("city=" + "x" * 121, "Use at most 120 characters."),
        ("status=bogus", "Choose 'active', 'pending' or 'sold'."),
        ("status=active&status=active&status=active&status=active", "Choose at most 3."),
        ("minprice=5", "This is not a search option."),
    ],
)
def test_validation_messages_are_plain_language(client: TestClient, query: str, message: str) -> None:
    """Shown under a form field, so no "unable to parse string" or other wording meant for developers."""
    details = client.get(f"/api/listings?{query}").json()["details"]
    assert [detail["message"] for detail in details] == [message]


def test_min_price_above_max_price_is_reported_on_max_price(client: TestClient) -> None:
    response = client.get("/api/listings", params={"minPrice": 700000, "maxPrice": 200000})
    assert response.status_code == 422
    assert response.json()["details"] == [
        {"field": "maxPrice", "message": "Maximum price must be at least the minimum price."}
    ]


def test_city_that_no_listing_has_is_reported_on_city(client: TestClient) -> None:
    response = client.get("/api/listings", params={"city": "Atlantis", "status": "sold"})
    assert response.status_code == 422
    assert response.json()["details"] == [
        {"field": "city", "message": "No listings are in a city with this name."}
    ]


def test_misspelled_city_suggests_the_closest_known_one(client: TestClient) -> None:
    response = client.get("/api/listings", params={"city": "Sprngfield"})
    assert response.status_code == 422
    assert response.json()["details"] == [
        {"field": "city", "message": "No listings are in a city with this name. Did you mean Springfield?"}
    ]


def test_every_invalid_parameter_is_reported_in_one_response(client: TestClient) -> None:
    response = client.get("/api/listings?minPrice=-1&minBedrooms=x&targetBudget=0&status=gone&pageSize=0")
    assert response.status_code == 422
    assert {detail["field"] for detail in response.json()["details"]} == {
        "minPrice",
        "minBedrooms",
        "targetBudget",
        "status",
        "pageSize",
    }


def test_unknown_path_uses_the_error_format(client: TestClient) -> None:
    response = client.get("/api/unknown")
    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND", "message": "Not Found", "details": []}


def test_wrong_method_uses_the_error_format(client: TestClient) -> None:
    response = client.post("/api/listings")
    assert response.status_code == 405
    assert response.json() == {"code": "METHOD_NOT_ALLOWED", "message": "Method Not Allowed", "details": []}
    assert response.headers["allow"] == "GET"


def test_unexpected_failure_is_a_500_without_internal_details() -> None:
    class BrokenRepository:
        def find(self, filters: ListingFilter) -> Iterable[Listing]:
            raise RuntimeError("connection password=secret")

    with TestClient(create_app(BrokenRepository()), raise_server_exceptions=False) as client:
        response = client.get("/api/listings")
    assert response.status_code == 500
    assert response.json() == {
        "code": "INTERNAL_ERROR",
        "message": "Something went wrong on our side. Please try again.",
        "details": [],
    }
    assert "secret" not in response.text


def test_unavailable_listings_are_a_503_and_the_api_recovers_without_a_restart(tmp_path: Path) -> None:
    dataset = tmp_path / "listings.json"
    with TestClient(create_app(JsonFileListingRepository(dataset))) as client:
        # The app starts without the file and keeps answering.
        response = client.get("/api/listings")
        assert response.status_code == 503
        assert response.json() == UNAVAILABLE
        assert str(tmp_path) not in response.text

        shutil.copy(DATA_PATH, dataset)
        assert client.get("/api/listings").status_code == 200


def test_broken_data_file_is_a_503(tmp_path: Path) -> None:
    dataset = tmp_path / "listings.json"
    dataset.write_text('[{"id": "A1"}]')
    with TestClient(create_app(JsonFileListingRepository(dataset))) as client:
        response = client.get("/api/listings")
    assert (response.status_code, response.json()) == (503, UNAVAILABLE)


def test_app_uses_the_injected_repository() -> None:
    with TestClient(create_app(InMemoryListingRepository(load_listings()[:1]))) as client:
        assert client.get("/api/listings").json()["pagination"]["total"] == 1
