"""NCPB depot directory."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import repository as repo
from ..schemas import DepotListResponse, DepotOut

router = APIRouter(prefix="/api/depots", tags=["depots"])


def _serialize(depot: dict) -> DepotOut:
    return DepotOut(
        **depot,
        status_label=repo.depot_status_label(depot),
        serves_farmers=repo.depot_serves_farmers(depot),
    )


@router.get(
    "",
    response_model=DepotListResponse,
    summary="List NCPB depots",
    description=(
        "The gazetted Government depot network, optionally filtered to the "
        "depots that serve one county.\n\n"
        "Filtering by `county` matches against each depot's **catchment**, not "
        "its physical location, because a farmer may only collect at a depot "
        "whose catchment includes their county. A depot in a neighbouring "
        "county will therefore appear if it serves yours.\n\n"
        "Only gazetted NCPB depots are listed. This is not a marketplace and "
        "contains no private or third-party vendors."
    ),
)
def list_depots(
    county: str | None = Query(
        default=None,
        description=(
            "Filter to depots whose catchment includes this county, "
            "e.g. 'Uasin Gishu'. Matched case-insensitively."
        ),
        examples=["Uasin Gishu"],
    ),
    serving_only: bool = Query(
        default=False,
        description=(
            "When true, return only depots currently able to serve farmers "
            "(status ACTIVE)."
        ),
    ),
) -> DepotListResponse:
    canonical_county: str | None = None

    if county is not None:
        county_record = repo.find_county(county)
        if county_record is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "field": "county",
                    "message": (
                        f"Unknown county {county!r}. Use a county from "
                        "GET /api/geo/hierarchy."
                    ),
                    "valid_options": repo.county_names(),
                },
            )
        canonical_county = county_record["county_name"]

    depots = repo.list_depots(canonical_county)
    if serving_only:
        depots = [d for d in depots if repo.depot_serves_farmers(d)]

    return DepotListResponse(
        network_name=repo.DEPOT_NETWORK_META["network_name"],
        source_citation=repo.DEPOT_NETWORK_META["source_citation"],
        notice=repo.DEPOT_NETWORK_META["notice"],
        filtered_by_county=canonical_county,
        count=len(depots),
        status_definitions=repo.STATUS_DEFINITIONS,
        depots=[_serialize(d) for d in depots],
    )


@router.get(
    "/{depot_id}",
    response_model=DepotOut,
    summary="Get one depot",
    description="Retrieve a single depot by its `depot_id`.",
    responses={404: {"description": "No depot with that id."}},
)
def get_depot(depot_id: str) -> DepotOut:
    depot = repo.find_depot(depot_id)
    if depot is None:
        raise HTTPException(
            status_code=404,
            detail={
                "field": "depot_id",
                "message": f"Unknown depot {depot_id!r}.",
                "valid_options": [d["depot_id"] for d in repo.DEPOTS],
            },
        )
    return _serialize(depot)
