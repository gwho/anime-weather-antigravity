"""Application configuration and constants."""

from __future__ import annotations

import logging
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    app_name: str = "Anime Weather API"
    app_description: str = (
        "5-day weather forecast enriched with mood-matched anime recommendations and quotes."
    )
    app_version: str = "1.0.0"

    log_level: str = "INFO"
    cors_origins: str = "*"
    cache_ttl: int = 1800

    request_timeout_seconds: float = 10.0

    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    open_meteo_geocode_url: str = "https://geocoding-api.open-meteo.com/v1/search"

    jikan_top_url: str = "https://api.jikan.moe/v4/top/anime"
    jikan_search_url: str = "https://api.jikan.moe/v4/anime"
    anilist_graphql_url: str = "https://graphql.anilist.co"
    animechan_quote_url: str = "https://animechan.io/api/v1/quotes/random"

    weather_cache_ttl_seconds: int = 1800
    anime_trending_cache_ttl_seconds: int = 7200
    quote_cache_ttl_seconds: int = 21600
    geocode_cache_ttl_seconds: int = 86400

    cleanup_interval_seconds: int = 600

    model_config = SettingsConfigDict(env_prefix="ANIME_WEATHER_", extra="ignore")


settings = Settings()


def configure_logging() -> None:
    """Configure process-wide logging for the API."""
    level_name = settings.log_level.upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def cors_origin_list() -> list[str]:
    """Return parsed CORS origins from a comma-separated string."""
    raw = settings.cors_origins.strip()
    if raw == "*":
        return ["*"]

    parts = [item.strip() for item in raw.split(",")]
    return [item for item in parts if item]
