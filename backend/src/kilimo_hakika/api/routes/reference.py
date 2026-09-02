"""Reference data and citations - the only unauthenticated reads.

`/reference` is public and cacheable because it is the wizard's own skeleton: a
farmer must be able to see the depot list and the document checklist before
signing in, and none of it is personal.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response, status

from ...packs.repository import repository
from ..schemas import serialise_reference

router = APIRouter()


@router.get("/reference")
def reference(
    response: Response,
    lang: str = Query(default="en", pattern="^(en|sw)$"),
) -> dict[str, Any]:
    loaded = repository.current
    if loaded is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "NO_ACTIVE_PACK", "message": "no rules loaded"}},
        )
    response.headers["Cache-Control"] = "public, max-age=3600, stale-while-revalidate=86400"
    response.headers["ETag"] = f'W/"{loaded.checksum[:16]}-{lang}"'
    return serialise_reference(loaded.pack, lang)


@router.get("/citations/{citation_id}")
def citation(citation_id: str) -> dict[str, Any]:
    """Who says so. Kept out of the triage payload to keep it small on 2G."""
    loaded = repository.current
    if loaded is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "NO_ACTIVE_PACK", "message": "no rules loaded"}},
        )
    record = loaded.pack.citations.get(citation_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "no such citation"}},
        )
    return {
        "id": citation_id,
        "is_unverified": loaded.pack.citation_is_unverified(citation_id),
        **record,
    }
