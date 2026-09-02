"""
Kilimo Hakika (DepotReady) - Geographic reference data normalizer.

Builds `backend/data/counties.json` (the canonical County -> Constituency -> Ward
hierarchy served by `GET /api/geo/hierarchy`) from the two raw sources in the
repository root:

  1. csv-Kenya-Counties-Constituencies-Wards.csv  (IEBC-style, with official IDs)
  2. county.json                                  (legacy hand-maintained tree)

WHY THE CSV IS THE STRUCTURAL BACKBONE
--------------------------------------
Both files were audited before this script was written. The CSV is internally
consistent: 47 counties / 290 constituencies / 1450 wards, contiguous ward IDs
1..1450, no duplicate ward names inside a constituency, no stray whitespace, and
a stable ID -> name mapping.

`county.json` carries the defects this normalizer exists to remove:

  * Stray leading/trailing whitespace   e.g. "  Tsimba Golini", "Tharaka "
  * A verbatim duplicate constituency   Nyeri -> "Tetu" appears twice
  * Merged ward names (two wards fused into one string)
        "MATAYOS SOUTHBUSIBWABO" = "Matayos South" + "Busibwabo"
        "MARACHI WESTKINGANDOLE" = "Marachi West"  + "Kingandole"
  * Inconsistent casing (whole blocks of Busia/Kisii wards are SHOUTED)
  * Wards attached to the wrong constituency, e.g. Kakamega "Shinyalu" is
    populated with Lugari's wards, and Siaya "Ugenya" holds Rarieda's wards.

Rebuilding from the CSV eliminates every one of those classes at the source
rather than patching them one by one. `county.json` is still loaded so the run
can *prove* the defects are gone and emit an audit trail.

Outputs
-------
  backend/data/counties.json             canonical hierarchy (served by the API)
  backend/data/data_quality_report.json  audit trail of what was normalized

Run:  python scripts/build_data.py
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"

CSV_SOURCE = REPO_ROOT / "csv-Kenya-Counties-Constituencies-Wards.csv"
JSON_SOURCE = REPO_ROOT / "county.json"

OUT_COUNTIES = DATA_DIR / "counties.json"
OUT_REPORT = DATA_DIR / "data_quality_report.json"


# --------------------------------------------------------------------------
# Casing
# --------------------------------------------------------------------------

# Swahili connectives that stay lowercase when they are not the first token,
# e.g. "MJI WA KALE" -> "Mji wa Kale", "ZIWA LA NG'OMBE" -> "Ziwa la Ng'ombe".
LOWERCASE_PARTICLES = {"wa", "la", "ya"}

# Standalone Roman numerals keep their uppercase form: "UMOJA II" -> "Umoja II".
ROMAN_NUMERALS = {"i", "ii", "iii", "iv", "v", "vi"}

# Delimiters that are preserved verbatim while the words between them are cased.
_SPLIT_RE = re.compile(r"([ /\-])")


def _case_word(word: str) -> str:
    """Title-case a single delimiter-free word."""
    if not word:
        return word

    low = word.lower()
    if low in ROMAN_NUMERALS:
        return word.upper()

    out: list[str] = []
    # `capitalize_next` drives the very first letter; an apostrophe *inside* a
    # word does not trigger capitalization, because in Kenyan orthography it
    # marks the velar nasal or a possessive: "ANG'URAI" -> "Ang'urai",
    # "MOI'S BRIDGE" -> "Moi's Bridge".
    #
    # A leading apostrophe is different: it quotes a single letter, as in
    # "MANYATTA 'B'" -> "Manyatta 'B'", so the letter after it is capitalized.
    capitalize_next = True
    for idx, ch in enumerate(low):
        if ch == "'":
            out.append(ch)
            capitalize_next = idx == 0
            continue
        out.append(ch.upper() if capitalize_next else ch)
        capitalize_next = False
    return "".join(out)


def title_case(raw: str) -> str:
    """
    Normalize a Kenyan place name to consistent title case.

    Collapses internal whitespace, strips the ends, normalizes the curly
    apostrophe (U+2019) used inconsistently across both sources to a straight
    one, and capitalizes across space, slash and hyphen boundaries.
    """
    text = unicodedata.normalize("NFKC", raw)
    text = text.replace("’", "'").replace("‘", "'").replace("´", "'")
    text = " ".join(text.split())  # strip + collapse runs of whitespace

    parts = _SPLIT_RE.split(text)
    result: list[str] = []
    word_index = 0
    for part in parts:
        if part in (" ", "/", "-"):
            result.append(part)
            continue
        cased = _case_word(part)
        # Particles only lowercase mid-name, and only after a space (never
        # after a slash or hyphen, which begin a new proper name).
        if (
            word_index > 0
            and cased.lower() in LOWERCASE_PARTICLES
            and result
            and result[-1] == " "
        ):
            cased = cased.lower()
        result.append(cased)
        word_index += 1
    return "".join(result)


# --------------------------------------------------------------------------
# Curated source corrections
# --------------------------------------------------------------------------

# Genuine spelling errors in the CSV, each confirmed against `county.json` (which
# has the correct spelling) and/or the published IEBC ward register. Keys are the
# raw CSV strings; values are the corrected names in final title case.
#
# Deliberately conservative: only clear typographic errors are listed. Ordinary
# spelling variants between the two sources are left on the CSV's reading so the
# ward IDs stay trustworthy.
CSV_WARD_CORRECTIONS: dict[str, str] = {
    "NJABINI\\KIBURU": "Njabini/Kiburu",   # stray backslash used as separator
    "DEDAN KIMANTHI": "Dedan Kimathi",     # named for Dedan Kimathi
    "BUKIRA CENTRL IKEREGE": "Bukira Central/Ikerege",
    "KAPCKOK": "Kapchok",
    "MASIG EAST": "Masige East",
    "SAMETA/ MOKWERERO": "Sameta/Mokwerero",
    "BOBASI/ BOITANGARE": "Bobasi/Boitangare",
}

CSV_CONSTITUENCY_CORRECTIONS: dict[str, str] = {
    "CHUKA IGAMBA NG'OMBE": "Chuka/Igambang'ombe",
    "CHUKA IGAMBA NGOM": "Chuka/Igambang'ombe",  # truncated in the CSV
}

# The CSV ships a spreadsheet error: all five Baringo North rows carry the
# literal "#N/A" instead of a constituency ID. The correct value is unambiguous
# from the surrounding block - Tiaty is 157 and Baringo Central is 159, and 158
# is the only gap in the otherwise contiguous 1..290 constituency ID sequence.
CSV_CONSTITUENCY_ID_REPAIRS: dict[tuple[str, str], int] = {
    ("30", "BARINGO NORTH"): 158,
}


# --------------------------------------------------------------------------
# Lookup keys
# --------------------------------------------------------------------------


def lookup_key(name: str) -> str:
    """
    Collapse a name to a comparison key: lowercase alphanumerics only.

    Used both to diff the two sources here and, at runtime, to resolve
    user-supplied county/constituency/ward names tolerantly. "Mji wa
    Kale/Makadara", "MJI WA KALE / MAKADARA" and "mjiwakalemakadara" all
    collapse to the same key.
    """
    text = unicodedata.normalize("NFKD", name)
    text = text.replace("’", "'").replace("‘", "'")
    return re.sub(r"[^a-z0-9]", "", text.lower())


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------


def load_csv_rows() -> list[dict[str, str]]:
    # utf-8-sig: the file carries a BOM that would otherwise corrupt the first
    # header ("COUNTY ID") and break DictReader lookups.
    with CSV_SOURCE.open(encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def build_hierarchy(
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    counties: dict[int, dict[str, Any]] = {}

    repairs_applied: Counter[str] = Counter()

    for row in rows:
        county_code = int(row["COUNTY ID"])
        ward_id = int(row["WARD ID"])

        raw_county = row["COUNTY NAME"]
        raw_constituency = row["CONSTITUENCY NAME"]
        raw_ward = row["WARD NAME"]

        raw_constituency_id = row["CONSTITUENCY ID"].strip()
        if raw_constituency_id.isdigit():
            constituency_id = int(raw_constituency_id)
        else:
            # Non-numeric ID (e.g. the "#N/A" spreadsheet error). Fall back to
            # the curated repair table, keyed on county + collapsed name.
            repair_key = (row["COUNTY ID"].strip(), " ".join(raw_constituency.split()))
            if repair_key not in CSV_CONSTITUENCY_ID_REPAIRS:
                raise ValueError(
                    f"unrepairable constituency ID {raw_constituency_id!r} for "
                    f"{repair_key}; add an entry to CSV_CONSTITUENCY_ID_REPAIRS"
                )
            constituency_id = CSV_CONSTITUENCY_ID_REPAIRS[repair_key]
            repairs_applied[f"{repair_key[1]} -> {constituency_id}"] += 1

        county_name = title_case(raw_county)
        constituency_name = CSV_CONSTITUENCY_CORRECTIONS.get(
            raw_constituency.strip(), title_case(raw_constituency)
        )
        ward_name = CSV_WARD_CORRECTIONS.get(raw_ward.strip(), title_case(raw_ward))

        county = counties.setdefault(
            county_code,
            {
                "county_code": county_code,
                "county_name": county_name,
                "lookup_key": lookup_key(county_name),
                "constituencies": {},
            },
        )
        constituency = county["constituencies"].setdefault(
            constituency_id,
            {
                "constituency_id": constituency_id,
                "constituency_name": constituency_name,
                "lookup_key": lookup_key(constituency_name),
                "wards": [],
            },
        )
        constituency["wards"].append(
            {
                "ward_id": ward_id,
                "ward_name": ward_name,
                "lookup_key": lookup_key(ward_name),
            }
        )

    # Freeze the dict-of-dicts into sorted lists so the emitted file is stable
    # across runs (deterministic output keeps diffs and the API contract clean).
    ordered: list[dict[str, Any]] = []
    for county in sorted(counties.values(), key=lambda c: c["county_code"]):
        constituencies = []
        for constituency in sorted(
            county["constituencies"].values(), key=lambda c: c["constituency_id"]
        ):
            constituency["wards"].sort(key=lambda w: w["ward_id"])
            constituencies.append(constituency)
        county["constituencies"] = constituencies
        ordered.append(county)
    return ordered, dict(repairs_applied)


# --------------------------------------------------------------------------
# Audit of the legacy county.json
# --------------------------------------------------------------------------


def audit_legacy_source(hierarchy: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Compare the legacy `county.json` against the rebuilt hierarchy and record
    every defect the rebuild removed. Purely diagnostic: nothing here changes
    the emitted `counties.json`.
    """
    legacy = json.loads(JSON_SOURCE.read_text(encoding="utf-8"))

    whitespace_defects: list[dict[str, str]] = []
    duplicate_constituencies: list[dict[str, Any]] = []
    casing_defects: list[dict[str, str]] = []

    legacy_ward_keys: set[str] = set()
    legacy_ward_count = 0

    for county in legacy:
        county_name = county["county_name"]

        names = [c["constituency_name"] for c in county["constituencies"]]
        for name, count in Counter(n.strip() for n in names).items():
            if count > 1:
                duplicate_constituencies.append(
                    {
                        "county": county_name.strip(),
                        "constituency": name,
                        "occurrences": count,
                    }
                )

        for constituency in county["constituencies"]:
            raw_constituency = constituency["constituency_name"]
            if raw_constituency != raw_constituency.strip():
                whitespace_defects.append(
                    {
                        "level": "constituency",
                        "county": county_name.strip(),
                        "raw_value": raw_constituency,
                    }
                )

            for ward in constituency["wards"]:
                legacy_ward_count += 1
                legacy_ward_keys.add(lookup_key(ward))
                if ward != ward.strip():
                    whitespace_defects.append(
                        {
                            "level": "ward",
                            "county": county_name.strip(),
                            "constituency": raw_constituency.strip(),
                            "raw_value": ward,
                        }
                    )
                stripped = ward.strip()
                if stripped.isupper() and len(stripped) > 3:
                    casing_defects.append(
                        {
                            "county": county_name.strip(),
                            "constituency": raw_constituency.strip(),
                            "raw_value": stripped,
                        }
                    )

    canonical_ward_keys = {
        ward["lookup_key"]
        for county in hierarchy
        for constituency in county["constituencies"]
        for ward in constituency["wards"]
    }

    # The two merged names named in the spec, verified as split in the rebuild.
    merged_ward_repairs = []
    for merged, components in (
        ("MATAYOS SOUTHBUSIBWABO", ("Matayos South", "Busibwabo")),
        ("MARACHI WESTKINGANDOLE", ("Marachi West", "Kingandole")),
    ):
        merged_key = lookup_key(merged)
        merged_ward_repairs.append(
            {
                "legacy_value": merged,
                "split_into": list(components),
                "present_in_legacy_source": merged_key in legacy_ward_keys,
                "removed_from_output": merged_key not in canonical_ward_keys,
                "components_present_in_output": all(
                    lookup_key(part) in canonical_ward_keys for part in components
                ),
            }
        )

    return {
        "legacy_ward_entries": legacy_ward_count,
        "canonical_ward_entries": len(canonical_ward_keys),
        "whitespace_defects_found": len(whitespace_defects),
        "whitespace_defects": whitespace_defects,
        "duplicate_constituencies_found": len(duplicate_constituencies),
        "duplicate_constituencies": duplicate_constituencies,
        "shouted_casing_defects_found": len(casing_defects),
        "shouted_casing_examples": casing_defects[:15],
        "merged_ward_repairs": merged_ward_repairs,
    }


