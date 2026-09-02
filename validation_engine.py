"""Kilimo Hakika (DepotReady) - deterministic subsidy eligibility triage.

Pure decision logic. The only I/O in this module is reading the rules file in
load_rules(). Every answer below is a direct read of scheme_rules.json: the
engine never extrapolates, estimates or guesses a figure that policy does not
state. Run this file directly to execute the self-check.
"""

from __future__ import annotations

import json
from pathlib import Path

PROCEED = "PROCEED"
DO_NOT_TRAVEL = "DO NOT TRAVEL"


def load_rules(path: str) -> dict:
    """Load the policy rules file. The only I/O in this module."""
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def check_documents(held: list[str], required: list[str]) -> dict:
    """Compare what the farmer holds against what the scheme requires.

    A document counts only on an exact match. Missing documents are listed in
    the order the policy lists them.
    """
    missing = [document for document in required if document not in held]
    return {"complete": not missing, "missing": missing}


def calculate_allocation(acreage: float, caps: list[dict]) -> dict:
    """Find the tier that contains `acreage` and price its bag cap.

    A tier matches when min_acres <= acreage <= max_acres. The first matching
    tier wins. If no tier matches - acreage above, below or between the defined
    tiers - the result is tier_matched=False with bag_cap=0 for manual review.
    No cap is ever extrapolated beyond the tiers policy defines.
    """
    for tier in caps:
        if tier["min_acres"] <= acreage <= tier["max_acres"]:
            bag_cap = int(tier["bag_cap"])
            return {
                "bag_cap": bag_cap,
                "total_cost_kes": int(bag_cap * tier["price_per_bag_kes"]),
                "tier_matched": True,
            }
    return {"bag_cap": 0, "total_cost_kes": 0, "tier_matched": False}


def get_status(documents_complete: bool) -> str:
    """Travel advice. Returns PROCEED or DO NOT TRAVEL and nothing else."""
    return PROCEED if documents_complete else DO_NOT_TRAVEL


def run_triage(
    scheme_id: str,
    acreage: float,
    depot: str,
    held_docs: list[str],
    rules: dict,
) -> dict:
    """One farmer, one scheme, one depot -> one auditable verdict.

    Raises ValueError for an unknown scheme_id or depot rather than returning a
    verdict that policy does not cover.
    """
    schemes = rules["schemes"]
    if scheme_id not in schemes:
        raise ValueError(f"Unknown scheme_id: {scheme_id!r}")
    if depot not in rules["depots"]:
        raise ValueError(f"Unknown depot: {depot!r}")

    scheme = schemes[scheme_id]
    documents = check_documents(held_docs, scheme["required_documents"])
    allocation = calculate_allocation(acreage, scheme["acreage_tiers"])
    return {
        "status": get_status(documents["complete"]),
        "missing_documents": documents["missing"],
        "bag_cap": allocation["bag_cap"],
        "total_cost_kes": allocation["total_cost_kes"],
        "tier_matched": allocation["tier_matched"],
        "source_circular": scheme["source_circular"],
    }


if __name__ == "__main__":
    rules = load_rules(str(Path(__file__).with_name("scheme_rules.json")))

    # Scenario 1: every required document held, acreage inside Tier 1.
    # Scenario 2: land document missing, acreage inside Tier 2.
    # Scenario 3: acreage exactly on the Tier 1 upper boundary (2.0 acres).
    scenarios = [
        (
            "clean PROCEED (1.5 acres, all 3 documents)",
            {
                "scheme_id": "FERT-SUB-2024",
                "acreage": 1.5,
                "depot": "DEP-ELD-01",
                "held_docs": [
                    "National ID card",
                    "Farmer registration number",
                    "Land ownership or lease document",
                ],
            },
            {
                "status": "PROCEED",
                "missing_documents": [],
                "bag_cap": 2,
                "total_cost_kes": 5000,
                "tier_matched": True,
                "source_circular": "MOALD Circular 2024/02",
            },
        ),
        (
            "missing document DO NOT TRAVEL (3.0 acres, land document absent)",
            {
                "scheme_id": "FERT-SUB-2024",
                "acreage": 3.0,
                "depot": "DEP-NKR-02",
                "held_docs": ["National ID card", "Farmer registration number"],
            },
            {
                "status": "DO NOT TRAVEL",
                "missing_documents": ["Land ownership or lease document"],
                "bag_cap": 5,
                "total_cost_kes": 12500,
                "tier_matched": True,
                "source_circular": "MOALD Circular 2024/02",
            },
        ),
        (
            "tier boundary (exactly 2.0 acres -> Tier 1, not Tier 2)",
            {
                "scheme_id": "SEED-SUB-2024",
                "acreage": 2.0,
                "depot": "DEP-KTL-03",
                "held_docs": [
                    "National ID card",
                    "Farmer registration number",
                    "Previous season delivery receipt",
                ],
            },
            {
                "status": "PROCEED",
                "missing_documents": [],
                "bag_cap": 1,
                "total_cost_kes": 1750,
                "tier_matched": True,
                "source_circular": "MOALD Circular 2024/07",
            },
        ),
    ]

    passed = 0
    for label, inputs, expected in scenarios:
        actual = run_triage(rules=rules, **inputs)
        if actual == expected:
            passed += 1
            print(f"PASS - {label}")
        else:
            print(f"FAIL - {label}")
            print(f"       expected: {expected}")
            print(f"       actual:   {actual}")

    print(f"{passed}/{len(scenarios)} PASS")
