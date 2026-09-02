"""A pack that cannot be understood must never serve a verdict."""

from __future__ import annotations

import copy

import pytest

from kilimo_hakika.engine import PackValidationError, load


def mutate(payload: dict, fn) -> dict:
    clone = copy.deepcopy(payload)
    fn(clone)
    return clone


def test_the_committed_fixture_loads(pack):
    assert pack.version == "NFSP-2026_SHORT_RAINS-0001"
    assert len(pack.rules) == 13
    assert pack.environment == "development-fixture"


def test_unknown_predicate_field_is_rejected(payload):
    bad = mutate(
        payload,
        lambda p: p["rules"][5].__setitem__("applies_when", {"field": "rainfall_mm", "eq": 3}),
    )
    with pytest.raises(PackValidationError, match="unknown input field"):
        load(bad)


def test_unknown_operator_is_rejected(payload):
    bad = mutate(
        payload,
        lambda p: p["rules"][5].__setitem__("applies_when", {"field": "acreage_acres", "roughly": 3}),
    )
    with pytest.raises(PackValidationError, match="unknown operator"):
        load(bad)


def test_missing_citation_is_rejected(payload):
    bad = mutate(payload, lambda p: p["rules"][0].__setitem__("citation", None))
    with pytest.raises(PackValidationError, match="a rule without a citation is not a rule"):
        load(bad)


def test_dangling_citation_is_rejected(payload):
    bad = mutate(payload, lambda p: p["rules"][0].__setitem__("citation", "NO-SUCH-SOURCE"))
    with pytest.raises(PackValidationError, match="is not in the pack"):
        load(bad)


def test_missing_allocation_is_rejected(payload):
    bad = mutate(payload, lambda p: p.pop("allocation"))
    with pytest.raises(PackValidationError, match="allocation is required"):
        load(bad)


def test_empty_rules_is_rejected(payload):
    """An empty rule set would return PROCEED for everyone - the worst possible
    failure mode, since it looks like success."""
    bad = mutate(payload, lambda p: p.__setitem__("rules", []))
    with pytest.raises(PackValidationError, match="no rules"):
        load(bad)


def test_unsupported_contract_is_rejected(payload):
    bad = mutate(payload, lambda p: p.__setitem__("engine_contract", "2.0"))
    with pytest.raises(PackValidationError, match="engine_contract"):
        load(bad)


def test_document_rule_without_a_document_is_rejected(payload):
    bad = mutate(payload, lambda p: p["rules"][0].__setitem__("document", None))
    with pytest.raises(PackValidationError, match="DOCUMENT rules need a document"):
        load(bad)


def test_non_document_rule_with_a_document_is_rejected(payload):
    idx = next(i for i, r in enumerate(payload["rules"]) if r["kind"] == "ELIGIBILITY")
    bad = mutate(payload, lambda p: p["rules"][idx].__setitem__("document", "EVOUCHER_CODE"))
    with pytest.raises(PackValidationError, match="only DOCUMENT rules may have one"):
        load(bad)


def test_depot_in_unknown_county_is_rejected(payload):
    bad = mutate(payload, lambda p: p["depots"][0].__setitem__("county", "999"))
    with pytest.raises(PackValidationError, match="is not in the pack"):
        load(bad)


def test_price_for_unknown_fertilizer_is_rejected(payload):
    bad = mutate(payload, lambda p: p["prices"][0].__setitem__("fertilizer", "UNOBTANIUM"))
    with pytest.raises(PackValidationError, match="unknown fertilizer"):
        load(bad)


def test_duplicate_rule_code_is_rejected(payload):
    bad = mutate(payload, lambda p: p["rules"].append(copy.deepcopy(p["rules"][0])))
    with pytest.raises(PackValidationError, match="duplicate rule code"):
        load(bad)


def test_press_citations_are_treated_as_unverified(pack):
    """A price sourced from press reporting is not a gazetted price, and the UI
    has to be able to say so."""
    assert pack.citation_is_unverified("PRESS-PRICES-2025") is True
    assert pack.citation_is_unverified("SEED-SEASON-WINDOW") is True
    assert pack.citation_is_unverified("NCPB-FAQ-2022-10-Q8") is False
