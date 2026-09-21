"""
DataSF property enrichment client (San Francisco open data).

Authoritative, free, official SF property facts from the Assessor-Recorder's
secured property tax roll (Socrata dataset ``wv5m-vpq2``). This is the same
Socrata platform already used for crime data, so no new infrastructure.

Use this for building-level facts once an apartment's address is known:
    - year_built      -> drives the SF rent-control determination
    - number_of_units -> building size
    - use_definition  -> property type (e.g. "Apartment", "Dwelling", "Condominium")

Important caveat on square footage
----------------------------------
For a multi-unit APARTMENT building, the roll row describes the whole
parcel/building: ``property_area`` is the total building area and
``number_of_units`` is the count of units in the building — NOT the individual
apartment's size. Per-unit area from this source is only meaningful for condos
and single-parcel homes (which each have their own APN). ``to_apartment_data``
therefore only surfaces sqft when the parcel is effectively a single unit.

No API key required (the dataset is public). An optional Socrata app token
(``DATASF_APP_TOKEN``) raises anonymous rate limits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

import config
from utils.cache import Cache


_cache = Cache()
# Leading-wildcard LIKE on property_location forces a scan, which can be slow
# under load, so allow generous headroom before giving up.
REQUEST_TIMEOUT = 30

# The roll's ``property_location`` is a fixed-width composite, NOT a clean
# address, e.g. "0000 2000 BROADWAY              0000" or
# "0000 0749 FILBERT             ST0000". Notable quirks we match around:
#   - a leading range field ("0000" or a secondary number), then a space
#   - the primary street number zero-padded to 4 digits ("0749")
#   - the street name, then padding, then a 2-char type + unit suffix
# So we match with a CONTAINS on " <4-digit-number> <NAME>" (leading space
# guards against 2000 -> 12000 false positives) and drop the street-type suffix,
# which the roll and the input often disagree on (ST vs STREET, etc.).
_UNIT_TOKEN_RE = re.compile(r"\b(?:APT|UNIT|STE|SUITE|#)\b.*$", re.IGNORECASE)

_STREET_TYPES = {
    "ST", "STREET", "AVE", "AVENUE", "BLVD", "BOULEVARD", "DR", "DRIVE",
    "CT", "COURT", "LN", "LANE", "WAY", "PL", "PLACE", "RD", "ROAD",
    "TER", "TERRACE", "CIR", "CIRCLE", "HWY", "HIGHWAY", "PKWY", "PARKWAY",
    "ALY", "ALLEY", "PLZ", "PLAZA", "SQ", "SQUARE", "WALK", "ROW", "LOOP",
}


class DataSFError(Exception):
    """Raised when the DataSF/Socrata request fails."""


@dataclass
class PropertyRecord:
    """Normalized assessor-roll record for one parcel."""
    parcel_number: str
    property_location: str
    year_built: Optional[int] = None
    building_sqft: Optional[int] = None
    lot_sqft: Optional[int] = None
    number_of_units: Optional[int] = None
    number_of_bedrooms: Optional[int] = None
    number_of_bathrooms: Optional[float] = None
    number_of_stories: Optional[int] = None
    use_definition: str = ""
    closed_roll_year: Optional[int] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_rent_controlled(self) -> Optional[bool]:
        """SF rent-control heuristic: built before the ordinance cutoff.
        None if year unknown (can't determine)."""
        if self.year_built is None:
            return None
        return self.year_built < config.SF_RENT_CONTROL_CUTOFF_YEAR

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parcel_number": self.parcel_number,
            "property_location": self.property_location,
            "year_built": self.year_built,
            "building_sqft": self.building_sqft,
            "lot_sqft": self.lot_sqft,
            "number_of_units": self.number_of_units,
            "number_of_bedrooms": self.number_of_bedrooms,
            "number_of_bathrooms": self.number_of_bathrooms,
            "number_of_stories": self.number_of_stories,
            "use_definition": self.use_definition,
            "closed_roll_year": self.closed_roll_year,
            "is_rent_controlled": self.is_rent_controlled,
        }

    def to_apartment_data(self) -> Dict[str, Any]:
        """
        Map to the ``data`` dict shape consumed by persist_apartment(), for
        authoritatively filling year_built + rent_control (and sqft only when the
        parcel is a single unit — see the module-level caveat).
        """
        data: Dict[str, Any] = {}
        if self.year_built is not None:
            data["year_built"] = self.year_built
            data["rent_control"] = self.is_rent_controlled
        # Only trust building_sqft as the unit's sqft for a true single unit
        # (condo/SFR). units==0 means unknown/non-residential; multi-unit means
        # this is the whole building, not the apartment.
        if self.building_sqft and self.number_of_units == 1:
            data["sqft"] = self.building_sqft
        return data


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


