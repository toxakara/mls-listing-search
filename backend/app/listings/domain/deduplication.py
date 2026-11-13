from __future__ import annotations

import re

from app.listings.domain.models import Listing

# Feeds spell the same address differently: "123 Main St, Apt 4B" vs "123 Main Street, Unit 4B".
_CANONICAL_WORDS = {
    "st": "street",
    "ave": "avenue",
    "av": "avenue",
    "rd": "road",
    "ln": "lane",
    "dr": "drive",
    "ct": "court",
    "blvd": "boulevard",
    "pl": "place",
    "ter": "terrace",
    "hwy": "highway",
    "pkwy": "parkway",
    "cir": "circle",
    "sq": "square",
    "n": "north",
    "s": "south",
    "e": "east",
    "w": "west",
    "apt": "unit",
    "apartment": "unit",
    "ste": "unit",
    "suite": "unit",
    "#": "unit",
}
_ADDRESS_WORD = re.compile(r"#|[a-z0-9]+")

PropertyKey = tuple[str, str, str]


def normalize_address(address: str) -> str:
    """'123 Main St, Apt 4B' -> '123 main street unit 4b'."""
    words = _ADDRESS_WORD.findall(address.casefold())
    return " ".join(_CANONICAL_WORDS.get(word, word) for word in words)


def property_key(listing: Listing) -> PropertyKey:
    """Listings with the same key are the same physical property.

    ZIP is left out on purpose: the feeds disagree on it (22150 vs 22151 for 456 Oak Ave).
    """
    return (
        listing.state.strip().casefold(),
        listing.city.strip().casefold(),
        normalize_address(listing.address),
    )
