"""
Regression tests for the normalized reference data.

These lock in the specific defects that `scripts/build_data.py` exists to
remove, so a future data refresh cannot quietly reintroduce them.
"""

from __future__ import annotations

import json
from collections import Counter

from app import repository as repo
from app.config import COUNTIES_FILE


def test_totals_match_the_official_register():
    assert repo.GEO_TOTALS == {
        "counties": 47,
        "constituencies": 290,
        "wards": 1450,
    }


def test_no_leading_or_trailing_whitespace_anywhere():
    """The legacy source had 18 of these, e.g. '  Tsimba Golini', 'Tharaka '."""
    for county in repo.COUNTIES:
        assert county["county_name"] == county["county_name"].strip()
        for constituency in county["constituencies"]:
            name = constituency["constituency_name"]
            assert name == name.strip()
            for ward in constituency["wards"]:
                assert ward["ward_name"] == ward["ward_name"].strip()


def test_no_collapsed_internal_whitespace():
    """The CSV carried 'BARINGO  NORTH', 'CENTRAL  WARD', 'KITUTU   CENTRAL'."""
    for county in repo.COUNTIES:
        for constituency in county["constituencies"]:
            assert "  " not in constituency["constituency_name"]
            for ward in constituency["wards"]:
                assert "  " not in ward["ward_name"]


def test_nyeri_tetu_appears_exactly_once():
    """`county.json` listed Tetu twice with identical wards."""
    nyeri = repo.find_county("Nyeri")
    names = [c["constituency_name"] for c in nyeri["constituencies"]]
    assert names.count("Tetu") == 1


def test_no_duplicate_constituency_within_a_county():
    for county in repo.COUNTIES:
        keys = [c["lookup_key"] for c in county["constituencies"]]
        assert [k for k, n in Counter(keys).items() if n > 1] == []


def test_no_duplicate_ward_within_a_constituency():
    for county in repo.COUNTIES:
        for constituency in county["constituencies"]:
            keys = [w["lookup_key"] for w in constituency["wards"]]
            assert [k for k, n in Counter(keys).items() if n > 1] == []


def test_merged_busia_ward_names_are_split():
    """
    'MATAYOS SOUTHBUSIBWABO' and 'MARACHI WESTKINGANDOLE' each fused two
    distinct wards into one string in the legacy source.
    """
    assert repo.find_ward("Busia", "Matayos", "Matayos South") is not None
    assert repo.find_ward("Busia", "Matayos", "Busibwabo") is not None
    assert repo.find_ward("Busia", "Butula", "Marachi West") is not None
    assert repo.find_ward("Busia", "Butula", "Kingandole") is not None

    # And the fused forms are gone.
    assert repo.find_ward("Busia", "Matayos", "Matayos South Busibwabo") is None
    assert repo.find_ward("Busia", "Butula", "Marachi West Kingandole") is None


def test_shouted_casing_is_normalized():
    """Whole blocks of Busia and Kisii wards were uppercase in the legacy source."""
    for county in repo.COUNTIES:
        for constituency in county["constituencies"]:
            for ward in constituency["wards"]:
                name = ward["ward_name"]
                assert not (name.isupper() and len(name) > 3), name


def test_kenyan_orthography_is_preserved_by_title_casing():
    """
    Title casing must not flatten Swahili particles, the velar-nasal
    apostrophe, quoted single letters, hyphens or Roman numerals.
    """
    cases = [
        ("Mombasa", "Mvita", "Mji wa Kale/Makadara"),
        ("Mombasa", "Nyali", "Ziwa la Ng'ombe"),
        ("Uasin Gishu", "Soy", "Moi's Bridge"),
        ("Busia", "Teso North", "Ang'urai North"),
        ("Kisumu", "Kisumu East", "Manyatta 'B'"),
        ("Nyeri", "Othaya", "Iria-Ini"),
        ("Nairobi", "Embakasi West", "Umoja II"),
        ("Nairobi", "Embakasi North", "Dandora Area III"),
    ]
    for county, constituency, ward in cases:
        record = repo.find_ward(county, constituency, ward)
        assert record is not None, f"{ward} not found"
        assert record["ward_name"] == ward


def test_official_ids_are_contiguous_and_unique():
    """A gap is how the '#N/A' Baringo North constituency ID was caught."""
    ward_ids = [
        w["ward_id"]
        for c in repo.COUNTIES
        for con in c["constituencies"]
        for w in con["wards"]
    ]
    assert sorted(ward_ids) == list(range(1, 1451))

    constituency_ids = [
        con["constituency_id"] for c in repo.COUNTIES for con in c["constituencies"]
    ]
    assert sorted(constituency_ids) == list(range(1, 291))

    assert sorted(c["county_code"] for c in repo.COUNTIES) == list(range(1, 48))


def test_baringo_north_id_was_repaired():
    """The CSV shipped '#N/A' for all five Baringo North rows."""
    record = repo.find_constituency("Baringo", "Baringo North")
    assert record is not None
    assert record["constituency_id"] == 158
    assert len(record["wards"]) == 5


def test_stray_backslash_separator_was_fixed():
    """The CSV had 'NJABINI\\KIBURU' using a backslash as a separator."""
    assert repo.find_ward("Nyandarua", "Kinangop", "Njabini/Kiburu") is not None


