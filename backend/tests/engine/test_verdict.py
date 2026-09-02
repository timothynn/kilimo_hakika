"""Verdict behaviour: the three questions, and the fail-closed states."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from kilimo_hakika.engine import LandTenure, ReasonKind, Verdict, evaluate
from tests.conftest import ALL_REQUIRED, make_input


def test_holding_everything_proceeds(pack):
    result = evaluate(pack, make_input())
    assert result.verdict is Verdict.PROCEED
    assert result.reason_kind is ReasonKind.READY
    assert result.blockers == ()


def test_verdict_is_proceed_iff_no_blockers(pack):
    for held in ({}, {"NATIONAL_ID_ORIGINAL"}, ALL_REQUIRED - {"EVOUCHER_CODE"}, ALL_REQUIRED):
        result = evaluate(pack, make_input(held_documents=held))
        assert (result.verdict is Verdict.PROCEED) == (len(result.blockers) == 0)


@pytest.mark.parametrize("missing", sorted(ALL_REQUIRED))
def test_each_required_document_blocks_on_its_own(pack, missing):
    result = evaluate(pack, make_input(held_documents=ALL_REQUIRED - {missing}))
    assert result.verdict is Verdict.DO_NOT_TRAVEL
    assert [b.document_code for b in result.blockers] == [missing]
    assert result.blockers[0].citation, "every policy blocker cites a source"


def test_holding_nothing_lists_every_missing_artifact(pack):
    result = evaluate(pack, make_input(held_documents=set()))
    assert {b.document_code for b in result.blockers} == ALL_REQUIRED
    assert "5" in result.summary or "things are missing" in result.summary


def test_cost_is_answered_even_on_a_red_verdict(pack):
    """Question 3 must be answered on a "no" - a farmer fixing a gap still needs
    to know the cap and the official price."""
    result = evaluate(pack, make_input(held_documents=set()))
    assert result.verdict is Verdict.DO_NOT_TRAVEL
    assert result.allocation is not None
    assert result.allocation.total_bags == 8
    assert result.costing is not None
    assert result.costing.min_total_cost_kes == Decimal("18880.00")  # 4x2500 DAP + 4x2220 SA


def test_advisories_never_change_the_verdict(pack):
    """Leased land raises advisories about the lease and the chief's letter,
    both citing an UNVERIFIED source. Neither may turn the verdict red."""
    result = evaluate(pack, make_input(land_tenure=LandTenure.LEASED))
    assert result.verdict is Verdict.PROCEED
    codes = {a.code for a in result.advisories}
    assert {"ADVISORY_LEASED_LAND_PROOF", "ADVISORY_LEASED_LAND_AGREEMENT"} <= codes
    unverified = [a for a in result.advisories if a.citation_is_unverified]
    assert unverified, "an untraceable rule ships as an advisory, flagged as such"


def test_wrong_county_blocks(pack):
    result = evaluate(pack, make_input(registration_county_code="039"))  # Bungoma vs Nakuru depot
    assert result.verdict is Verdict.DO_NOT_TRAVEL
    assert "ELIG_DEPOT_COUNTY_MISMATCH" in result.blocker_codes


def test_unknown_county_degrades_to_an_advisory(pack):
    result = evaluate(pack, make_input(registration_county_code=None))
    assert result.verdict is Verdict.PROCEED
    assert "ELIG_DEPOT_COUNTY_UNKNOWN" in {a.code for a in result.advisories}


def test_matching_county_raises_neither(pack):
    result = evaluate(pack, make_input(registration_county_code="032"))
    assert "ELIG_DEPOT_COUNTY_MISMATCH" not in result.blocker_codes
    assert "ELIG_DEPOT_COUNTY_UNKNOWN" not in {a.code for a in result.advisories}


def test_sunday_travel_blocks(pack):
    result = evaluate(pack, make_input(travel_date=date(2026, 9, 6)))  # a Sunday
    assert result.verdict is Verdict.DO_NOT_TRAVEL
    assert "TEMPORAL_DEPOT_CLOSED" in result.blocker_codes
    assert result.depot is not None and result.depot.open_on_travel_date is False


def test_weekday_travel_does_not_block(pack):
    result = evaluate(pack, make_input(travel_date=date(2026, 9, 4)))  # a Friday
    assert "TEMPORAL_DEPOT_CLOSED" not in result.blocker_codes


def test_collecting_for_someone_else_blocks(pack):
    result = evaluate(pack, make_input(collecting_in_person=False))
    assert "ELIG_COLLECTING_IN_PERSON" in result.blocker_codes


def test_unknown_depot_fails_closed(pack):
    result = evaluate(pack, make_input(depot_code="NCPB-NOWHERE"))
    assert result.verdict is Verdict.DO_NOT_TRAVEL
    assert result.reason_kind is ReasonKind.DEPOT_UNKNOWN
    assert result.blockers[0].citation is None, "an app-knowledge gap is not a legal citation"


def test_date_outside_the_season_fails_closed(pack):
    result = evaluate(pack, make_input(travel_date=date(2027, 6, 1)))
    assert result.verdict is Verdict.DO_NOT_TRAVEL
    assert result.reason_kind is ReasonKind.NO_EFFECTIVE_SEASON
    assert result.allocation is None, "no season means no cap and no price to quote"


def test_swahili_verdict_is_translated(pack):
    result = evaluate(pack, make_input(held_documents=set()), locale="sw")
    assert result.headline == "Usisafiri bado"
    assert all(b.message for b in result.blockers)


def test_document_order_does_not_change_the_result(pack):
    a = evaluate(pack, make_input(held_documents=["NATIONAL_ID_ORIGINAL", "EVOUCHER_CODE"]))
    b = evaluate(pack, make_input(held_documents=["EVOUCHER_CODE", "NATIONAL_ID_ORIGINAL"]))
    assert a.blocker_codes == b.blocker_codes
    assert a.verdict == b.verdict


def test_repeated_evaluation_is_identical(pack):
    """The core promise: same inputs, same verdict, every time."""
    args = make_input(held_documents={"NATIONAL_ID_ORIGINAL"}, land_tenure=LandTenure.LEASED)
    first = evaluate(pack, args)
    for _ in range(20):
        again = evaluate(pack, args)
        assert again == first


def test_every_rule_in_the_pack_is_reachable(pack):
    """A rule no input can trigger is dead policy - it looks like protection and
    provides none. This asserts each seeded rule fires for some input."""
    fired: set[str] = set()
    candidates = [
        make_input(held_documents=set()),
        make_input(held_documents=set(), land_tenure=LandTenure.LEASED),
        make_input(land_tenure=LandTenure.FAMILY_UNREGISTERED),
        make_input(registration_county_code="039"),
        make_input(registration_county_code=None),
        make_input(travel_date=date(2026, 9, 6)),
        make_input(collecting_in_person=False),
        make_input(acreage_acres=Decimal("40")),
    ]
    for candidate in candidates:
        result = evaluate(pack, candidate)
        fired |= set(result.blocker_codes) | {a.code for a in result.advisories}

    unreachable = {r.code for r in pack.rules} - fired
    assert not unreachable, f"rules never triggered by any test input: {sorted(unreachable)}"
