"""
Tests for the deterministic triage engine.

Each test starts from `passing_request` and breaks exactly one thing, so a
failure points at a single rule.
"""

from __future__ import annotations

import pytest

from app import repository as repo
from app.triage import TriageInputError, run_triage

MANDATORY_DOCUMENTS = [
    "Original National ID",
    "KIAMIS E-Voucher SMS Code",
    "Signed Ward Agricultural Officer (WAO) Form",
]


def triage(**overrides):
    payload = {
        "county": "Uasin Gishu",
        "constituency": "Soy",
        "ward": "Moi's Bridge",
        "target_depot_id": "ncpb_eldoret",
        "acreage": 4.5,
        "crop_type": "maize",
        "documents_held": list(MANDATORY_DOCUMENTS),
        "is_land_leased": False,
        "has_stamped_lease": False,
    }
    payload.update(overrides)
    return run_triage(**payload)


# --------------------------------------------------------------------------
# The passing case
# --------------------------------------------------------------------------


def test_complete_application_at_an_active_depot_proceeds():
    result = triage()

    assert result["verdict"]["will_be_served"] is True
    assert result["verdict"]["status"] == "PROCEED"
    assert result["gap_analysis"]["missing_documents"] == []
    assert result["gap_analysis"]["rejection_reasons"] == []
    # 4.5 acres x 4 bags = 18 bags at KES 2,500 = KES 45,000
    assert result["financial_breakdown"]["allocated_bags"] == 18
    assert result["financial_breakdown"]["price_per_bag"] == 2500
    assert result["financial_breakdown"]["total_cost_kes"] == 45_000
    assert result["policy_grounding"]["circular"] == "MOALD Circular 2026/02"
    assert result["policy_grounding"]["operating_procedure"] == "NCPB Operating Circular 4B"
    assert result["policy_grounding"]["depot_status"].startswith("ACTIVE")


def test_proceed_offers_no_alternative_depots():
    """Alternatives are only for when the chosen depot is the problem."""
    assert triage()["alternative_depots"] == []


def test_location_is_resolved_to_canonical_names_and_official_ids():
    result = triage(county="uasin gishu", constituency="SOY", ward="mois bridge")
    location = result["resolved_location"]

    assert location["county"] == "Uasin Gishu"
    assert location["county_code"] == 27
    assert location["constituency"] == "Soy"
    assert location["ward"] == "Moi's Bridge"
    assert isinstance(location["ward_id"], int)


# --------------------------------------------------------------------------
# Allocation arithmetic
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("acreage", "expected_bags"),
    [
        (0.25, 1),      # exactly the minimum: 1 bag
        (0.5, 2),
        (1.0, 4),       # 2 planting + 2 top-dressing
        (2.0, 8),
        (4.5, 18),
        (7.3, 29),      # 29.2 floored
        (10.0, 40),
        (24.75, 99),
        (25.0, 100),    # the cap is reached exactly here
        (26.0, 100),    # capped
        (500.0, 100),   # still capped
    ],
)
def test_allocation_is_four_bags_per_acre_floored_and_capped(acreage, expected_bags):
    result = triage(acreage=acreage)
    assert result["financial_breakdown"]["allocated_bags"] == expected_bags
    assert result["financial_breakdown"]["total_cost_kes"] == expected_bags * 2500


def test_cap_is_flagged_in_the_allocation_basis():
    result = triage(acreage=40.0)
    basis = result["allocation_basis"]

    assert basis["uncapped_entitlement_bags"] == 160
    assert basis["max_bags_per_farmer"] == 100
    assert basis["cap_applied"] is True
    assert result["financial_breakdown"]["allocated_bags"] == 100
    # Being capped is not a reason to stay home.
    assert result["verdict"]["status"] == "PROCEED"


def test_cap_is_not_flagged_below_the_ceiling():
    assert triage(acreage=4.5)["allocation_basis"]["cap_applied"] is False


@pytest.mark.parametrize("acreage", [0.7, 2.35, 1.1, 3.3, 0.35])
def test_float_representation_error_does_not_shave_off_a_bag(acreage):
    """
    0.7 * 4 evaluates to 2.8000000000000003 in binary floating point; naive
    flooring of similar products can land a whole bag low.
    """
    import math

    result = triage(acreage=acreage)
    assert result["financial_breakdown"]["allocated_bags"] == math.floor(
        round(acreage * 4, 6)
    )


