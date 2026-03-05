"""Weather code to mood classification utilities."""

from __future__ import annotations

from anime_weather.models import WeatherMood


MOOD_TAGS: dict[WeatherMood, list[str]] = {
    WeatherMood.sunny: ["slice of life", "comedy", "sports", "adventure"],
    WeatherMood.rainy: ["drama", "romance", "mystery"],
    WeatherMood.stormy: ["action", "thriller", "mecha", "battle"],
    WeatherMood.snowy: ["wholesome", "family", "fantasy", "iyashikei"],
    WeatherMood.cloudy: ["supernatural", "psychological", "school"],
    WeatherMood.foggy: ["horror", "mystery", "psychological thriller"],
    WeatherMood.scorching: ["ecchi", "comedy", "beach", "summer"],
}

# Start with a complete 0-99 map and override known WMO categories.
WMO_TO_MOOD: dict[int, WeatherMood] = {code: WeatherMood.cloudy for code in range(100)}

for code in (0, 1):
    WMO_TO_MOOD[code] = WeatherMood.sunny
for code in (2, 3):
    WMO_TO_MOOD[code] = WeatherMood.cloudy
for code in (45, 48):
    WMO_TO_MOOD[code] = WeatherMood.foggy
for code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
    WMO_TO_MOOD[code] = WeatherMood.rainy
for code in (71, 73, 75, 77, 85, 86):
    WMO_TO_MOOD[code] = WeatherMood.snowy
for code in (95, 96, 99):
    WMO_TO_MOOD[code] = WeatherMood.stormy


def classify_mood(weather_code: int, temperature_max: float) -> WeatherMood:
    """Classify a weather code and max temperature into a mood category."""
    base_mood = WMO_TO_MOOD.get(weather_code, WeatherMood.cloudy)

    if base_mood == WeatherMood.sunny and temperature_max >= 35:
        return WeatherMood.scorching
    if base_mood == WeatherMood.rainy and temperature_max <= 2:
        return WeatherMood.snowy
    return base_mood
