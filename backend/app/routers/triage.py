"""The core triage endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..compliance import REFUSAL_MESSAGE, detect_advice_request
from ..schemas import ErrorResponse, TriageRequest, TriageResponse
from ..triage import TriageInputError, run_triage

router = APIRouter(prefix="/api/triage", tags=["triage"])


@router.post(
    "",
    response_model=TriageResponse,
    summary="Run subsidy and depot triage",
    description=(
        "Decides whether a farmer will actually be served if they travel to "
        "their chosen NCPB depot today, and states exactly why.\n\n"
        "**The engine is deterministic.** No model, no scoring, no randomness. "
        "The same request always yields the same verdict, and every rejection "
        "cites the circular clause behind it, so any answer can be audited by "
        "hand.\n\n"
        "**Blockers are never short-circuited.** A farmer missing two documents "
        "at a closed depot is told all three problems at once, so a single "
        "follow-up trip resolves everything.\n\n"
        "**Entitlement is always reported**, even on DO_NOT_TRAVEL, because the "
        "farmer still needs to know what they are owed once the blockers clear.\n\n"
        "Scope limits:\n"
        "- No agronomic advice. `crop_type` is used only to confirm the holding "
        "falls inside the circular's gazetted crop schedule. A `crop_type` "
        "phrased as an agronomy question is refused with HTTP 422.\n"
        "- No payments. `financial_breakdown` reports statutory prices for "
        "planning; payment happens at the depot counter.\n"
        "- No marketplace. `alternative_depots` lists only gazetted Government "
        "depots."
    ),
    responses={
        404: {
            "model": ErrorResponse,
            "description": "The `target_depot_id` does not exist.",
        },
        422: {
            "model": ErrorResponse,
            "description": (
                "The location could not be resolved, a field failed validation, "
                "or the request sought agronomic advice."
            ),
        },
    },
)
def triage(request: TriageRequest) -> TriageResponse:
    # Constraint 1, enforced before any work is done: refuse rather than
    # answer, and say where agronomic guidance actually comes from.
    advice_reason = detect_advice_request(request.crop_type)
    if advice_reason is not None:
        raise HTTPException(
            status_code=422,
            detail={
                "field": "crop_type",
                "error": "agronomic_advice_refused",
                "message": REFUSAL_MESSAGE,
                "detected": advice_reason,
                "submitted_value": request.crop_type,
            },
        )

    try:
        result = run_triage(
            county=request.county,
            constituency=request.constituency,
            ward=request.ward,
            target_depot_id=request.target_depot_id,
            acreage=request.acreage,
            crop_type=request.crop_type,
            documents_held=request.documents_held,
            is_land_leased=request.is_land_leased,
            has_stamped_lease=request.has_stamped_lease,
        )
    except TriageInputError as error:
        raise HTTPException(
            status_code=error.status_code, detail=error.as_detail()
        ) from error

    return TriageResponse(**result)
