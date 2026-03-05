"""Open-Meteo weather and geocoding service client."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from anime_weather.cache import geocode_cache, weather_cache
from anime_weather.config import settings
from anime_weather.models import GeocodingResult

logger = logging.getLogger(__name__)


class WeatherAPIError(RuntimeError):
    """Raised when Open-Meteo API operations fail."""


@dataclass(frozen=True)
class WeatherDayData:
    """Parsed daily weather forecast data."""

    date: str
    weather_code: int
    temperature_max: float
    temperature_min: float
    precipitation_chance: int


WMO_DESCRIPTIONS: dict[int, str] = {code: "Unknown weather" for code in range(100)}
WMO_DESCRIPTIONS.update(
    {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        56: "Light freezing drizzle",
        57: "Dense freezing drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        66: "Light freezing rain",
        67: "Heavy freezing rain",
        71: "Slight snow fall",
        73: "Moderate snow fall",
        75: "Heavy snow fall",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail",
    }
)


def describe_weather_code(code: int) -> str:
    """Return a human-readable weather description for a WMO code."""
    return WMO_DESCRIPTIONS.get(code, "Unknown weather")


class OpenMeteoService:
    """Service wrapper for Open-Meteo APIs."""

    async def geocode_city(self, city: str) -> GeocodingResult:
        """Resolve a city name to coordinates and canonical location text."""
        cache_key = f"geocode:{city.strip().lower()}"
        cached = geocode_cache.get(cache_key)
        if cached is not None:
            return cached

        params: dict[str, str | int] = {"name": city, "count": 5, "language": "en"}

        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                response = await client.get(settings.open_meteo_geocode_url, params=params)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            logger.exception("Geocoding request failed for city=%s", city)
            raise WeatherAPIError("Unable to geocode city at the moment") from exc

        results = payload.get("results")
        if not isinstance(results, list) or not results:
            logger.warning("No geocoding results found for city=%s", city)
            raise WeatherAPIError(f"Could not resolve city: {city}")

        first = results[0]
        try:
            result = GeocodingResult(
                name=str(first.get("name", city)),
                country=str(first.get("country", "")),
                latitude=float(first["latitude"]),
                longitude=float(first["longitude"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.exception("Unexpected geocoding schema for city=%s", city)
            raise WeatherAPIError("Received invalid geocoding data") from exc

        geocode_cache.set(cache_key, result)
        return result

    async def fetch_forecast(self, latitude: float, longitude: float) -> list[WeatherDayData]:
        """Fetch a 5-day forecast for the provided coordinates."""
        cache_key = f"weather:{latitude:.3f}:{longitude:.3f}"
        cached = weather_cache.get(cache_key)
        if cached is not None:
            return cached

        params: dict[str, str | int | float] = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto",
            "forecast_days": 5,
        }

        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                response = await client.get(settings.open_meteo_forecast_url, params=params)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            logger.exception(
                "Forecast request failed for lat=%.4f lon=%.4f", latitude, longitude
            )
            raise WeatherAPIError("Unable to fetch forecast at the moment") from exc

        parsed = self._parse_daily_payload(payload)
        weather_cache.set(cache_key, parsed)
        return parsed

    def _parse_daily_payload(self, payload: dict[str, Any]) -> list[WeatherDayData]:
        """Parse and validate daily payload returned by Open-Meteo."""
        daily = payload.get("daily")
        if not isinstance(daily, dict):
            raise WeatherAPIError("Forecast response missing daily data")

        dates_raw = daily.get("time")
        codes_raw = daily.get("weather_code")
        tmax_raw = daily.get("temperature_2m_max")
        tmin_raw = daily.get("temperature_2m_min")
        precip_raw = daily.get("precipitation_probability_max")

        if (
            not isinstance(dates_raw, list)
            or not isinstance(codes_raw, list)
            or not isinstance(tmax_raw, list)
            or not isinstance(tmin_raw, list)
            or not isinstance(precip_raw, list)
        ):
            raise WeatherAPIError("Forecast response fields are malformed")

        dates: list[Any] = dates_raw
        codes: list[Any] = codes_raw
        tmax: list[Any] = tmax_raw
        tmin: list[Any] = tmin_raw
        precip: list[Any] = precip_raw

        lengths = {len(dates), len(codes), len(tmax), len(tmin), len(precip)}
        if len(lengths) != 1:
            raise WeatherAPIError("Forecast response has mismatched daily arrays")

        forecast: list[WeatherDayData] = []
        for i in range(len(dates)):
            try:
                forecast.append(
                    WeatherDayData(
                        date=str(dates[i]),
                        weather_code=int(codes[i]),
                        temperature_max=float(tmax[i]),
                        temperature_min=float(tmin[i]),
                        precipitation_chance=max(0, min(100, int(precip[i]))),
                    )
                )
            except (TypeError, ValueError) as exc:
                raise WeatherAPIError("Forecast response contains invalid numeric values") from exc

        return forecast
