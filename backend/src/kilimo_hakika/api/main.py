from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..assistant import corpus
from ..packs.repository import repository
from ..persistence import db
from ..settings import get_settings
from .routes import assistant, auth, profile, reference, triage

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    loaded = repository.refresh()
    if loaded is None:
        log.error("started with NO rule pack; triage will refuse every request")
    else:
        log.info(
            "loaded pack %s from %s (%s), checksum %s",
            loaded.pack.version,
            loaded.source,
            loaded.pack.environment,
            loaded.checksum[:12],
        )
        corpus.rebuild(loaded.pack)

    yield
    db.close_pool()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Kilimo Hakika API",
        version="1.0.0",
        description=(
            "Deterministic depot triage, identity and the assistant. "
            "The verdict path contains no model call and no live database read."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-Rule-Pack-Version"],
    )

    @app.middleware("http")
    async def stamp_pack_version(request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        loaded = repository.current
        if loaded is not None:
            response.headers["X-Rule-Pack-Version"] = loaded.pack.version
        return response

    @app.exception_handler(500)
    async def on_unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL", "message": "something went wrong"}},
        )

    for router in (
        reference.router,
        auth.router,
        profile.router,
        triage.router,
        assistant.router,
    ):
        app.include_router(router, prefix="/api/v1")

    @app.get("/api/v1/health")
    def health() -> dict[str, Any]:
        loaded = repository.current
        return {
            "status": "ok" if loaded is not None else "degraded",
            "rule_pack_version": loaded.pack.version if loaded else None,
            "rule_pack_checksum": loaded.checksum if loaded else None,
            "pack_source": loaded.source if loaded else None,
            "environment": loaded.pack.environment if loaded else None,
            "database": "up" if db.is_available() else "down",
            "assistant": "configured" if get_settings().anthropic_api_key else "unconfigured",
            "engine_version": "1.0.0",
        }

    return app


app = create_app()
