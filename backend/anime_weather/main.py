"""FastAPI application entrypoint and lifecycle management."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from anime_weather.cache import anime_cache, geocode_cache, quote_cache, weather_cache
from anime_weather.config import configure_logging, cors_origin_list, settings
from anime_weather.routers import forecast, health
from anime_weather.services.anime import AnimeService

configure_logging()
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Build and configure the FastAPI app instance."""
    app = FastAPI(
        title=settings.app_name,
        description=settings.app_description,
        version=settings.app_version,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Attach a per-request identifier for traceability."""
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    app.include_router(health.router, prefix="/api")
    app.include_router(forecast.router, prefix="/api")

    @app.on_event("startup")
    async def startup_event() -> None:
        """Warm caches and start periodic maintenance tasks."""
        anime_service = AnimeService()
        await anime_service.prewarm_trending_cache()
        app.state.cache_cleanup_task = asyncio.create_task(_cache_cleanup_loop())

    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        """Stop background tasks gracefully."""
        task = getattr(app.state, "cache_cleanup_task", None)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info("Cache cleanup loop stopped")

    return app


async def _cache_cleanup_loop() -> None:
    """Periodically clear expired entries from all in-memory caches."""
    while True:
        await asyncio.sleep(settings.cleanup_interval_seconds)
        cleared = (
            weather_cache.clear_expired()
            + anime_cache.clear_expired()
            + quote_cache.clear_expired()
            + geocode_cache.clear_expired()
        )
        if cleared:
            logger.info("Cleared %d expired cache entries", cleared)


app = create_app()