def test_acreage_below_the_minimum_cannot_be_served():
    result = triage(acreage=0.1)

    assert result["verdict"]["status"] == "DO_NOT_TRAVEL"
    assert result["financial_breakdown"]["allocated_bags"] == 0
    assert result["financial_breakdown"]["total_cost_kes"] == 0
    assert any(
        "does not attract a whole 50kg bag" in reason
        for reason in result["gap_analysis"]["rejection_reasons"]
    )


# --------------------------------------------------------------------------
# Missing documents
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("omitted", "expected_label"),
    [
        ("Original National ID", "Original National ID"),
        ("KIAMIS E-Voucher SMS Code", "KIAMIS E-Voucher SMS Code"),
        (
            "Signed Ward Agricultural Officer (WAO) Form",
            "Signed Ward Agricultural Officer (WAO) Form",
        ),
    ],
)
def test_each_mandatory_document_blocks_when_missing(omitted, expected_label):
    documents = [d for d in MANDATORY_DOCUMENTS if d != omitted]
    result = triage(documents_held=documents)

    assert result["verdict"]["status"] == "DO_NOT_TRAVEL"
    assert result["gap_analysis"]["missing_documents"] == [expected_label]


def test_no_documents_at_all_lists_all_three():
    result = triage(documents_held=[])

    assert result["verdict"]["will_be_served"] is False
    assert result["gap_analysis"]["missing_documents"] == MANDATORY_DOCUMENTS
    assert len(result["gap_analysis"]["rejection_reasons"]) == 3


def test_every_rejection_reason_cites_its_authority():
    """A farmer, or an officer checking the answer, must be able to trace it."""
    result = triage(documents_held=[])
    for reason in result["gap_analysis"]["rejection_reasons"]:
        assert "MOALD Circular 2026/02" in reason or "NCPB Operating Circular 4B" in reason


# --------------------------------------------------------------------------
# Document alias tolerance
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "documents",
    [
        ["original_national_id", "kiamis_evoucher_sms_code", "wao_signed_form"],
        ["national id", "e-voucher", "wao form"],
        ["ORIGINAL NATIONAL ID", "KIAMIS Code", "Signed WAO Form"],
        ["kitambulisho", "sms code", "ward agricultural officer form"],
    ],
)
def test_documents_are_accepted_as_codes_labels_or_aliases(documents):
    result = triage(documents_held=documents)
    assert result["verdict"]["status"] == "PROCEED", result["gap_analysis"]


def test_unrecognised_documents_are_reported_and_never_satisfy_a_requirement():
    result = triage(documents_held=["a letter from my cousin"])

    assert result["unrecognised_documents"] == ["a letter from my cousin"]
    # It must not have counted as any mandatory document.
    assert result["gap_analysis"]["missing_documents"] == MANDATORY_DOCUMENTS
    assert result["verdict"]["will_be_served"] is False


def test_blank_document_entries_are_ignored():
    result = triage(documents_held=[*MANDATORY_DOCUMENTS, "", "   "])
    assert result["verdict"]["status"] == "PROCEED"
    assert "unrecognised_documents" not in result


# --------------------------------------------------------------------------
# Rejection criteria
# --------------------------------------------------------------------------


def test_id_photocopy_is_rejected():
    result = triage(
        documents_held=[
            "ID Photocopy",
            "KIAMIS E-Voucher SMS Code",
            "Signed Ward Agricultural Officer (WAO) Form",
        ]
    )

    assert result["verdict"]["status"] == "DO_NOT_TRAVEL"
    reasons = " ".join(result["gap_analysis"]["rejection_reasons"])
    assert "photocopies" in reasons.lower()
    assert "NCPB Operating Circular 4B, Section 2.1" in reasons
    # The photocopy also fails to satisfy the original-ID requirement.
    assert "Original National ID" in result["gap_analysis"]["missing_documents"]


def test_expired_voucher_is_rejected():
    result = triage(
        documents_held=[
            "Original National ID",
            "expired voucher",
            "Signed Ward Agricultural Officer (WAO) Form",
        ]
    )

    assert result["verdict"]["status"] == "DO_NOT_TRAVEL"
    reasons = " ".join(result["gap_analysis"]["rejection_reasons"])
    assert "void" in reasons.lower()
    assert "NCPB Operating Circular 4B, Section 2.4" in reasons


# --------------------------------------------------------------------------
# Leased land
# --------------------------------------------------------------------------