def _normalize_street(address: str) -> str:
    """Reduce a free-text address to 'NUMBER STREETNAME' (uppercased, unit
    stripped) for matching against the roll's ``property_location``."""
    street = address.split(",")[0]
    street = _UNIT_TOKEN_RE.sub("", street)
    street = re.sub(r"\s+", " ", street).strip().upper()
    return street


def _parse_address(address: str):
    """Return (number4, street_name) for LIKE matching, or None if the address
    has no leading street number. ``number4`` is zero-padded to 4 digits to
    match the roll's format; the street-type suffix is dropped."""
    tokens = _normalize_street(address).split(" ")
    if not tokens or not tokens[0].isdigit():
        return None
    number4 = tokens[0].zfill(4)
    name_tokens = tokens[1:]
    if name_tokens and name_tokens[-1] in _STREET_TYPES:
        name_tokens = name_tokens[:-1]
    name = " ".join(name_tokens)
    if not name:
        return None
    return number4, name


def _normalize_record(row: Dict[str, Any]) -> PropertyRecord:
    return PropertyRecord(
        parcel_number=str(row.get("parcel_number") or "").strip(),
        property_location=str(row.get("property_location") or "").strip(),
        year_built=_to_int(row.get("year_property_built")),
        building_sqft=_to_int(row.get("property_area")),
        lot_sqft=_to_int(row.get("lot_area")),
        number_of_units=_to_int(row.get("number_of_units")),
        number_of_bedrooms=_to_int(row.get("number_of_bedrooms")),
        number_of_bathrooms=_to_float(row.get("number_of_bathrooms")),
        number_of_stories=_to_int(row.get("number_of_stories")),
        use_definition=str(row.get("use_definition") or "").strip(),
        closed_roll_year=_to_int(row.get("closed_roll_year")),
        raw=row,
    )


def _query(where: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Run a SoQL query against the assessor roll, newest roll year first."""
    params = {
        "$where": where,
        "$order": "closed_roll_year DESC",
        "$limit": limit,
    }
    headers = {}
    if getattr(config, "DATASF_APP_TOKEN", ""):
        headers["X-App-Token"] = config.DATASF_APP_TOKEN
    try:
        resp = requests.get(
            config.DATASF_ASSESSOR_ENDPOINT,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise DataSFError(f"DataSF request failed: {exc}") from exc

    if resp.status_code != 200:
        raise DataSFError(
            f"DataSF returned HTTP {resp.status_code}: {resp.text[:200]}"
        )
    try:
        return resp.json()
    except ValueError as exc:
        raise DataSFError("DataSF returned invalid JSON") from exc


def lookup_by_parcel(apn: str, use_cache: bool = True) -> Optional[PropertyRecord]:
    """Look up the most recent roll record for an Assessor Parcel Number."""
    apn = (apn or "").strip()
    if not apn:
        return None
    cache_key = f"datasf_apn:{apn}"
    if use_cache:
        cached = _cache.get(cache_key)
        if cached is not None:
            return _normalize_record(cached) if cached else None

    apn_escaped = apn.replace("'", "''")
    rows = _query(f"parcel_number = '{apn_escaped}'", limit=5)
    record = _normalize_record(rows[0]) if rows else None
    if use_cache:
        _cache.set(cache_key, record.raw if record else {})
    return record


def lookup_by_address(address: str, use_cache: bool = True) -> Optional[PropertyRecord]:
    """
    Best-effort lookup of the assessor record for a street address.

    Matching is fuzzy: the roll stores addresses without city/ZIP and with
    inconsistent street-type suffixes, so we filter on street number + name stem
    and then pick the closest candidate (newest roll year). Returns None if
    nothing plausibly matches.
    """
    if not address or not address.strip():
        return None

    cache_key = f"datasf_addr:{_normalize_street(address)}"
    if use_cache:
        cached = _cache.get(cache_key)
        if cached is not None:
            return _normalize_record(cached) if cached else None

    parsed = _parse_address(address)
    if parsed is None:
        return None
    number4, name = parsed
    # Leading space in the pattern prevents 2000 -> 12000 style false matches.
    pattern = f"% {number4} {name}%".replace("'", "''")
    rows = _query(f"upper(property_location) like '{pattern}'", limit=50)

    # Rows are ordered newest-roll-first; take the first match. (For condos the
    # address yields one row per unit — all share the building's year_built.)
    record = _normalize_record(rows[0]) if rows else None
    if use_cache:
        _cache.set(cache_key, record.raw if record else {})
    return record
