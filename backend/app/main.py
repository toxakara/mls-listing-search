"""Composition root: the only place that picks concrete implementations."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from fastapi import FastAPI

from app.listings.application.ports import ListingRepository
from app.listings.application.search import ListingSearchService, utc_today
from app.listings.domain.ranking import BudgetRecencyRanking
from app.listings.http.errors import register_error_handlers
from app.listings.http.routes import create_listings_router
from app.listings.infrastructure.in_memory_repository import JsonFileListingRepository


def create_app(repository: ListingRepository | None = None, clock: Callable[[], date] = utc_today) -> FastAPI:
    """Tests pass their own repository and a fixed date; by default the listings come from the JSON file.

    Moving to a database means replacing the one line that builds the repository.
    """
    if repository is None:
        repository = JsonFileListingRepository()
    service = ListingSearchService(repository, BudgetRecencyRanking(), clock)

    app = FastAPI(title="MLS Explorer API")
    app.include_router(create_listings_router(service))
    register_error_handlers(app)
    return app


app = create_app()
