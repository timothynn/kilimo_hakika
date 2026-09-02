#!/usr/bin/env python
"""
End-to-end verification of the Kilimo Hakika triage API.

Walks every endpoint and exercises POST /api/triage with a passing case and a
range of failing cases, printing what it asserted so the output doubles as a
readable demo of the engine's behaviour.

Usage
-----
In-process (no server needed):
    python verify.py

Against a running server:
    uvicorn main:app --reload --port 8000     # in another terminal
    python verify.py --url http://localhost:8000

Exit code is 0 when every check passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

GREEN = "\033[32m"
RED = "\033[31m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

_failures: list[str] = []
_checks = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global _checks
    _checks += 1
    if condition:
        print(f"  {GREEN}PASS{RESET}  {label}")
    else:
        print(f"  {RED}FAIL{RESET}  {label}" + (f"  {DIM}{detail}{RESET}" if detail else ""))
        _failures.append(label)


def heading(text: str) -> None:
    print(f"\n{BOLD}{text}{RESET}")


def build_client(url: str | None):
    """A live httpx client when --url is given, else an in-process TestClient."""
    if url:
        import httpx

        return httpx.Client(base_url=url.rstrip("/"), timeout=15.0)

    from fastapi.testclient import TestClient

    from main import app

    return TestClient(app)


# --------------------------------------------------------------------------
# Cases
# --------------------------------------------------------------------------

PASSING_CASE: dict[str, Any] = {
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

FAILING_CASE: dict[str, Any] = {
    "county": "Busia",
    "constituency": "Matayos",
    "ward": "Matayos South",
    "target_depot_id": "ncpb_bungoma",
    "acreage": 3.0,
    "crop_type": "maize",
    # A photocopy instead of the original ID, an expired voucher, no WAO form,
    # and leased land with no stamped lease.
    "documents_held": ["ID Photocopy", "expired voucher"],
    "is_land_leased": True,
    "has_stamped_lease": False,
}


def verify_reference_endpoints(client) -> None:
    heading("1. Reference endpoints")

    health = client.get("/health")
    check("GET /health returns 200", health.status_code == 200)
    body = health.json()
    check("health reports status 'ok'", body.get("status") == "ok")
    check(
        "47 counties / 290 constituencies / 1450 wards loaded",
        body["data_loaded"]["counties"] == 47
        and body["data_loaded"]["constituencies"] == 290
        and body["data_loaded"]["wards"] == 1450,
        str(body.get("data_loaded")),
    )
    check("depot network loaded", body["data_loaded"]["depots"] > 0)

    hierarchy = client.get("/api/geo/hierarchy")
    check("GET /api/geo/hierarchy returns 200", hierarchy.status_code == 200)
    counties = hierarchy.json()["counties"]
    check("hierarchy contains 47 counties", len(counties) == 47)
    check(
        "hierarchy is nested county -> constituency -> ward",
        bool(counties[0]["constituencies"][0]["wards"][0]["ward_name"]),
    )

    matayos = client.get(
        "/api/geo/wards", params={"county": "Busia", "constituency": "Matayos"}
    ).json()
    ward_names = [w["ward_name"] for w in matayos["wards"]]
    check(
        "merged ward 'MATAYOS SOUTHBUSIBWABO' is split into two wards",
        "Matayos South" in ward_names and "Busibwabo" in ward_names,
        str(ward_names),
    )

    nyeri = next(c for c in counties if c["county_name"] == "Nyeri")
    tetu_count = sum(
        1 for c in nyeri["constituencies"] if c["constituency_name"] == "Tetu"
    )
    check("duplicate Nyeri 'Tetu' constituency de-duplicated", tetu_count == 1)

    depots = client.get("/api/depots")
    check("GET /api/depots returns 200", depots.status_code == 200)
    check(
        "all listed depots are Government (NCPB) depots",
        all(d["depot_id"].startswith("ncpb_") for d in depots.json()["depots"]),
    )

    filtered = client.get("/api/depots", params={"county": "Nandi"}).json()
    check(
        "?county= filters on catchment (NCPB Eldoret serves Nandi)",
        "ncpb_eldoret" in [d["depot_id"] for d in filtered["depots"]],
    )

    scheme = client.get("/api/schemes/current")
    check("GET /api/schemes/current returns 200", scheme.status_code == 200)
    scheme_body = scheme.json()
    check(
        "price is the statutory KES 2,500 per 50kg bag",
        scheme_body["pricing"]["price_per_bag_kes"] == 2500
        and scheme_body["pricing"]["bag_weight_kg"] == 50,
    )
    check(
        "allocation is 2 planting + 2 top-dressing per acre, capped at 100 bags",
        scheme_body["allocation"]["bags_per_acre_planting"] == 2
        and scheme_body["allocation"]["bags_per_acre_top_dressing"] == 2
        and scheme_body["allocation"]["max_bags_per_farmer"] == 100,
    )
    check(
        "3 mandatory documents, 1 conditional, 3 rejection criteria",
        len(scheme_body["required_documents"]) == 3
        and len(scheme_body["conditional_documents"]) == 1
        and len(scheme_body["rejection_criteria"]) == 3,
    )

    docs = client.get("/docs")
    check("Swagger UI is served at /docs", docs.status_code == 200)
    check("OpenAPI schema is served", client.get("/openapi.json").status_code == 200)


def verify_passing_case(client) -> None:
    heading("2. POST /api/triage - PASSING case")
    print(
        f"  {DIM}Uasin Gishu / Soy / Moi's Bridge -> NCPB Eldoret, 4.5 acres, "
        f"maize, all 3 documents, owned land{RESET}"
    )

    response = client.post("/api/triage", json=PASSING_CASE)
    check("returns 200", response.status_code == 200, response.text[:300])
    if response.status_code != 200:
        return

    body = response.json()
    verdict = body["verdict"]
    breakdown = body["financial_breakdown"]
    grounding = body["policy_grounding"]

    print(f"  {DIM}verdict: {verdict['summary']}{RESET}")

    check("will_be_served is True", verdict["will_be_served"] is True)
    check("status is PROCEED", verdict["status"] == "PROCEED")
    check("no missing documents", body["gap_analysis"]["missing_documents"] == [])
    check("no rejection reasons", body["gap_analysis"]["rejection_reasons"] == [])
    check(
        "allocated_bags is 18 (4.5 acres x 4 bags/acre)",
        breakdown["allocated_bags"] == 18,
        str(breakdown["allocated_bags"]),
    )
    check("price_per_bag is 2500", breakdown["price_per_bag"] == 2500)
    check(
        "total_cost_kes is 45,000 (18 x 2,500)",
        breakdown["total_cost_kes"] == 45_000,
        str(breakdown["total_cost_kes"]),
    )
    check(
        "statutory notice states no payments are processed",
        "does not process payments" in breakdown["statutory_notice"],
    )
    check(
        "grounded in MOALD Circular 2026/02 and NCPB Circular 4B",
        grounding["circular"] == "MOALD Circular 2026/02"
        and grounding["operating_procedure"] == "NCPB Circular 4B",
    )
    check("depot status reported as ACTIVE", grounding["depot_status"].startswith("ACTIVE"))


def verify_failing_case(client) -> None:
    heading("3. POST /api/triage - FAILING case")
    print(
        f"  {DIM}Busia / Matayos / Matayos South -> NCPB Bungoma, 3 acres, maize, "
        f"ID photocopy + expired voucher, leased land with no stamped lease{RESET}"
    )

    response = client.post("/api/triage", json=FAILING_CASE)
    check("returns 200 (a verdict, not an error)", response.status_code == 200)
    if response.status_code != 200:
        return

    body = response.json()
    verdict = body["verdict"]
    gaps = body["gap_analysis"]
    reasons = " ".join(gaps["rejection_reasons"])

    print(f"  {DIM}verdict: {verdict['summary'][:220]}...{RESET}")

    check("will_be_served is False", verdict["will_be_served"] is False)
    check("status is DO_NOT_TRAVEL", verdict["status"] == "DO_NOT_TRAVEL")
    check(
        "all four missing documents are listed",
        len(gaps["missing_documents"]) == 4,
        str(gaps["missing_documents"]),
    )
    check(
        "ID photocopy is rejected",
        "photocopies" in reasons.lower(),
    )
    check("expired voucher is rejected", "void" in reasons.lower())
    check(
        "unstamped lease on leased land is rejected",
        "Section 3.2" in reasons,
    )
    check(
        "blockers are not short-circuited (>= 5 reasons)",
        len(gaps["rejection_reasons"]) >= 5,
        f"{len(gaps['rejection_reasons'])} reasons",
    )
    check(
        "every reason cites a circular clause",
        all(
            "MOALD Circular 2026/02" in r or "NCPB Circular 4B" in r
            for r in gaps["rejection_reasons"]
        ),
    )
    check(
        "entitlement is still reported (12 bags on 3 acres)",
        body["financial_breakdown"]["allocated_bags"] == 12,
        str(body["financial_breakdown"]["allocated_bags"]),
    )


def verify_edge_cases(client) -> None:
    heading("4. Policy edge cases")

    capped = client.post("/api/triage", json={**PASSING_CASE, "acreage": 40}).json()
    check(
        "40 acres capped at the statutory 100 bags",
        capped["financial_breakdown"]["allocated_bags"] == 100
        and capped["allocation_basis"]["cap_applied"] is True,
    )
    check("a capped farmer still gets PROCEED", capped["verdict"]["status"] == "PROCEED")

    tiny = client.post("/api/triage", json={**PASSING_CASE, "acreage": 0.1}).json()
    check(
        "0.1 acres yields 0 bags and DO_NOT_TRAVEL",
        tiny["financial_breakdown"]["allocated_bags"] == 0
        and tiny["verdict"]["status"] == "DO_NOT_TRAVEL",
    )

    closed = client.post(
        "/api/triage",
        json={
            **PASSING_CASE,
            "county": "Siaya",
            "constituency": "Alego Usonga",
            "ward": "West Alego",
            "target_depot_id": "ncpb_siaya",
        },
    ).json()
    check(
        "a stock-depleted depot yields DO_NOT_TRAVEL",
        closed["verdict"]["status"] == "DO_NOT_TRAVEL",
    )
    check(
        "and suggests serving Government alternatives",
        bool(closed["alternative_depots"])
        and all(d["serves_farmers"] for d in closed["alternative_depots"]),
    )

    wrong_catchment = client.post(
        "/api/triage", json={**PASSING_CASE, "target_depot_id": "ncpb_mombasa_changamwe"}
    ).json()
    check(
        "a depot outside the farmer's catchment yields DO_NOT_TRAVEL",
        wrong_catchment["verdict"]["status"] == "DO_NOT_TRAVEL",
    )

    leased_ok = client.post(
        "/api/triage",
        json={**PASSING_CASE, "is_land_leased": True, "has_stamped_lease": True},
    ).json()
    check(
        "leased land with a Chief's stamped lease proceeds",
        leased_ok["verdict"]["status"] == "PROCEED",
    )

    leased_bad = client.post(
        "/api/triage",
        json={**PASSING_CASE, "is_land_leased": True, "has_stamped_lease": False},
    ).json()
    check(
        "leased land without a stamped lease is blocked",
        leased_bad["verdict"]["status"] == "DO_NOT_TRAVEL",
    )

    aliased = client.post(
        "/api/triage",
        json={
            **PASSING_CASE,
            "county": "uasin gishu",
            "ward": "mois bridge",
            "documents_held": ["kitambulisho", "sms code", "wao form"],
        },
    ).json()
    check(
        "names and documents match case- and punctuation-insensitively",
        aliased["verdict"]["status"] == "PROCEED",
    )

    first = client.post("/api/triage", json=PASSING_CASE).json()
    repeats = [client.post("/api/triage", json=PASSING_CASE).json() for _ in range(5)]
    check("engine is deterministic across repeated calls", all(r == first for r in repeats))


def verify_compliance(client) -> None:
    heading("5. Track compliance")

    advice = client.post(
        "/api/triage",
        json={**PASSING_CASE, "crop_type": "what fertilizer is best for maize?"},
    )
    check(
        "an agronomic question is refused with 422",
        advice.status_code == 422,
        str(advice.status_code),
    )
    if advice.status_code == 422:
        detail = advice.json()["detail"]
        check(
            "refusal is explicit and redirects to the WAO",
            detail.get("error") == "agronomic_advice_refused"
            and "Ward Agricultural Officer" in detail["message"],
        )
        check("refusal leaks no partial verdict", "verdict" not in advice.json())

    plain = client.post("/api/triage", json={**PASSING_CASE, "crop_type": "maize"})
    check("a plain crop name is accepted", plain.status_code == 200)

    body = client.post("/api/triage", json=PASSING_CASE).json()
    check(
        "every verdict carries the three scope boundaries",
        set(body["compliance"]) == {
            "no_agronomic_advice",
            "no_payments",
            "no_marketplace",
        },
    )

    schema = client.get("/openapi.json").json()
    paths = " ".join(schema["paths"]).lower()
    check(
        "no payment / marketplace routes exist",
        not any(
            token in paths
            for token in ("pay", "mpesa", "checkout", "cart", "order", "vendor", "market")
        ),
    )

    text = " ".join([body["verdict"]["summary"], *body["next_steps"]]).lower()
    check(
        "no payment or e-commerce language in the verdict",
        not any(t in text for t in ("m-pesa", "mpesa", "checkout", "add to cart")),
    )


def verify_error_handling(client) -> None:
    heading("6. Error handling")

    unknown_county = client.post("/api/triage", json={**PASSING_CASE, "county": "Wakanda"})
    check("unknown county returns 422", unknown_county.status_code == 422)
    if unknown_county.status_code == 422:
        detail = unknown_county.json()["detail"]
        check(
            "and lists valid counties to choose from",
            "Uasin Gishu" in detail.get("valid_options", []),
        )

    bad_ward = client.post("/api/triage", json={**PASSING_CASE, "ward": "Kabiyet"})
    check(
        "a ward outside the named constituency returns 422",
        bad_ward.status_code == 422,
    )

    bad_depot = client.post(
        "/api/triage", json={**PASSING_CASE, "target_depot_id": "ncpb_atlantis"}
    )
    check("unknown depot returns 404", bad_depot.status_code == 404)

    bad_acreage = client.post("/api/triage", json={**PASSING_CASE, "acreage": 0})
    check("zero acreage is rejected by validation", bad_acreage.status_code == 422)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=None,
        help="Base URL of a running server, e.g. http://localhost:8000. "
        "Omit to run in-process.",
    )
    args = parser.parse_args()

    mode = f"live server at {args.url}" if args.url else "in-process (TestClient)"
    print(f"{BOLD}Kilimo Hakika (DepotReady) - API verification{RESET}")
    print(f"{DIM}mode: {mode}{RESET}")

    client = build_client(args.url)

    verify_reference_endpoints(client)
    verify_passing_case(client)
    verify_failing_case(client)
    verify_edge_cases(client)
    verify_compliance(client)
    verify_error_handling(client)

    print()
    if _failures:
        print(f"{RED}{BOLD}{len(_failures)} of {_checks} checks FAILED{RESET}")
        for failure in _failures:
            print(f"  {RED}- {failure}{RESET}")
        return 1

    print(f"{GREEN}{BOLD}All {_checks} checks passed.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
