"""HTTP-level tests: status codes, response contract, CORS and docs."""

from __future__ import annotations

import pytest

from app import repository as repo


# --------------------------------------------------------------------------
# Health and index
# --------------------------------------------------------------------------


def test_health_reports_ok_and_loaded_data(client):
    response = client.get("/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["scheme_id"] == "fertilizer_subsidy_2026"
    assert body["data_loaded"]["counties"] == 47
    assert body["data_loaded"]["constituencies"] == 290
    assert body["data_loaded"]["wards"] == 1450
    assert body["data_loaded"]["depots"] == len(repo.DEPOTS)
    assert set(body["track_constraints"]) == {
        "no_agronomic_advice",
        "no_payments",
        "no_marketplace",
    }


def test_root_redirects_to_the_swagger_docs(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/docs"


def test_api_index_lists_every_endpoint(client):
    body = client.get("/api").json()
    assert body["endpoints"]["triage"] == "POST /api/triage"
    assert body["docs"]["swagger"] == "/docs"


# --------------------------------------------------------------------------
# OpenAPI / Swagger - the frontend developer's entry point
# --------------------------------------------------------------------------


def test_swagger_ui_is_served(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower()


def test_openapi_schema_documents_all_endpoints(client):
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]

    assert "/health" in paths
    assert "/api/geo/hierarchy" in paths
    assert "/api/depots" in paths
    assert "/api/schemes/current" in paths
    assert "post" in paths["/api/triage"]


def test_triage_schema_carries_a_worked_example(client):
    """The example is what makes /docs immediately usable via 'Try it out'."""
    schema = client.get("/openapi.json").json()
    request_schema = schema["components"]["schemas"]["TriageRequest"]

    assert "examples" in request_schema
    example = request_schema["examples"][0]
    assert example["county"] == "Uasin Gishu"
    assert example["target_depot_id"] == "ncpb_eldoret"


# --------------------------------------------------------------------------
# CORS
# --------------------------------------------------------------------------


def test_cors_allows_any_frontend_origin(client):
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "*"


def test_cors_preflight_permits_the_triage_post(client):
    response = client.options(
        "/api/triage",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"


# --------------------------------------------------------------------------
# Geography
# --------------------------------------------------------------------------


def test_geo_hierarchy_is_shaped_for_cascading_dropdowns(client):
    body = client.get("/api/geo/hierarchy").json()

    assert body["totals"] == {"counties": 47, "constituencies": 290, "wards": 1450}
    assert len(body["counties"]) == 47

    county = body["counties"][0]
    assert {"county_code", "county_name", "lookup_key", "constituencies"} <= set(county)
    constituency = county["constituencies"][0]
    assert {"constituency_id", "constituency_name", "wards"} <= set(constituency)
    assert {"ward_id", "ward_name"} <= set(constituency["wards"][0])


def test_geo_counties_shortcut(client):
    body = client.get("/api/geo/counties").json()
    assert body["count"] == 47
    assert body["counties"][0]["county_name"] == "Mombasa"


def test_geo_wards_returns_one_constituencys_wards(client):
    body = client.get(
        "/api/geo/wards", params={"county": "Busia", "constituency": "Matayos"}
    ).json()

    names = [w["ward_name"] for w in body["wards"]]
    # The formerly merged pair, now correctly separate.
    assert "Matayos South" in names
    assert "Busibwabo" in names
    assert body["count"] == len(names)


def test_geo_wards_rejects_an_unknown_county(client):
    response = client.get(
        "/api/geo/wards", params={"county": "Wakanda", "constituency": "Matayos"}
    )
    assert response.status_code == 404
    assert response.json()["detail"]["field"] == "county"


# --------------------------------------------------------------------------
# Depots
# --------------------------------------------------------------------------


def test_depots_lists_the_whole_network(client):
    body = client.get("/api/depots").json()

    assert body["count"] == len(repo.DEPOTS)
    assert body["filtered_by_county"] is None
    assert "not a marketplace" in body["notice"]
    assert "ACTIVE" in body["status_definitions"]


def test_depots_filter_matches_catchment_not_location(client):
    """NCPB Eldoret stands in Uasin Gishu but serves Nandi, so it must appear."""
    body = client.get("/api/depots", params={"county": "Nandi"}).json()

    assert body["filtered_by_county"] == "Nandi"
    ids = [d["depot_id"] for d in body["depots"]]
    assert "ncpb_eldoret" in ids
    for depot in body["depots"]:
        assert "Nandi" in depot["catchment_counties"]


def test_depots_county_filter_is_case_insensitive(client):
    lower = client.get("/api/depots", params={"county": "uasin gishu"}).json()
    exact = client.get("/api/depots", params={"county": "Uasin Gishu"}).json()
    assert lower == exact


def test_depots_serving_only_filter(client):
    body = client.get(
        "/api/depots", params={"serving_only": True}
    ).json()
    assert all(d["serves_farmers"] for d in body["depots"])
    assert body["count"] < len(repo.DEPOTS), "fixture should include closed depots"


def test_depots_rejects_an_unknown_county(client):
    response = client.get("/api/depots", params={"county": "Atlantis"})
    assert response.status_code == 404
    assert response.json()["detail"]["field"] == "county"


def test_single_depot_lookup(client):
    body = client.get("/api/depots/ncpb_eldoret").json()
    assert body["name"] == "NCPB Eldoret Depot"
    assert body["serves_farmers"] is True
    assert body["status_label"]


def test_single_depot_lookup_404(client):
    assert client.get("/api/depots/ncpb_atlantis").status_code == 404


def test_every_listed_depot_is_a_government_depot(client):
    """Constraint 3: no third-party or vendor entries may appear."""
    body = client.get("/api/depots").json()
    for depot in body["depots"]:
        assert depot["depot_id"].startswith("ncpb_")
        assert depot["name"].startswith("NCPB ")


# --------------------------------------------------------------------------
# Scheme
# --------------------------------------------------------------------------


def test_current_scheme_exposes_the_full_circular(client):
    body = client.get("/api/schemes/current").json()

    assert body["scheme_id"] == "fertilizer_subsidy_2026"
    assert (
        body["source_citation"]
        == "MOALD Circular 2026/02 & NCPB Operating Circular 4B"
    )
    assert body["pricing"]["price_per_bag_kes"] == 2500
    assert body["pricing"]["bag_weight_kg"] == 50
    assert body["allocation"]["bags_per_acre_planting"] == 2
    assert body["allocation"]["bags_per_acre_top_dressing"] == 2
    assert body["allocation"]["max_bags_per_farmer"] == 100

    assert len(body["required_documents"]) == 3
    assert len(body["conditional_documents"]) == 1
    assert len(body["rejection_criteria"]) == 3


def test_scheme_declares_that_payments_are_disabled(client):
    body = client.get("/api/schemes/current").json()
    assert body["compliance"]["payments_enabled"] is False
    assert body["compliance"]["marketplace_enabled"] is False
    assert body["compliance"]["agronomic_advice_provided"] is False


# --------------------------------------------------------------------------
# Triage over HTTP
# --------------------------------------------------------------------------


def test_triage_passing_case_returns_the_full_contract(client, passing_request):
    response = client.post("/api/triage", json=passing_request)
    assert response.status_code == 200

    body = response.json()
    # The four blocks required by the specification, with exact field sets.
    assert set(body["verdict"]) == {"will_be_served", "status", "summary"}
    assert set(body["gap_analysis"]) == {"missing_documents", "rejection_reasons"}
    assert set(body["financial_breakdown"]) == {
        "allocated_bags",
        "price_per_bag",
        "total_cost_kes",
        "statutory_notice",
    }
    assert set(body["policy_grounding"]) == {
        "circular",
        "depot_status",
        "operating_procedure",
    }

    assert body["verdict"]["will_be_served"] is True
    assert body["verdict"]["status"] == "PROCEED"
    assert body["financial_breakdown"]["allocated_bags"] == 18
    assert body["financial_breakdown"]["total_cost_kes"] == 45_000


def test_triage_failing_case_over_http(client, passing_request):
    payload = {
        **passing_request,
        "documents_held": ["ID Photocopy"],
        "is_land_leased": True,
        "has_stamped_lease": False,
    }
    response = client.post("/api/triage", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["verdict"]["will_be_served"] is False
    assert body["verdict"]["status"] == "DO_NOT_TRAVEL"
    assert body["gap_analysis"]["rejection_reasons"]
    assert body["gap_analysis"]["missing_documents"]
    # Entitlement is still reported, so the farmer knows what they are owed.
    assert body["financial_breakdown"]["allocated_bags"] == 18


def test_status_always_agrees_with_will_be_served(client, passing_request):
    cases = [
        passing_request,
        {**passing_request, "documents_held": []},
        {**passing_request, "acreage": 0.05},
        {**passing_request, "target_depot_id": "ncpb_mombasa_changamwe"},
    ]
    for payload in cases:
        body = client.post("/api/triage", json=payload).json()
        expected = "PROCEED" if body["verdict"]["will_be_served"] else "DO_NOT_TRAVEL"
        assert body["verdict"]["status"] == expected


def test_triage_optional_fields_default_to_the_conservative_case(client):
    """
    Omitting documents_held / is_land_leased / has_stamped_lease must never
    produce a PROCEED it did not earn.
    """
    response = client.post(
        "/api/triage",
        json={
            "county": "Uasin Gishu",
            "constituency": "Soy",
            "ward": "Moi's Bridge",
            "target_depot_id": "ncpb_eldoret",
            "acreage": 2,
            "crop_type": "maize",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"]["status"] == "DO_NOT_TRAVEL"
    assert len(body["gap_analysis"]["missing_documents"]) == 3


@pytest.mark.parametrize("acreage", [0, -1, -0.5])
def test_non_positive_acreage_is_rejected_by_validation(client, passing_request, acreage):
    response = client.post(
        "/api/triage", json={**passing_request, "acreage": acreage}
    )
    assert response.status_code == 422


def test_missing_required_field_is_rejected(client, passing_request):
    payload = dict(passing_request)
    del payload["target_depot_id"]
    assert client.post("/api/triage", json=payload).status_code == 422


def test_unknown_location_returns_422_with_valid_options(client, passing_request):
    response = client.post(
        "/api/triage", json={**passing_request, "county": "Wakanda"}
    )
    assert response.status_code == 422

    detail = response.json()["detail"]
    assert detail["field"] == "county"
    assert "Uasin Gishu" in detail["valid_options"]


def test_unknown_depot_returns_404(client, passing_request):
    response = client.post(
        "/api/triage", json={**passing_request, "target_depot_id": "ncpb_atlantis"}
    )
    assert response.status_code == 404
    assert response.json()["detail"]["field"] == "target_depot_id"


def test_ward_outside_constituency_returns_422_listing_real_wards(client, passing_request):
    response = client.post(
        "/api/triage", json={**passing_request, "ward": "Kabiyet"}
    )
    assert response.status_code == 422

    detail = response.json()["detail"]
    assert detail["field"] == "ward"
    assert "Moi's Bridge" in detail["valid_options"]


# --------------------------------------------------------------------------
# Constraint 1 - agronomic advice is refused, not answered
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "crop_type",
    [
        "what fertilizer should I use for maize?",
        "best fertilizer for beans",
        "which crop should I plant this season",
        "recommend a top dressing rate for my maize",
        "maize - how much DAP per acre",
        "soil ph for wheat",
        "is my soil suitable for rice",
    ],
)
def test_agronomic_questions_are_refused_with_422(client, passing_request, crop_type):
    response = client.post(
        "/api/triage", json={**passing_request, "crop_type": crop_type}
    )
    assert response.status_code == 422

    detail = response.json()["detail"]
    assert detail["error"] == "agronomic_advice_refused"
    assert "cannot answer agronomic questions" in detail["message"]
    assert "Ward Agricultural Officer" in detail["message"]


@pytest.mark.parametrize(
    "crop_type", ["maize", "Mahindi", "irish potatoes", "finger millet", "green grams"]
)
def test_plain_crop_names_are_not_mistaken_for_advice_requests(
    client, passing_request, crop_type
):
    response = client.post(
        "/api/triage", json={**passing_request, "crop_type": crop_type}
    )
    assert response.status_code == 200


def test_a_refused_request_returns_no_verdict_at_all(client, passing_request):
    """A refusal must not leak a partial answer."""
    body = client.post(
        "/api/triage",
        json={**passing_request, "crop_type": "what is the best fertilizer?"},
    ).json()

    assert "verdict" not in body
    assert "financial_breakdown" not in body


# --------------------------------------------------------------------------
# Constraint 2 & 3 - structural absence
# --------------------------------------------------------------------------


def test_no_payment_or_marketplace_endpoints_exist(client):
    """
    Constraints 2 and 3 are structural: the routes simply do not exist. This
    guards against one being added by accident.
    """
    schema = client.get("/openapi.json").json()
    paths = " ".join(schema["paths"]).lower()

    for forbidden in (
        "pay",
        "mpesa",
        "m-pesa",
        "checkout",
        "order",
        "cart",
        "transaction",
        "vendor",
        "listing",
        "seller",
        "market",
    ):
        assert forbidden not in paths, f"unexpected route segment: {forbidden}"


def test_triage_response_exposes_no_payment_fields(client, passing_request):
    body = client.post("/api/triage", json=passing_request).json()
    breakdown = body["financial_breakdown"]

    for forbidden in ("payment_url", "checkout_url", "paybill", "till_number", "phone"):
        assert forbidden not in breakdown


# --------------------------------------------------------------------------
# Statutory payment rule over HTTP
# --------------------------------------------------------------------------


def test_payment_notice_is_returned_on_proceed(client, passing_request):
    body = client.post("/api/triage", json=passing_request).json()
    assert body["verdict"]["status"] == "PROCEED"

    notice = body["payment_notice"]
    assert set(notice) == {
        "headline",
        "notice",
        "accepted_means",
        "authority",
        "cash_accepted_at_depot",
    }
    assert notice["cash_accepted_at_depot"] is False
    assert "NCPB Operating Circular 4B, Section 5.1" == notice["authority"]


def test_scheme_endpoint_publishes_the_payment_rule(client):
    body = client.get("/api/schemes/current").json()
    assert body["payment_at_depot"]["cash_accepted_at_depot"] is False
    assert body["operating_procedure"] == "NCPB Operating Circular 4B"


def test_crop_type_is_optional_over_http(client, passing_request):
    payload = dict(passing_request)
    payload.pop("crop_type")

    response = client.post("/api/triage", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"]["status"] == "PROCEED"
    assert body["crop_within_gazetted_scope"] is None


def test_the_payment_rule_is_not_a_payment_integration(client, passing_request):
    """
    Naming a till number is an instruction. It must not become a field any
    client could transact against.
    """
    notice = client.post("/api/triage", json=passing_request).json()["payment_notice"]
    for forbidden in ("paybill", "till_number", "account_number", "phone", "stk", "url"):
        assert forbidden not in notice


def test_geo_constituencies_endpoint(client):
    body = client.get(
        "/api/geo/constituencies", params={"county": "Uasin Gishu"}
    ).json()
    assert body["county"] == "Uasin Gishu"
    assert body["count"] == 6
    names = [c["constituency_name"] for c in body["constituencies"]]
    assert "Soy" in names
    assert all(c["ward_count"] > 0 for c in body["constituencies"])


def test_geo_constituencies_rejects_unknown_county(client):
    response = client.get("/api/geo/constituencies", params={"county": "Wakanda"})
    assert response.status_code == 404
