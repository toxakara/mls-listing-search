"""Which listings a search matches. The rules are the same whichever storage runs the query."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property
from typing import get_args

from app.listings.domain.models import Listing, ListingStatus

ALL_STATUSES: frozenset[ListingStatus] = frozenset(get_args(ListingStatus))
# Buyers search what is on the market; pending and sold are opt-in.
DEFAULT_STATUSES: frozenset[ListingStatus] = frozenset({"active"})
_WORD = re.compile(r"\w+")


def fold_plural(word: str) -> str:
    """'pets' -> 'pet', 'amenities' -> 'amenity', 'porches' -> 'porch'; other words unchanged.

    Without a dictionary some plurals fold to a wrong stem ('movies' -> 'movy', 'buses' -> 'buse'),
    and irregular ones ('children') are left alone: listings rarely use them.
    """
    if len(word) <= 3 or word.endswith("ss"):
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith(("ches", "shes", "sses", "xes")):
        return word[:-2]
    if word.endswith("s"):
        return word[:-1]
    return word


def _words(text: str) -> list[str]:
    return _WORD.findall(text.casefold())


def keyword_tokens(keyword: str | None) -> tuple[str, ...]:
    return tuple(_words(keyword or ""))


def _word_starts_with(word: str, token: str) -> bool:
    # As written, a singular starts its plural: 'movie' -> 'movies'.
    # In the singular, a plural starts its singular: 'pets' -> 'pet', 'amenities' -> 'amenity'.
    return word.startswith(token) or fold_plural(word).startswith(fold_plural(token))


def matches_keyword(description: str, tokens: tuple[str, ...]) -> bool:
    """Every token must start a word: 'pet' matches 'pets' but not 'carpet', and 'pets' matches 'Pet'."""
    if not tokens:
        # Most searches have no keyword; splitting every description into words would be wasted.
        return True
    words = _words(description)
    return all(any(_word_starts_with(word, token) for word in words) for token in tokens)


@dataclass(frozen=True)
class ListingFilter:
    """Search filters, combined with AND; `None` means no constraint.

    Each repository translates this into its own query (SQL WHERE, Elasticsearch bool query, ...).
    `matches` is the reference behaviour, and the repository contract tests hold every
    implementation to it.
    """

    min_price: float | None = None
    max_price: float | None = None
    min_bedrooms: int | None = None
    # Case-insensitive substring of the city.
    city: str | None = None
    # Matched against the description with `matches_keyword`.
    keyword: str | None = None
    statuses: frozenset[ListingStatus] = DEFAULT_STATUSES

    # Both are derived from the fields once per filter, not once per listing checked.
    @cached_property
    def _city(self) -> str:
        return (self.city or "").strip().casefold()

    @cached_property
    def _keyword_tokens(self) -> tuple[str, ...]:
        return keyword_tokens(self.keyword)

    def matches(self, listing: Listing) -> bool:
        return (
            listing.status in self.statuses
            and (self.min_price is None or listing.price >= self.min_price)
            and (self.max_price is None or listing.price <= self.max_price)
            and (self.min_bedrooms is None or listing.bedrooms >= self.min_bedrooms)
            and self._city in listing.city.casefold()
            and matches_keyword(listing.description, self._keyword_tokens)
        )
