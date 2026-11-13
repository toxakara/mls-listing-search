from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

ListingStatus = Literal["active", "pending", "sold"]


class Listing(BaseModel):
    """One record from an MLS feed. `id` is unique only within its `source`."""

    # The feed is camelCase (`listedDate`); Python code uses snake_case.
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        extra="forbid",
        frozen=True,
    )

    id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    address: str
    city: str
    state: str
    zip: str
    price: float = Field(ge=0)
    bedrooms: int = Field(ge=0)
    bathrooms: float = Field(ge=0)
    sqft: int = Field(ge=0)
    latitude: float
    longitude: float
    listed_date: date
    status: ListingStatus
    description: str
