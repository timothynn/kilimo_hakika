"""
Kilimo Hakika (DepotReady) - application entry point.

Run in development:
    uvicorn main:app --reload --port 8000

Interactive API docs (Swagger UI):  http://localhost:8000/docs
Alternative docs (ReDoc):           http://localhost:8000/redoc
Raw OpenAPI schema:                 http://localhost:8000/openapi.json
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app import repository as repo
from app.config import (
    APP_NAME,
    APP_SUMMARY,
    APP_VERSION,
    CORS_ALLOW_ORIGINS,
    TRACK_CONSTRAINTS,
)
from app.routers import depots, geo, health, schemes, triage

DESCRIPTION = f"""
{APP_SUMMARY}

Answers one question for a Kenyan farmer before they spend a day and a matatu
fare travelling to an NCPB depot: **will I actually be served?**

The engine is **deterministic** - no model, no scoring, no randomness. Identical
requests always produce identical verdicts, and every rejection cites the
circular clause it rests on, so a Ward Agricultural Officer can audit any answer
by hand.

### Where to start
1. `GET /api/geo/hierarchy` - populate the County -> Constituency -> Ward
   cascading dropdowns (47 / 290 / 1450, each with official IEBC IDs).
2. `GET /api/depots?county=...` - list the depots that serve the chosen county.
3. `GET /api/schemes/current` - render the cost table and document checklist
   from policy rather than hard-coding figures.
4. `POST /api/triage` - get the verdict.

### Name matching
County, constituency, ward, depot, document and crop names are matched
case-, spacing- and punctuation-insensitively. `"Moi's Bridge"`,
`"MOI'S BRIDGE"` and `"mois bridge"` all resolve to the same ward. Matching is
exact on a normalized key, never fuzzy, so determinism is preserved.

### Scope boundaries
This service is a statutory triage tool and deliberately does **not**:

- **{TRACK_CONSTRAINTS['no_agronomic_advice']}**
- **{TRACK_CONSTRAINTS['no_payments']}**
- **{TRACK_CONSTRAINTS['no_marketplace']}**
"""

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    summary=APP_SUMMARY,
    description=DESCRIPTION,
    contact={"name": "Kilimo Hakika Backend"},
    openapi_tags=[
        {"name": "health", "description": "Liveness and loaded-data reporting."},
        {
            "name": "geography",
            "description": (
                "Normalized County -> Constituency -> Ward reference data for "
                "cascading dropdowns."
            ),
        },
        {
            "name": "depots",
            "description": (
                "The gazetted NCPB depot network, its catchments and its "
                "operational statuses. Government depots only."
            ),
        },
        {
            "name": "schemes",
            "description": (
                "The gazetted subsidy circular: pricing, allocation, document "
                "checklist and rejection criteria."
            ),
        },
        {
            "name": "triage",
            "description": "The deterministic PROCEED / DO_NOT_TRAVEL engine.",
        },
    ],
)

# Wide-open CORS. The frontend folder is still empty so no dev origin is known
# yet, and this service exposes only public statutory reference data - no
# credentials, sessions or personal records. `allow_credentials` stays False
# because a wildcard origin combined with credentials is rejected by browsers
# and would silently break the frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(geo.router)
app.include_router(depots.router)
app.include_router(schemes.router)
app.include_router(triage.router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Send browsers straight to the interactive docs."""
    return RedirectResponse(url="/docs")


@app.get("/api", tags=["health"], summary="API index")
def api_index() -> dict[str, object]:
    """Machine-readable index of the available endpoints."""
    return {
        "service": APP_NAME,
        "version": APP_VERSION,
        "scheme_id": repo.SCHEME["scheme_id"],
        "source_citation": repo.SCHEME["source_citation"],
        "docs": {"swagger": "/docs", "redoc": "/redoc", "openapi": "/openapi.json"},
        "endpoints": {
            "health": "GET /health",
            "geo_hierarchy": "GET /api/geo/hierarchy",
            "geo_counties": "GET /api/geo/counties",
            "geo_wards": "GET /api/geo/wards?county=&constituency=",
            "depots": "GET /api/depots?county=&serving_only=",
            "depot_detail": "GET /api/depots/{depot_id}",
            "current_scheme": "GET /api/schemes/current",
            "triage": "POST /api/triage",
        },
        "track_constraints": TRACK_CONSTRAINTS,
    }
