"""Wire format of GET /api/listings: camelCase JSON, snake_case Python."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from pydantic.alias_generators import to_camel
from pydantic_core import PydanticCustomError

from app.listings.application.search import DEFAULT_PAGE_SIZE, RankedListing, SearchCriteria, SearchResult
from app.listings.domain.filters import DEFAULT_STATUSES, ListingFilter
from app.listings.domain.models import ListingStatus

MAX_PAGE_SIZE = 100
MAX_CITY_LENGTH = 120
MAX_KEYWORD_LENGTH = 250


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True, validate_by_alias=True)


class SearchQueryDTO(CamelModel):
    """Query parameters. All input validation lives here; unknown parameters are rejected."""

    model_config = ConfigDict(extra="forbid")

    min_price: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    max_price: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    min_bedrooms: int | None = Field(default=None, ge=0)
    city: str | None = Field(default=None, max_length=MAX_CITY_LENGTH)
    keyword: str | None = Field(default=None, max_length=MAX_KEYWORD_LENGTH)
    target_budget: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    # Repeatable: ?status=active&status=pending. Capped like every other parameter.
    status: list[ListingStatus] = Field(default_factory=lambda: sorted(DEFAULT_STATUSES), max_length=3)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)

    @field_validator("max_price")
    @classmethod
    def max_price_not_below_min_price(cls, max_price: float | None, info: ValidationInfo) -> float | None:
        # A field validator (not a model validator) so the error is reported on `maxPrice`.
        # `min_price` is declared first, so it is already in `info.data` when it was valid.
        min_price = info.data.get("min_price")
        if min_price is not None and max_price is not None and min_price > max_price:
            raise PydanticCustomError("price_range", "Maximum price must be at least the minimum price.")
        return max_price

    def to_criteria(self) -> SearchCriteria:
        return SearchCriteria(
            filters=ListingFilter(
                min_price=self.min_price,
                max_price=self.max_price,
                min_bedrooms=self.min_bedrooms,
                city=self.city,
                keyword=self.keyword,
                statuses=frozenset(self.status),
            ),
            target_budget=self.target_budget,
            page=self.page,
            page_size=self.page_size,
        )


class ListingRefDTO(BaseModel):
    source: str
    id: str


class RankedListingDTO(CamelModel):
    """A listing plus its scores (0-100).

    The fields are listed here rather than inherited from the domain `Listing`, so a field added
    to the domain does not appear in the API until it is added to this contract on purpose.
    """

    id: str
    source: str
    address: str
    city: str
    state: str
    zip: str
    price: float
    bedrooms: int
    bathrooms: float
    sqft: int
    latitude: float
    longitude: float
    listed_date: date
    status: ListingStatus
    description: str
    relevance_score: float
    recency_score: float
    budget_score: float | None
    duplicates: list[ListingRefDTO]

    @classmethod
    def from_domain(cls, item: RankedListing) -> RankedListingDTO:
        listing, score = item.listing, item.score
        return cls(
            id=listing.id,
            source=listing.source,
            address=listing.address,
            city=listing.city,
            state=listing.state,
            zip=listing.zip,
            price=listing.price,
            bedrooms=listing.bedrooms,
            bathrooms=listing.bathrooms,
            sqft=listing.sqft,
            latitude=listing.latitude,
            longitude=listing.longitude,
            listed_date=listing.listed_date,
            status=listing.status,
            description=listing.description,
            relevance_score=score.relevance,
            recency_score=score.recency,
            budget_score=score.budget,
            duplicates=[ListingRefDTO(source=d.source, id=d.id) for d in item.duplicates],
        )


class PaginationDTO(CamelModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class SearchPageDTO(CamelModel):
    items: list[RankedListingDTO]
    pagination: PaginationDTO

    @classmethod
    def from_domain(cls, result: SearchResult) -> SearchPageDTO:
        return cls(
            items=[RankedListingDTO.from_domain(item) for item in result.items],
            pagination=PaginationDTO(
                page=result.page,
                page_size=result.page_size,
                total=result.total,
                total_pages=result.total_pages,
            ),
        )
