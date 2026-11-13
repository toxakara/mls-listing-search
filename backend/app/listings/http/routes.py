from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.listings.application.search import ListingSearchService
from app.listings.http.dto import SearchPageDTO, SearchQueryDTO
from app.listings.http.errors import ErrorDTO


def create_listings_router(service: ListingSearchService) -> APIRouter:
    """The service is passed in, so the route has no global state and tests can swap the storage."""
    router = APIRouter(prefix="/api", tags=["Listings"])

    @router.get("/listings", responses={422: {"model": ErrorDTO}, 503: {"model": ErrorDTO}})
    def search_listings(query: Annotated[SearchQueryDTO, Query()]) -> SearchPageDTO:
        return SearchPageDTO.from_domain(service.search(query.to_criteria()))

    return router
