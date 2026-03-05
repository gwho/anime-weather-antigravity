"""Pydantic data models for API contracts."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class WeatherMood(str, Enum):
    """Supported weather mood categories."""

    scorching = "scorching"
    sunny = "sunny"
    cloudy = "cloudy"
    rainy = "rainy"
    stormy = "stormy"
    snowy = "snowy"
    foggy = "foggy"


class AnimeRecommendation(BaseModel):
    """Anime recommendation matched to a weather mood."""

    title: str
    japanese_title: str
    image_url: str
    synopsis: str
    quote: str
    quote_character: str
    genre: str
    mood_match_reason: str
    source: str
    external_url: str

    model_config = ConfigDict(extra="forbid")


class DayForecast(BaseModel):
    """Forecast and anime recommendation for a single day."""

    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    weather_code: int
    weather_description: str
    temperature_max: float
    temperature_min: float
    precipitation_chance: int = Field(ge=0, le=100)
    mood: WeatherMood
    anime: AnimeRecommendation

    model_config = ConfigDict(extra="forbid")


class ForecastResponse(BaseModel):
    """Top-level forecast response payload."""

    location: str
    latitude: float
    longitude: float
    forecasts: list[DayForecast]

    model_config = ConfigDict(extra="forbid")


class GeocodingResult(BaseModel):
    """Resolved geocoding output."""

    name: str
    country: str
    latitude: float
    longitude: float

    model_config = ConfigDict(extra="forbid")
