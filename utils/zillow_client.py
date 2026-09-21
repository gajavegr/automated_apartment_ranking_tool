"""
Zillow listing search client (automated candidate import).

Why this module exists and why it is isolated
----------------------------------------------
Zillow has no official public listings-search API, and it actively blocks
direct scraping (see the note in manual_entry.py about 403 errors). Neither
the ChatGPT "Zillow plugin" nor any chat-tool connector is callable from a
backend service, so an automated, multi-user search must go through a
third-party scraper API using a server-side key that the app holds.

Everything provider-specific lives behind this module. The rest of the app
depends only on the normalized ``ListingResult`` shape. If the provider
changes, breaks, or is swapped for Apify/Bright Data, this file is the only
thing that changes.

Default provider: RapidAPI "zillow-com1" (propertyExtendedSearch). Configure
via environment variables (see env.example / config.py):

    ZILLOW_SEARCH_ENABLED   "true" to enable (default false)
    ZILLOW_RAPIDAPI_KEY     your RapidAPI key
    ZILLOW_RAPIDAPI_HOST    default "zillow-com1.p.rapidapi.com"

If disabled or unconfigured, ``is_enabled()`` returns False and callers should
surface a friendly "search not configured" message rather than erroring.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

import config
from utils.cache import Cache


ZILLOW_BASE_URL = "https://www.zillow.com"

# Cache search responses so repeated / test searches don't burn paid API calls.
_cache = Cache()

# Number of seconds to wait on the upstream scraper before giving up.
REQUEST_TIMEOUT = 20


class ZillowSearchError(Exception):
    """Raised when the upstream Zillow search provider fails."""


def is_enabled() -> bool:
    """True only if search is turned on AND a key is configured."""
    return bool(config.ZILLOW_SEARCH_ENABLED and config.ZILLOW_RAPIDAPI_KEY)


@dataclass
class ListingResult:
    """
    A normalized Zillow listing, provider-agnostic.

    These are the fields we can reliably get from a listing search. Fields the
    tool scores that Zillow does NOT provide (parking type, laundry type, WFH
    quality, tour answers) are intentionally absent — they stay manual, and the
    location fields (commute/safety/gym) are filled by the app's own enrichment
    after import.
    """
    zpid: str
    address: str
    zillow_url: str
    price: Optional[int] = None          # monthly rent
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    sqft: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    image_url: str = ""
    property_type: str = ""
    listing_status: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable form for the /search_zillow preview response."""
        return {
            "zpid": self.zpid,
            "address": self.address,
            "zillow_url": self.zillow_url,
            "price": self.price,
            "bedrooms": self.bedrooms,
            "bathrooms": self.bathrooms,
            "sqft": self.sqft,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "image_url": self.image_url,
            "property_type": self.property_type,
            "listing_status": self.listing_status,
        }

    def to_apartment_data(self) -> Dict[str, Any]:
        """
        Map to the ``data`` dict shape consumed by persist_apartment() / the
        /add pipeline, so imported listings flow through the exact same
        enrichment + scoring path as manually entered ones.
        """
        from datetime import datetime

        data: Dict[str, Any] = {
            "zillow_url": self.zillow_url,
            "address": self.address,
            "availability_status": "Available",
            "manual_safety_rating": 5.0,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        if self.price is not None:
            data["price"] = self.price
        if self.bedrooms is not None:
            data["bedrooms"] = self.bedrooms
        if self.bathrooms is not None:
            data["bathrooms"] = self.bathrooms
        if self.sqft:
            data["sqft"] = self.sqft
        return data


def _normalize_prop(prop: Dict[str, Any]) -> Optional[ListingResult]:
    """
    Convert one raw RapidAPI "prop" object into a ListingResult.

    Defensive on purpose: the upstream schema is unofficial and fields drift.
    Anything without a zpid or address is skipped rather than trusted.
    """
    zpid = str(prop.get("zpid") or prop.get("id") or "").strip()
    if not zpid:
        return None

    # Address can arrive as a flat string or as component parts.
    address = (prop.get("address") or "").strip()
    if not address:
        parts = [
            prop.get("addressStreet"),
            prop.get("addressCity"),
            prop.get("addressState"),
            prop.get("addressZipcode"),
        ]
        address = ", ".join(p for p in parts if p)
    if not address:
        return None

    # detailUrl may be absolute or a "/homedetails/..." relative path.
    detail_url = (prop.get("detailUrl") or "").strip()
    if detail_url.startswith("http"):
        zillow_url = detail_url
    elif detail_url:
        zillow_url = ZILLOW_BASE_URL + detail_url
    else:
        zillow_url = f"{ZILLOW_BASE_URL}/homedetails/{zpid}_zpid/"

    def _to_int(value: Any) -> Optional[int]:
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return None

    def _to_float(value: Any) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    return ListingResult(
        zpid=zpid,
        address=address,
        zillow_url=zillow_url,
        price=_to_int(prop.get("price")),
        bedrooms=_to_int(prop.get("bedrooms")),
        bathrooms=_to_float(prop.get("bathrooms")),
        sqft=_to_int(prop.get("livingArea") or prop.get("sqft")),
        latitude=_to_float(prop.get("latitude")),
        longitude=_to_float(prop.get("longitude")),
        image_url=(prop.get("imgSrc") or "").strip(),
        property_type=(prop.get("propertyType") or "").strip(),
        listing_status=(prop.get("listingStatus") or "").strip(),
        raw=prop,
    )


def search_listings(
    location: str,
    max_rent: Optional[int] = None,
    min_beds: Optional[int] = None,
    min_baths: Optional[float] = None,
    min_sqft: Optional[int] = None,
    limit: int = 40,
    use_cache: bool = True,
) -> List[ListingResult]:
    """
    Search for-rent Zillow listings via the configured provider.

    Args:
        location: Free-text location, e.g. "San Francisco, CA" or a ZIP.
        max_rent: Upper monthly-rent bound.
        min_beds / min_baths / min_sqft: Lower bounds.
        limit: Max normalized results to return.
        use_cache: Serve from local cache when available (avoids paid calls).

    Returns:
        List of normalized ListingResult (may be empty).

    Raises:
        ZillowSearchError: on configuration or upstream failure.
    """
    if not is_enabled():
        raise ZillowSearchError(
            "Zillow search is not configured. Set ZILLOW_SEARCH_ENABLED=true "
            "and ZILLOW_RAPIDAPI_KEY (see env.example)."
        )

    params: Dict[str, Any] = {
        "location": location,
        "status_type": "ForRent",
        "page": 1,
    }
    if max_rent is not None:
        params["rentMaxPrice"] = int(max_rent)
    if min_beds is not None:
        params["bedsMin"] = int(min_beds)
    if min_baths is not None:
        params["bathsMin"] = min_baths
    if min_sqft is not None:
        params["sqftMin"] = int(min_sqft)

    cache_key = "zillow_search:" + json.dumps(params, sort_keys=True)
    if use_cache:
        cached = _cache.get(cache_key)
        if cached is not None:
            return [ListingResult(**item) for item in cached]

    url = f"https://{config.ZILLOW_RAPIDAPI_HOST}/propertyExtendedSearch"
    headers = {
        "X-RapidAPI-Key": config.ZILLOW_RAPIDAPI_KEY,
        "X-RapidAPI-Host": config.ZILLOW_RAPIDAPI_HOST,
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise ZillowSearchError(f"Zillow search request failed: {exc}") from exc

    if resp.status_code != 200:
        raise ZillowSearchError(
            f"Zillow search provider returned HTTP {resp.status_code}: "
            f"{resp.text[:200]}"
        )

    try:
        payload = resp.json()
    except ValueError as exc:
        raise ZillowSearchError("Zillow search returned invalid JSON") from exc

    props = payload.get("props") or payload.get("results") or []
    listings: List[ListingResult] = []
    for prop in props:
        normalized = _normalize_prop(prop)
        if normalized is not None:
            listings.append(normalized)
        if len(listings) >= limit:
            break

    if use_cache:
        # Store the dataclass fields (raw included) so cache round-trips cleanly.
        _cache.set(cache_key, [vars(l) for l in listings])

    return listings
