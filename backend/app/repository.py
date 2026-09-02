"""
Read-only access to the normalized reference data in `backend/data/`.

Everything is loaded once at import and cached in module-level indexes. The
data is static gazetted reference material, so there is no database and no
write path anywhere in this service.

This module also owns *tolerant name resolution*. A farmer's county, ward or
document name arrives from a form or a voice transcript, so it may differ from
the canonical spelling in case, spacing, punctuation or apostrophe style. Every
lookup here collapses the input to a comparison key (lowercase alphanumerics
only) before matching, so "Uasin Gishu", "uasin gishu" and "UASIN-GISHU" all
resolve to the same record. Matching is exact on that key - never fuzzy - so
the engine stays deterministic.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from typing import Any

from .config import COUNTIES_FILE, DEPOTS_FILE, SCHEME_RULES_FILE


def lookup_key(name: str) -> str:
    """
    Collapse a name to its comparison key: lowercase alphanumerics only.

    Mirrors `scripts/build_data.py::lookup_key` so the keys baked into
    counties.json line up with keys computed from live request data.
    """
    text = unicodedata.normalize("NFKD", name or "")
    text = text.replace("’", "'").replace("‘", "'")
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _load(path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


# --------------------------------------------------------------------------
# Geography
# --------------------------------------------------------------------------

_COUNTIES_DOC: dict[str, Any] = _load(COUNTIES_FILE)
COUNTIES: list[dict[str, Any]] = _COUNTIES_DOC["counties"]
GEO_TOTALS: dict[str, int] = _COUNTIES_DOC["totals"]

# county key -> county record
_COUNTY_INDEX: dict[str, dict[str, Any]] = {c["lookup_key"]: c for c in COUNTIES}

# (county key, constituency key) -> constituency record
_CONSTITUENCY_INDEX: dict[tuple[str, str], dict[str, Any]] = {
    (county["lookup_key"], constituency["lookup_key"]): constituency
    for county in COUNTIES
    for constituency in county["constituencies"]
}

# (county key, constituency key, ward key) -> ward record
_WARD_INDEX: dict[tuple[str, str, str], dict[str, Any]] = {
    (county["lookup_key"], constituency["lookup_key"], ward["lookup_key"]): ward
    for county in COUNTIES
    for constituency in county["constituencies"]
    for ward in constituency["wards"]
}


def find_county(name: str) -> dict[str, Any] | None:
    return _COUNTY_INDEX.get(lookup_key(name))


def find_constituency(county: str, constituency: str) -> dict[str, Any] | None:
    return _CONSTITUENCY_INDEX.get((lookup_key(county), lookup_key(constituency)))


def find_ward(county: str, constituency: str, ward: str) -> dict[str, Any] | None:
    return _WARD_INDEX.get(
        (lookup_key(county), lookup_key(constituency), lookup_key(ward))
    )


def county_names() -> list[str]:
    return [c["county_name"] for c in COUNTIES]


def constituency_names(county: str) -> list[str]:
    record = find_county(county)
    if record is None:
        return []
    return [c["constituency_name"] for c in record["constituencies"]]


def ward_names(county: str, constituency: str) -> list[str]:
    record = find_constituency(county, constituency)
    if record is None:
        return []
    return [w["ward_name"] for w in record["wards"]]


def geo_hierarchy() -> dict[str, Any]:
    """The full cascading-dropdown payload served by GET /api/geo/hierarchy."""
    return _COUNTIES_DOC


# --------------------------------------------------------------------------
# Scheme rules
# --------------------------------------------------------------------------

SCHEME: dict[str, Any] = _load(SCHEME_RULES_FILE)

PRICING: dict[str, Any] = SCHEME["pricing"]
ALLOCATION: dict[str, Any] = SCHEME["allocation"]
REQUIRED_DOCUMENTS: list[dict[str, Any]] = SCHEME["required_documents"]
CONDITIONAL_DOCUMENTS: list[dict[str, Any]] = SCHEME["conditional_documents"]
REJECTION_CRITERIA: list[dict[str, Any]] = SCHEME["rejection_criteria"]
CROP_SCOPE: dict[str, Any] = SCHEME["gazetted_crop_scope"]
PAYMENT_AT_DEPOT: dict[str, Any] = SCHEME["payment_at_depot"]

# Document alias key -> canonical document code. Built from both the mandatory
# and the conditional document definitions, plus each document's own code and
# label, so a client may send a code, a human label or any listed alias.
_DOCUMENT_ALIAS_INDEX: dict[str, str] = {}
for _doc in (*REQUIRED_DOCUMENTS, *CONDITIONAL_DOCUMENTS):
    for _candidate in (_doc["code"], _doc["label"], *_doc.get("aliases", [])):
        _DOCUMENT_ALIAS_INDEX[lookup_key(_candidate)] = _doc["code"]

# Document code -> definition, for both mandatory and conditional documents.
_DOCUMENT_BY_CODE: dict[str, dict[str, Any]] = {
    doc["code"]: doc for doc in (*REQUIRED_DOCUMENTS, *CONDITIONAL_DOCUMENTS)
}

# Disqualifying-item alias key -> rejection criterion code. A farmer "holding" a
# photocopy or an expired voucher is not holding a valid document; it actively
# triggers a documented refusal at the depot counter.
_REJECTION_TRIGGER_INDEX: dict[str, str] = {}
for _criterion in REJECTION_CRITERIA:
    for _trigger in _criterion.get("triggered_by_documents", []):
        _REJECTION_TRIGGER_INDEX[lookup_key(_trigger)] = _criterion["code"]

_REJECTION_BY_CODE: dict[str, dict[str, Any]] = {
    criterion["code"]: criterion for criterion in REJECTION_CRITERIA
}

# Crop key -> canonical gazetted crop name, including the Swahili and colloquial
# aliases declared in the circular's schedule.
_CROP_INDEX: dict[str, str] = {
    lookup_key(crop): crop for crop in CROP_SCOPE["eligible_crops"]
}
for _alias, _canonical in CROP_SCOPE.get("crop_aliases", {}).items():
    _CROP_INDEX[lookup_key(_alias)] = _canonical


def resolve_document(raw: str) -> str | None:
    """Map a client-supplied document string to a canonical document code."""
    return _DOCUMENT_ALIAS_INDEX.get(lookup_key(raw))


def resolve_rejection_trigger(raw: str) -> str | None:
    """Map a client-supplied string to a rejection criterion it triggers."""
    return _REJECTION_TRIGGER_INDEX.get(lookup_key(raw))


def document_definition(code: str) -> dict[str, Any] | None:
    return _DOCUMENT_BY_CODE.get(code)


def document_label(code: str) -> str:
    definition = _DOCUMENT_BY_CODE.get(code)
    return definition["label"] if definition else code


def rejection_criterion(code: str) -> dict[str, Any] | None:
    return _REJECTION_BY_CODE.get(code)


def resolve_crop(raw: str) -> str | None:
    """Map a declared crop to its canonical gazetted name, or None if outside scope."""
    return _CROP_INDEX.get(lookup_key(raw))


# --------------------------------------------------------------------------
# Depots
# --------------------------------------------------------------------------

_DEPOTS_DOC: dict[str, Any] = _load(DEPOTS_FILE)
DEPOTS: list[dict[str, Any]] = _DEPOTS_DOC["depots"]
DEPOT_NETWORK_META: dict[str, Any] = {
    key: value for key, value in _DEPOTS_DOC.items() if key != "depots"
}
STATUS_DEFINITIONS: dict[str, Any] = _DEPOTS_DOC["status_definitions"]

_DEPOT_INDEX: dict[str, dict[str, Any]] = {d["depot_id"]: d for d in DEPOTS}

# Depot ids are also accepted case-insensitively and punctuation-insensitively,
# so "NCPB Eldoret" and "ncpb_eldoret" both resolve.
_DEPOT_ALIAS_INDEX: dict[str, str] = {}
for _depot in DEPOTS:
    for _candidate in (_depot["depot_id"], _depot["name"]):
        _DEPOT_ALIAS_INDEX[lookup_key(_candidate)] = _depot["depot_id"]


def find_depot(depot_id: str) -> dict[str, Any] | None:
    if depot_id in _DEPOT_INDEX:
        return _DEPOT_INDEX[depot_id]
    resolved = _DEPOT_ALIAS_INDEX.get(lookup_key(depot_id))
    return _DEPOT_INDEX.get(resolved) if resolved else None


def depot_serves_farmers(depot: dict[str, Any]) -> bool:
    """True only for statuses the depot network marks as serving farmers."""
    definition = STATUS_DEFINITIONS.get(depot["status"])
    return bool(definition and definition["serves_farmers"])


def depot_status_label(depot: dict[str, Any]) -> str:
    definition = STATUS_DEFINITIONS.get(depot["status"])
    return definition["label"] if definition else depot["status"]


def depot_covers_county(depot: dict[str, Any], county: str) -> bool:
    key = lookup_key(county)
    return any(lookup_key(c) == key for c in depot["catchment_counties"])


def list_depots(county: str | None = None) -> list[dict[str, Any]]:
    """All depots, or only those whose catchment includes `county`."""
    if county is None:
        return list(DEPOTS)
    return [d for d in DEPOTS if depot_covers_county(d, county)]


@lru_cache(maxsize=64)
def serving_depots_for_county(county: str) -> tuple[dict[str, Any], ...]:
    """
    Depots in a county's catchment that are currently serving farmers.

    Used to offer a concrete alternative when the chosen depot cannot serve the
    farmer. This is government depot routing, not a vendor listing.
    """
    return tuple(
        d
        for d in DEPOTS
        if depot_covers_county(d, county) and depot_serves_farmers(d)
    )