def test_leased_land_without_a_stamped_lease_is_rejected():
    result = triage(is_land_leased=True, has_stamped_lease=False)

    assert result["verdict"]["status"] == "DO_NOT_TRAVEL"
    assert (
        "Official Chief's Stamped Lease Agreement"
        in result["gap_analysis"]["missing_documents"]
    )
    assert any(
        "NCPB Operating Circular 4B, Section 3.2" in reason
        for reason in result["gap_analysis"]["rejection_reasons"]
    )


def test_leased_land_with_a_stamped_lease_proceeds():
    result = triage(is_land_leased=True, has_stamped_lease=True)

    assert result["verdict"]["status"] == "PROCEED"
    assert result["gap_analysis"]["missing_documents"] == []


def test_the_stamped_lease_can_be_declared_as_a_document_instead_of_the_flag():
    result = triage(
        is_land_leased=True,
        has_stamped_lease=False,
        documents_held=[
            *MANDATORY_DOCUMENTS,
            "Official Chief's Stamped Lease Agreement",
        ],
    )
    assert result["verdict"]["status"] == "PROCEED"


def test_owned_land_never_requires_a_lease_agreement():
    result = triage(is_land_leased=False, has_stamped_lease=False)

    assert result["verdict"]["status"] == "PROCEED"
    lease_row = next(
        row
        for row in result["document_checklist"]
        if row["code"] == "chiefs_stamped_lease_agreement"
    )
    assert lease_row["required"] is False


def test_an_unstamped_lease_is_irrelevant_on_owned_land():
    """No lease agreement is required at all when the land is owned."""
    result = triage(
        is_land_leased=False,
        documents_held=[*MANDATORY_DOCUMENTS, "unstamped lease agreement"],
    )
    assert result["verdict"]["status"] == "PROCEED"


def test_declaring_an_unstamped_lease_on_leased_land_is_rejected():
    result = triage(
        is_land_leased=True,
        has_stamped_lease=False,
        documents_held=[*MANDATORY_DOCUMENTS, "unstamped lease agreement"],
    )

    assert result["verdict"]["status"] == "DO_NOT_TRAVEL"
    # Reported once, though it arises from both the condition and the
    # declared document.
    lease_reasons = [
        reason
        for reason in result["gap_analysis"]["rejection_reasons"]
        if "Section 3.2" in reason
    ]
    assert len(lease_reasons) == 1


# --------------------------------------------------------------------------
# Depot readiness
# --------------------------------------------------------------------------


def _first_depot_with_status(status: str) -> dict:
    return next(d for d in repo.DEPOTS if d["status"] == status)


@pytest.mark.parametrize(
    "status", ["STOCK_DEPLETED", "UNDER_MAINTENANCE", "SUSPENDED"]
)
def test_a_non_serving_depot_blocks_travel(status):
    depot = _first_depot_with_status(status)
    county = depot["catchment_counties"][0]
    county_record = repo.find_county(county)
    constituency = county_record["constituencies"][0]
    ward = constituency["wards"][0]

    result = triage(
        county=county,
        constituency=constituency["constituency_name"],
        ward=ward["ward_name"],
        target_depot_id=depot["depot_id"],
    )

    assert result["verdict"]["status"] == "DO_NOT_TRAVEL"
    assert result["policy_grounding"]["depot_status"].startswith(status)
    assert any(
        "not issuing subsidised fertilizer" in reason
        for reason in result["gap_analysis"]["rejection_reasons"]
    )


def test_a_blocked_depot_offers_serving_government_alternatives():
    depot = _first_depot_with_status("STOCK_DEPLETED")
    county = depot["catchment_counties"][0]
    county_record = repo.find_county(county)
    constituency = county_record["constituencies"][0]

    result = triage(
        county=county,
        constituency=constituency["constituency_name"],
        ward=constituency["wards"][0]["ward_name"],
        target_depot_id=depot["depot_id"],
    )

    alternatives = result["alternative_depots"]
    assert alternatives, "a blocked depot should suggest a serving one"
    for alternative in alternatives:
        assert alternative["serves_farmers"] is True
        assert alternative["depot_id"] != depot["depot_id"]
        assert county in alternative["catchment_counties"]
        # Government depots only - never a third-party vendor.
        assert alternative["depot_id"].startswith("ncpb_")


