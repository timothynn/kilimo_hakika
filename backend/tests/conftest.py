"""Shared fixtures.

`backend/` currently holds two Python services, built in parallel:

  - `app/` + `main.py` - the FastAPI triage service on this branch, tested
    through `client` / `passing_request` below.
  - `src/kilimo_hakika/` - the triage service with the policy database,
    identity model and assistant, tested through `pack` / `make_input`.

Both suites collect from this one directory, so both fixture sets live here.
That is a symptom, not a design: see docs/design/integration.md. When the two
are reconciled, whichever set belongs to the retired service goes with it.
"""

from __future__ import annotations

import json
import pathlib
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

# --- app/ + main.py service ------------------------------------------------


@pytest.fixture(scope="session")
def client() -> TestClient:
    # Imported lazily: a collection-time import would make every test in this
    # directory, including the engine tests below, fail if this service's
    # dependencies are missing.
    from main import app

    return TestClient(app)


# A request that should always pass triage: an active depot whose catchment
# covers the farmer's county, all three mandatory documents, owned land, and a
# gazetted crop. Individual tests copy this and break one thing at a time, so
# each failure is attributable to exactly one cause.
PASSING_REQUEST: dict = {
    "county": "Uasin Gishu",
    "constituency": "Soy",
    "ward": "Moi's Bridge",
    "target_depot_id": "ncpb_eldoret",
    "acreage": 4.5,
    "crop_type": "maize",
    "documents_held": [
        "Original National ID",
        "KIAMIS E-Voucher SMS Code",
        "Signed Ward Agricultural Officer (WAO) Form",
    ],
    "is_land_leased": False,
    "has_stamped_lease": False,
}


@pytest.fixture
def passing_request() -> dict:
    return dict(PASSING_REQUEST)


# --- src/kilimo_hakika service --------------------------------------------

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
def pack(payload: dict):
    from kilimo_hakika.engine import load

    return load(payload)


def make_input(**overrides):
    from kilimo_hakika.engine import TriageInput

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
