"""The current gazetted subsidy scheme."""

from __future__ import annotations

from fastapi import APIRouter

from .. import repository as repo
from ..schemas import SchemeResponse

router = APIRouter(prefix="/api/schemes", tags=["schemes"])


@router.get(
    "/current",
    response_model=SchemeResponse,
    summary="Current gazetted subsidy circular",
    description=(
        "The full policy the triage engine applies: statutory pricing, the "
        "allocation formula and its per-farmer ceiling, the mandatory document "
        "checklist, the conditional requirement for leased land, and the "
        "rejection criteria that turn farmers away at the counter.\n\n"
        "Everything the frontend needs to render the checklist and cost table "
        "is here, so no policy figures need to be hard-coded client-side.\n\n"
        "Prices are statutory figures published for planning only - this "
        "service performs no transactions."
    ),
)
def current_scheme() -> SchemeResponse:
    return SchemeResponse(**repo.SCHEME)
