"""Geographic hierarchy for cascading dropdowns."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import repository as repo
from ..schemas import GeoHierarchyResponse

router = APIRouter(prefix="/api/geo", tags=["geography"])


@router.get(
    "/hierarchy",
    response_model=GeoHierarchyResponse,
    summary="County -> Constituency -> Ward hierarchy",
    description=(
        "The complete normalized hierarchy: 47 counties, 290 constituencies and "
        "1450 wards, each with its official IEBC ID.\n\n"
        "Built for cascading dropdowns - render `counties`, then the selected "
        "county's `constituencies`, then that constituency's `wards`. Every "
        "level also carries a `lookup_key` (lowercase alphanumerics only), "
        "which is the same key `POST /api/triage` uses to match names, so "
        "capitalisation and punctuation differences never cause a mismatch."
    ),
)
def geo_hierarchy() -> GeoHierarchyResponse:
    return GeoHierarchyResponse(**repo.geo_hierarchy())


@router.get(
    "/counties",
    summary="Flat list of county names",
    description=(
        "Convenience endpoint for populating the first dropdown without "
        "transferring the whole hierarchy."
    ),
)
def list_counties() -> dict[str, object]:
    return {
        "count": len(repo.COUNTIES),
        "counties": [
            {
                "county_code": county["county_code"],
                "county_name": county["county_name"],
                "constituency_count": len(county["constituencies"]),
                "ward_count": sum(
                    len(c["wards"]) for c in county["constituencies"]
                ),
            }
            for county in repo.COUNTIES
        ],
    }


@router.get(
    "/constituencies",
    summary="Constituencies within a county",
    description=(
        "The middle level of the cascading dropdown. Kept separate from "
        "/hierarchy so a low-bandwidth client can fetch one county's worth "
        "(a few hundred bytes) instead of the whole 47/290/1450 tree."
    ),
)
def list_constituencies(
    county: str = Query(description="County name, e.g. 'Uasin Gishu'."),
) -> dict[str, object]:
    county_record = repo.find_county(county)
    if county_record is None:
        raise HTTPException(
            status_code=404,
            detail={
                "field": "county",
                "message": f"Unknown county {county!r}.",
                "valid_options": repo.county_names(),
            },
        )

    return {
        "county": county_record["county_name"],
        "county_code": county_record["county_code"],
        "count": len(county_record["constituencies"]),
        "constituencies": [
            {
                "constituency_id": c["constituency_id"],
                "constituency_name": c["constituency_name"],
                "ward_count": len(c["wards"]),
            }
            for c in county_record["constituencies"]
        ],
    }


@router.get(
    "/wards",
    summary="Wards within a county and constituency",
    description=(
        "Returns the wards of one constituency. Names are matched "
        "case- and punctuation-insensitively."
    ),
)
def list_wards(
    county: str = Query(description="County name, e.g. 'Busia'."),
    constituency: str = Query(description="Constituency name, e.g. 'Matayos'."),
) -> dict[str, object]:
    county_record = repo.find_county(county)
    if county_record is None:
        raise HTTPException(
            status_code=404,
            detail={
                "field": "county",
                "message": f"Unknown county {county!r}.",
                "valid_options": repo.county_names(),
            },
        )

    constituency_record = repo.find_constituency(county, constituency)
    if constituency_record is None:
        raise HTTPException(
            status_code=404,
            detail={
                "field": "constituency",
                "message": (
                    f"{constituency!r} is not a constituency of "
                    f"{county_record['county_name']}."
                ),
                "valid_options": repo.constituency_names(county),
            },
        )

    return {
        "county": county_record["county_name"],
        "county_code": county_record["county_code"],
        "constituency": constituency_record["constituency_name"],
        "constituency_id": constituency_record["constituency_id"],
        "count": len(constituency_record["wards"]),
        "wards": constituency_record["wards"],
    }