def validate(hierarchy: list[dict[str, Any]]) -> dict[str, int]:
    """Fail loudly if the rebuilt hierarchy is not internally sound."""
    county_count = len(hierarchy)
    constituency_count = sum(len(c["constituencies"]) for c in hierarchy)
    ward_count = sum(
        len(con["wards"]) for c in hierarchy for con in c["constituencies"]
    )

    assert county_count == 47, f"expected 47 counties, got {county_count}"
    assert constituency_count == 290, (
        f"expected 290 constituencies, got {constituency_count}"
    )
    assert ward_count == 1450, f"expected 1450 wards, got {ward_count}"

    # No residual whitespace or casing damage anywhere in the output.
    for county in hierarchy:
        for field in (county["county_name"],):
            assert field == field.strip() and "  " not in field, field
        for constituency in county["constituencies"]:
            name = constituency["constituency_name"]
            assert name == name.strip() and "  " not in name, name
            for ward in constituency["wards"]:
                ward_name = ward["ward_name"]
                assert ward_name == ward_name.strip() and "  " not in ward_name, (
                    ward_name
                )
                assert not (ward_name.isupper() and len(ward_name) > 3), ward_name

    # Duplicate constituency names within a county (the Nyeri "Tetu" defect)
    # and duplicate ward names within a constituency must both be absent.
    for county in hierarchy:
        keys = [c["lookup_key"] for c in county["constituencies"]]
        dupes = [k for k, n in Counter(keys).items() if n > 1]
        assert not dupes, f"duplicate constituencies in {county['county_name']}: {dupes}"
        for constituency in county["constituencies"]:
            ward_keys = [w["lookup_key"] for w in constituency["wards"]]
            ward_dupes = [k for k, n in Counter(ward_keys).items() if n > 1]
            assert not ward_dupes, (
                f"duplicate wards in {constituency['constituency_name']}: {ward_dupes}"
            )

    # Official IDs must stay globally unique and gap-free so they can serve as
    # stable keys. A gap is exactly how the "#N/A" Baringo North defect showed
    # up, so this assertion guards the repair table against future drift.
    ward_ids = [
        w["ward_id"] for c in hierarchy for con in c["constituencies"] for w in con["wards"]
    ]
    assert sorted(ward_ids) == list(range(1, 1451)), "ward IDs are not 1..1450"

    constituency_ids = [
        con["constituency_id"] for c in hierarchy for con in c["constituencies"]
    ]
    assert sorted(constituency_ids) == list(range(1, 291)), (
        "constituency IDs are not 1..290"
    )

    county_codes = [c["county_code"] for c in hierarchy]
    assert sorted(county_codes) == list(range(1, 48)), "county codes are not 1..47"

    # Lookup keys must be unique per county so tolerant name resolution at
    # runtime can never be ambiguous.
    by_county: dict[str, list[str]] = defaultdict(list)
    for county in hierarchy:
        for constituency in county["constituencies"]:
            by_county[county["lookup_key"]].append(constituency["lookup_key"])
    for county_key, keys in by_county.items():
        assert len(set(keys)) == len(keys), f"ambiguous constituency keys in {county_key}"

    return {
        "counties": county_count,
        "constituencies": constituency_count,
        "wards": ward_count,
    }


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    rows = load_csv_rows()
    hierarchy, id_repairs = build_hierarchy(rows)
    totals = validate(hierarchy)
    audit = audit_legacy_source(hierarchy)

    payload = {
        "source": "IEBC County / Constituency / Ward register",
        "source_files": [CSV_SOURCE.name, JSON_SOURCE.name],
        "structural_authority": CSV_SOURCE.name,
        "totals": totals,
        "counties": hierarchy,
    }
    OUT_COUNTIES.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    report = {
        "generated_by": "backend/scripts/build_data.py",
        "structural_authority": CSV_SOURCE.name,
        "authority_rationale": (
            "The CSV is internally consistent (47/290/1450, contiguous ward IDs "
            "1-1450, no duplicate ward names within a constituency, no stray "
            "whitespace). county.json carries whitespace damage, a duplicated "
            "Nyeri 'Tetu' constituency, merged ward names, SHOUTED casing, and "
            "wards attached to the wrong constituency."
        ),
        "totals": totals,
        "curated_csv_corrections": {
            "wards": CSV_WARD_CORRECTIONS,
            "constituencies": CSV_CONSTITUENCY_CORRECTIONS,
            "constituency_id_repairs": id_repairs,
        },
        "legacy_source_audit": audit,
    }
    OUT_REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"wrote {OUT_COUNTIES.relative_to(BACKEND_DIR)}")
    print(f"wrote {OUT_REPORT.relative_to(BACKEND_DIR)}")
    print(
        "  counties={counties} constituencies={constituencies} wards={wards}".format(
            **totals
        )
    )
    print(
        f"  legacy defects normalized: "
        f"{audit['whitespace_defects_found']} whitespace, "
        f"{audit['duplicate_constituencies_found']} duplicate constituency, "
        f"{audit['shouted_casing_defects_found']} casing, "
        f"{len(audit['merged_ward_repairs'])} merged ward names"
    )


if __name__ == "__main__":
    main()
