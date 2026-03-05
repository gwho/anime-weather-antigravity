"""Forecast router and weather/anime aggregation endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status

from anime_weather.models import AnimeRecommendation, DayForecast, ForecastResponse, WeatherMood
from anime_weather.services.anime import AnimeService
from anime_weather.services.mood import MOOD_TAGS, classify_mood
from anime_weather.services.weather import OpenMeteoService, WeatherAPIError, describe_weather_code

logger = logging.getLogger(__name__)

router = APIRouter(tags=["forecast"])

weather_service = OpenMeteoService()
anime_service = AnimeService()


@router.get("/forecast", response_model=ForecastResponse, summary="5-day anime weather forecast")
async def get_forecast(
    lat: float | None = Query(default=None, ge=-90, le=90),
    lon: float | None = Query(default=None, ge=-180, le=180),
    city: str | None = Query(default=None, min_length=1, max_length=100),
) -> ForecastResponse:
    """Return weather forecasts enriched with mood-based anime recommendations."""
    if city and (lat is not None or lon is not None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either city or lat/lon, not both.",
        )

    if city is None and (lat is None or lon is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either city or both lat and lon.",
        )

    if city is None and ((lat is None) != (lon is None)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="lat and lon must be provided together.",
        )

    resolved_name: str
    latitude: float
    longitude: float

    try:
        if city is not None:
            geocoded = await weather_service.geocode_city(city)
            latitude = geocoded.latitude
            longitude = geocoded.longitude
            resolved_name = f"{geocoded.name}, {geocoded.country}".strip(", ")
        else:
            assert lat is not None and lon is not None
            latitude = float(lat)
            longitude = float(lon)
            resolved_name = f"{latitude:.2f}, {longitude:.2f}"

        weather_days = await weather_service.fetch_forecast(latitude, longitude)
    except WeatherAPIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    mood_to_anime: dict[WeatherMood, AnimeRecommendation] = {}
    forecast_items: list[DayForecast] = []

    for day in weather_days:
        mood = classify_mood(day.weather_code, day.temperature_max)
        if mood not in mood_to_anime:
            mood_to_anime[mood] = await anime_service.pick_anime_for_mood(mood)

        forecast_items.append(
            DayForecast(
                date=day.date,
                weather_code=day.weather_code,
                weather_description=describe_weather_code(day.weather_code),
                temperature_max=day.temperature_max,
                temperature_min=day.temperature_min,
                precipitation_chance=day.precipitation_chance,
                mood=mood,
                anime=mood_to_anime[mood],
            )
        )

    logger.info("Generated %d forecast rows for %s", len(forecast_items), resolved_name)
    return ForecastResponse(
        location=resolved_name,
        latitude=latitude,
        longitude=longitude,
        forecasts=forecast_items,
    )


@router.get("/moods", summary="Mood categories and genre tags")
async def get_moods() -> dict[str, list[str]]:
    """Return mood-to-keyword mapping used for anime discovery."""
    return {mood.value: tags for mood, tags in MOOD_TAGS.items()}


@router.get("/anime/{mood}", summary="Debug anime candidates for a mood")
async def debug_anime_candidates(mood: WeatherMood) -> dict[str, object]:
    """Return ranked candidate anime list for debugging recommendation quality."""
    ranked = await anime_service.get_ranked_candidates_for_mood(mood)
    normalized = [
        {
            "title": item["candidate"].title,
            "source": item["candidate"].source,
            "genres": item["candidate"].genres,
            "score": item["score"],
            "overlap": item["overlap"],
            "external_url": item["candidate"].external_url,
        }
        for item in ranked
    ]
    return {"mood": mood.value, "count": len(normalized), "candidates": normalized}