def test_lookup_keys_are_stable_and_normalized():
    """The baked keys must equal keys recomputed at runtime, or matching breaks."""
    for county in repo.COUNTIES:
        assert county["lookup_key"] == repo.lookup_key(county["county_name"])
        for constituency in county["constituencies"]:
            assert constituency["lookup_key"] == repo.lookup_key(
                constituency["constituency_name"]
            )
            for ward in constituency["wards"]:
                assert ward["lookup_key"] == repo.lookup_key(ward["ward_name"])


def test_counties_file_is_valid_json_with_expected_envelope():
    document = json.loads(COUNTIES_FILE.read_text(encoding="utf-8"))
    assert set(document) >= {
        "source",
        "source_files",
        "structural_authority",
        "totals",
        "counties",
    }


# --------------------------------------------------------------------------
# Depot network
# --------------------------------------------------------------------------


def test_every_county_has_at_least_one_serving_depot():
    """
    Without this, a farmer in an uncovered county could never get a PROCEED
    verdict no matter what paperwork they held.
    """
    uncovered = [
        county["county_name"]
        for county in repo.COUNTIES
        if not repo.serving_depots_for_county(county["county_name"])
    ]
    assert uncovered == []


def test_depot_ids_are_unique():
    ids = [d["depot_id"] for d in repo.DEPOTS]
    assert len(set(ids)) == len(ids)


def test_depot_counties_and_catchments_are_real_counties():
    valid = {c["county_name"] for c in repo.COUNTIES}
    for depot in repo.DEPOTS:
        assert depot["county"] in valid, depot["depot_id"]
        assert depot["status"] in repo.STATUS_DEFINITIONS, depot["depot_id"]
        for catchment_county in depot["catchment_counties"]:
            assert catchment_county in valid, (depot["depot_id"], catchment_county)
        # A depot must always serve the county it physically stands in.
        assert depot["county"] in depot["catchment_counties"], depot["depot_id"]


def test_depot_county_codes_agree_with_the_register():
    codes = {c["county_name"]: c["county_code"] for c in repo.COUNTIES}
    for depot in repo.DEPOTS:
        assert depot["county_code"] == codes[depot["county"]], depot["depot_id"]


def test_network_exercises_both_serving_and_non_serving_statuses():
    """Non-serving depots must exist, or the DO_NOT_TRAVEL depot path is dead code."""
    statuses = {d["status"] for d in repo.DEPOTS}
    assert any(repo.STATUS_DEFINITIONS[s]["serves_farmers"] for s in statuses)
    assert any(not repo.STATUS_DEFINITIONS[s]["serves_farmers"] for s in statuses)


# --------------------------------------------------------------------------
# Scheme rules
# --------------------------------------------------------------------------


def test_scheme_rules_match_the_circular():
    assert repo.SCHEME["scheme_id"] == "fertilizer_subsidy_2026"
    assert (
        repo.SCHEME["source_citation"]
        == "MOALD Circular 2026/02 & NCPB Operating Circular 4B"
    )
    assert repo.SCHEME["circular"] == "MOALD Circular 2026/02"
    assert repo.SCHEME["operating_procedure"] == "NCPB Circular 4B"

    assert repo.PRICING["price_per_bag_kes"] == 2500
    assert repo.PRICING["bag_weight_kg"] == 50

    assert repo.ALLOCATION["bags_per_acre_planting"] == 2
    assert repo.ALLOCATION["bags_per_acre_top_dressing"] == 2
    assert repo.ALLOCATION["bags_per_acre_total"] == 4
    assert repo.ALLOCATION["max_bags_per_farmer"] == 100


def test_the_three_mandatory_documents_are_the_ones_in_the_circular():
    assert [d["code"] for d in repo.REQUIRED_DOCUMENTS] == [
        "original_national_id",
        "kiamis_evoucher_sms_code",
        "wao_signed_form",
    ]


def test_leased_land_requires_a_chiefs_stamped_lease():
    assert [d["code"] for d in repo.CONDITIONAL_DOCUMENTS] == [
        "chiefs_stamped_lease_agreement"
    ]
    assert repo.CONDITIONAL_DOCUMENTS[0]["required_when"] == "is_land_leased"


def test_the_three_rejection_criteria_are_present():
    assert {c["code"] for c in repo.REJECTION_CRITERIA} == {
        "id_photocopy_presented",
        "expired_evoucher",
        "unstamped_lease_agreement",
    }


def test_no_string_means_both_a_valid_document_and_a_disqualifying_item():
    """
    If an alias appeared in both indexes, resolution order would silently decide
    the verdict. This must stay impossible.
    """
    document_keys = {
        repo.lookup_key(alias)
        for doc in (*repo.REQUIRED_DOCUMENTS, *repo.CONDITIONAL_DOCUMENTS)
        for alias in (doc["code"], doc["label"], *doc.get("aliases", []))
    }
    trigger_keys = {
        repo.lookup_key(trigger)
        for criterion in repo.REJECTION_CRITERIA
        for trigger in criterion.get("triggered_by_documents", [])
    }
    assert document_keys & trigger_keys == set()
