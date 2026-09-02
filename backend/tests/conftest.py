"""Shared fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
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