def test_a_depot_outside_the_farmers_catchment_blocks_travel():
    """NCPB Mombasa does not serve Uasin Gishu, however complete the paperwork."""
    result = triage(target_depot_id="ncpb_mombasa_changamwe")

    assert result["verdict"]["status"] == "DO_NOT_TRAVEL"
    assert any(
        "does not serve Uasin Gishu County" in reason
        for reason in result["gap_analysis"]["rejection_reasons"]
    )


def test_catchment_allows_collecting_in_a_neighbouring_county():
    """
    A Nandi farmer may use NCPB Eldoret, which stands in Uasin Gishu but has
    Nandi in its catchment.
    """
    assert "Nandi" in repo.find_depot("ncpb_eldoret")["catchment_counties"]
    result = triage(county="Nandi", constituency="Mosop", ward="Kabiyet")
    assert result["verdict"]["status"] == "PROCEED"


# --------------------------------------------------------------------------
# Crop scope (statutory, not agronomic)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("crop", ["maize", "Maize", "MAHINDI", "beans", "wheat", "tea"])
def test_gazetted_crops_are_in_scope(crop):
    result = triage(crop_type=crop)
    assert result["crop_within_gazetted_scope"] is True
    assert result["verdict"]["status"] == "PROCEED"


def test_a_crop_outside_the_schedule_is_out_of_scope():
    result = triage(crop_type="macadamia")

    assert result["crop_within_gazetted_scope"] is False
    assert result["verdict"]["status"] == "DO_NOT_TRAVEL"
    assert any(
        "gazetted crop schedule" in reason
        for reason in result["gap_analysis"]["rejection_reasons"]
    )


def test_out_of_scope_crop_never_suggests_an_alternative_crop():
    """
    Constraint 1: the engine may state that a crop is outside the circular's
    scope, but must never recommend what to grow instead.
    """
    result = triage(crop_type="macadamia")
    text = " ".join(
        [
            result["verdict"]["summary"],
            *result["gap_analysis"]["rejection_reasons"],
            *result["next_steps"],
        ]
    ).lower()

    for forbidden in ("instead grow", "you should grow", "we recommend", "try planting"):
        assert forbidden not in text
    # It points at the officer who is allowed to advise.
    assert "ward agricultural officer" in text


def test_the_declared_crop_is_echoed_verbatim():
    assert triage(crop_type="Mahindi")["declared_crop"] == "Mahindi"


# --------------------------------------------------------------------------
# Blockers accumulate
# --------------------------------------------------------------------------


def test_all_blockers_are_reported_together_not_short_circuited():
    """One trip should be enough to fix everything."""
    result = triage(
        target_depot_id="ncpb_mombasa_changamwe",  # outside catchment
        documents_held=["ID Photocopy"],            # photocopy + 3 missing docs
        is_land_leased=True,
        has_stamped_lease=False,                    # unstamped lease
    )

    reasons = result["gap_analysis"]["rejection_reasons"]
    assert len(reasons) >= 6
    joined = " ".join(reasons)
    assert "does not serve" in joined
    assert "photocopies" in joined.lower()
    assert "Section 3.2" in joined
    assert len(result["gap_analysis"]["missing_documents"]) == 4


def test_next_steps_are_procedural_and_end_with_a_recheck():
    result = triage(documents_held=[])
    steps = result["next_steps"]

    assert len(steps) == len(set(steps)), "steps must not repeat"
    assert "Re-run this check" in steps[-1]


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------


def test_identical_requests_produce_identical_verdicts():
    first = triage()
    for _ in range(25):
        assert triage() == first


def test_determinism_holds_for_a_failing_request():
    kwargs = {
        "documents_held": ["ID Photocopy", "expired voucher"],
        "is_land_leased": True,
        "has_stamped_lease": False,
        "acreage": 3.7,
    }
    first = triage(**kwargs)
    for _ in range(25):
        assert triage(**kwargs) == first


def test_document_order_does_not_change_the_verdict():
    import itertools

    baseline = triage(documents_held=MANDATORY_DOCUMENTS)
    for ordering in itertools.permutations(MANDATORY_DOCUMENTS):
        assert triage(documents_held=list(ordering)) == baseline


# --------------------------------------------------------------------------
# Unresolvable references
# --------------------------------------------------------------------------


def test_unknown_county_raises_with_valid_options():
    with pytest.raises(TriageInputError) as excinfo:
        triage(county="Wakanda")

    error = excinfo.value
    assert error.field == "county"
    assert error.status_code == 422
    assert "Uasin Gishu" in error.valid_options


