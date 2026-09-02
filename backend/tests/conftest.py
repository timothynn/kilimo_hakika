from __future__ import annotations

import json
import pathlib
from datetime import date
from decimal import Decimal

import pytest

from kilimo_hakika.engine import RulePack, TriageInput, load

FIXTURE = pathlib.Path(__file__).resolve().parents[2] / "database" / "rule_pack.json"

# Everything a farmer needs for the seeded 2026 short rains season.
ALL_REQUIRED = frozenset(
    {
        "NATIONAL_ID_ORIGINAL",
        "FARMER_REGISTER_ENTRY",
        "KIAMIS_REGISTRATION",
        "EVOUCHER_CODE",
        "NON_CASH_PAYMENT_MEANS",
    }
)

# A Wednesday inside the seeded season window.
TRAVEL_DATE = date(2026, 9, 2)


@pytest.fixture(scope="session")
def payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def pack(payload: dict) -> RulePack:
    return load(payload)


def make_input(**overrides) -> TriageInput:
    base = {
        "acreage_acres": Decimal("2"),
        "depot_code": "NCPB-NAKURU",
        "held_documents": ALL_REQUIRED,
        "travel_date": TRAVEL_DATE,
        "registration_county_code": "032",  # Nakuru, matching the depot
    }
    base.update(overrides)
    if not isinstance(base["held_documents"], frozenset):
        base["held_documents"] = frozenset(base["held_documents"])
    if not isinstance(base["acreage_acres"], Decimal):
        base["acreage_acres"] = Decimal(str(base["acreage_acres"]))
    return TriageInput(**base)
