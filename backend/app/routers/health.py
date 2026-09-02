"""Health check."""

from __future__ import annotations

from fastapi import APIRouter

from .. import repository as repo
from ..config import APP_NAME, APP_VERSION, TRACK_CONSTRAINTS
from ..schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
    description=(
        "Confirms the service is up and reports how much reference data was "
        "loaded. Useful as a container readiness probe and as the frontend's "
        "first connectivity test."
    ),
)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=APP_NAME,
        version=APP_VERSION,
        scheme_id=repo.SCHEME["scheme_id"],
        data_loaded={
            **repo.GEO_TOTALS,
            "depots": len(repo.DEPOTS),
        },
        track_constraints=TRACK_CONSTRAINTS,
    )