def test_constituency_outside_the_named_county_raises():
    """'Soy' is a real constituency, but not in Kisumu."""
    with pytest.raises(TriageInputError) as excinfo:
        triage(county="Kisumu", constituency="Soy", ward="Moi's Bridge")

    assert excinfo.value.field == "constituency"


def test_ward_outside_the_named_constituency_raises():
    with pytest.raises(TriageInputError) as excinfo:
        triage(ward="Kabiyet")  # a real ward, but in Nandi's Mosop

    assert excinfo.value.field == "ward"


def test_unknown_depot_raises_404():
    with pytest.raises(TriageInputError) as excinfo:
        triage(target_depot_id="ncpb_atlantis")

    assert excinfo.value.field == "target_depot_id"
    assert excinfo.value.status_code == 404


def test_valid_options_are_capped_so_errors_stay_readable():
    with pytest.raises(TriageInputError) as excinfo:
        triage(county="Nowhere")
    assert len(excinfo.value.valid_options) <= 60


# --------------------------------------------------------------------------
# Compliance boundary
# --------------------------------------------------------------------------


def test_every_verdict_carries_the_compliance_boundary():
    for result in (triage(), triage(documents_held=[])):
        compliance = result["compliance"]
        assert set(compliance) == {
            "no_agronomic_advice",
            "no_payments",
            "no_marketplace",
        }


def test_the_statutory_notice_disclaims_payment_processing():
    notice = triage()["financial_breakdown"]["statutory_notice"]
    assert "does not process payments" in notice
    assert "mobile money" in notice


def test_no_payment_or_marketplace_language_appears_in_a_verdict():
    result = triage()
    text = " ".join(
        [result["verdict"]["summary"], *result["next_steps"]]
    ).lower()

    for forbidden in ("m-pesa", "mpesa", "pay now", "checkout", "add to cart", "buy from"):
        assert forbidden not in text


# --------------------------------------------------------------------------
# Statutory payment rule (cash refused at the depot counter)
# --------------------------------------------------------------------------


def test_cash_warning_is_present_on_a_proceed_verdict():
    """
    The farmer told to travel is the one about to leave the house, so this is
    exactly when the cash rule has to be in front of them.
    """
    result = triage()
    assert result["verdict"]["status"] == "PROCEED"

    notice = result["payment_notice"]
    assert notice["cash_accepted_at_depot"] is False
    assert notice["headline"] == "Zero cash accepted at the depot"
    assert "NCPB Operating Circular 4B" in notice["authority"]
    assert notice["accepted_means"]


def test_cash_warning_is_present_on_a_do_not_travel_verdict_too():
    assert triage(documents_held=[])["payment_notice"]["cash_accepted_at_depot"] is False


def test_proceed_next_steps_warn_against_carrying_cash():
    steps = " ".join(triage()["next_steps"]).lower()
    assert "not carry cash" in steps or "do not carry cash" in steps
    assert "till number" in steps


def test_statutory_notice_states_the_cash_rule():
    notice = triage()["financial_breakdown"]["statutory_notice"]
    assert "CASH IS NOT ACCEPTED AT THE DEPOT" in notice
    # And still disclaims that we move money ourselves.
    assert "does not process" in notice


# --------------------------------------------------------------------------
# Crop is optional
# --------------------------------------------------------------------------


def test_crop_may_be_omitted_entirely():
    """The farmer wizard does not ask for a crop; omitting it must still work."""
    result = triage(crop_type=None)

    assert result["verdict"]["status"] == "PROCEED"
    assert result["declared_crop"] is None
    # Null, not False - "not declared" must never read as "outside the schedule".
    assert result["crop_within_gazetted_scope"] is None


def test_blank_crop_is_treated_as_not_declared():
    assert triage(crop_type="   ")["crop_within_gazetted_scope"] is None


def test_a_declared_crop_is_still_scope_checked():
    assert triage(crop_type="maize")["crop_within_gazetted_scope"] is True
    assert triage(crop_type="macadamia")["crop_within_gazetted_scope"] is False


# --------------------------------------------------------------------------
# Citation wording
# --------------------------------------------------------------------------


def test_operating_procedure_is_cited_in_full():
    result = triage()
    assert result["policy_grounding"]["operating_procedure"] == (
        "NCPB Operating Circular 4B"
    )
    assert result["policy_grounding"]["circular"] == "MOALD Circular 2026/02"
