"""Anime discovery and quote retrieval service."""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from anime_weather.cache import anime_cache, quote_cache
from anime_weather.config import settings
from anime_weather.models import AnimeRecommendation, WeatherMood
from anime_weather.services.mood import MOOD_TAGS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnimeCandidate:
    """Internal normalized anime candidate shape."""

    title: str
    japanese_title: str
    image_url: str
    synopsis: str
    genres: list[str]
    external_url: str
    source: str


FALLBACK_ANIME: tuple[AnimeCandidate, ...] = (
    AnimeCandidate("Fullmetal Alchemist: Brotherhood", "鋼の錬金術師 FULLMETAL ALCHEMIST", "https://cdn.myanimelist.net/images/anime/1223/96541.jpg", "Two brothers use alchemy in a high-stakes journey to restore what they lost after a forbidden ritual.", ["Action", "Adventure", "Drama"], "https://myanimelist.net/anime/5114", "fallback"),
    AnimeCandidate("Haikyuu!!", "ハイキュー!!", "https://cdn.myanimelist.net/images/anime/7/76014.jpg", "A short but relentless volleyball player pushes himself and his team toward nationals.", ["Sports", "Comedy", "School"], "https://myanimelist.net/anime/20583", "fallback"),
    AnimeCandidate("Natsume's Book of Friends", "夏目友人帳", "https://cdn.myanimelist.net/images/anime/5/77412.jpg", "A gentle boy who can see spirits spends his days returning stolen names to yokai.", ["Slice of Life", "Supernatural", "Drama"], "https://myanimelist.net/anime/4081", "fallback"),
    AnimeCandidate("Steins;Gate", "シュタインズ・ゲート", "https://cdn.myanimelist.net/images/anime/1935/127974.jpg", "A self-proclaimed mad scientist stumbles into time travel and spirals into consequences.", ["Sci-Fi", "Thriller", "Drama"], "https://myanimelist.net/anime/9253", "fallback"),
    AnimeCandidate("K-On!", "けいおん!", "https://cdn.myanimelist.net/images/anime/10/76120.jpg", "A high-school light music club turns after-school snacks and jam sessions into pure comfort.", ["Comedy", "Music", "Slice of Life"], "https://myanimelist.net/anime/5680", "fallback"),
    AnimeCandidate("Demon Slayer", "鬼滅の刃", "https://cdn.myanimelist.net/images/anime/1286/99889.jpg", "A kind-hearted swordsman fights demons while searching for a cure for his sister.", ["Action", "Fantasy", "Adventure"], "https://myanimelist.net/anime/38000", "fallback"),
    AnimeCandidate("Your Lie in April", "四月は君の嘘", "https://cdn.myanimelist.net/images/anime/3/67177.jpg", "A piano prodigy rediscovers music through a fearless violinist.", ["Drama", "Romance", "Music"], "https://myanimelist.net/anime/23273", "fallback"),
    AnimeCandidate("Mob Psycho 100", "モブサイコ100", "https://cdn.myanimelist.net/images/anime/8/80356.jpg", "A psychic middle-schooler tries to grow as a person while suppressing world-breaking power.", ["Action", "Comedy", "Supernatural"], "https://myanimelist.net/anime/32182", "fallback"),
    AnimeCandidate("March Comes in Like a Lion", "3月のライオン", "https://cdn.myanimelist.net/images/anime/3/88469.jpg", "A lonely shogi prodigy slowly learns warmth, family, and resilience.", ["Drama", "Slice of Life"], "https://myanimelist.net/anime/31646", "fallback"),
    AnimeCandidate("Yuru Camp", "ゆるキャン△", "https://cdn.myanimelist.net/images/anime/6/89778.jpg", "Camping, good food, and winter air make every episode feel like a warm blanket.", ["Slice of Life", "Comedy", "Iyashikei"], "https://myanimelist.net/anime/34798", "fallback"),
    AnimeCandidate("Attack on Titan", "進撃の巨人", "https://cdn.myanimelist.net/images/anime/10/47347.jpg", "Humanity fights for survival behind walls while dark truths unravel.", ["Action", "Drama", "Mystery"], "https://myanimelist.net/anime/16498", "fallback"),
    AnimeCandidate("Toradora!", "とらドラ!", "https://cdn.myanimelist.net/images/anime/13/22128.jpg", "Two chaotic classmates team up in love and accidentally grow up along the way.", ["Romance", "Comedy", "School"], "https://myanimelist.net/anime/4224", "fallback"),
    AnimeCandidate("Samurai Champloo", "サムライチャンプルー", "https://cdn.myanimelist.net/images/anime/13/14134.jpg", "A wild swordsman trio road-trips through Edo Japan with hip-hop attitude.", ["Action", "Adventure", "Comedy"], "https://myanimelist.net/anime/205", "fallback"),
    AnimeCandidate("Mushishi", "蟲師", "https://cdn.myanimelist.net/images/anime/6/73245.jpg", "A wandering expert studies strange lifeforms that blur nature and spirit.", ["Fantasy", "Mystery", "Iyashikei"], "https://myanimelist.net/anime/457", "fallback"),
    AnimeCandidate("Parasyte", "寄生獣 セイの格率", "https://cdn.myanimelist.net/images/anime/3/73178.jpg", "A teenager and an alien parasite share one body in a brutal survival story.", ["Horror", "Psychological", "Action"], "https://myanimelist.net/anime/22535", "fallback"),
    AnimeCandidate("Barakamon", "ばらかもん", "https://cdn.myanimelist.net/images/anime/5/73199.jpg", "An arrogant calligrapher is exiled to an island and finds joy through community.", ["Comedy", "Slice of Life"], "https://myanimelist.net/anime/22789", "fallback"),
    AnimeCandidate("Frieren: Beyond Journey's End", "葬送のフリーレン", "https://cdn.myanimelist.net/images/anime/1015/138006.jpg", "After the hero's party disbands, an elf mage learns what human time really means.", ["Fantasy", "Drama", "Adventure"], "https://myanimelist.net/anime/52991", "fallback"),
    AnimeCandidate("Spy x Family", "SPY×FAMILY", "https://cdn.myanimelist.net/images/anime/1441/122795.jpg", "A spy, an assassin, and a telepath fake a family and somehow make it work.", ["Comedy", "Action", "Slice of Life"], "https://myanimelist.net/anime/50265", "fallback"),
    AnimeCandidate("Psycho-Pass", "PSYCHO-PASS サイコパス", "https://cdn.myanimelist.net/images/anime/5/43399.jpg", "In a surveillance-heavy future, detectives chase criminals before crimes happen.", ["Psychological", "Thriller", "Sci-Fi"], "https://myanimelist.net/anime/13601", "fallback"),
    AnimeCandidate("One Piece", "ONE PIECE", "https://cdn.myanimelist.net/images/anime/6/73245.jpg", "A rubber pirate captain and his crew chase freedom and the greatest treasure at sea.", ["Adventure", "Action", "Comedy"], "https://myanimelist.net/anime/21", "fallback"),
)

ANILIST_QUERY = """
query TrendingByGenre($genre: String) {
  Page(page: 1, perPage: 25) {
    media(type: ANIME, status: RELEASING, sort: TRENDING_DESC, genre_in: [$genre]) {
      title {
        romaji
        english
        native
      }
      description(asHtml: false)
      genres
      coverImage {
        large
      }
      siteUrl
    }
  }
}
"""


def _strip_html(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", value or "")).strip()


def _truncate(value: str, max_len: int = 220) -> str:
    cleaned = value.strip()
    if len(cleaned) <= max_len:
        return cleaned
    return f"{cleaned[: max_len - 3].rstrip()}..."


class AnimeService:
    """Service for dynamic anime discovery and quote lookups."""

    async def prewarm_trending_cache(self) -> None:
        """Preload trending anime into cache during app startup."""
        try:
            await self.fetch_trending_anime()
            logger.info("Pre-warmed trending anime cache")
        except Exception:
            logger.exception("Failed to pre-warm trending cache")

    async def fetch_trending_anime(self) -> list[AnimeCandidate]:
        """Return trending/airing anime using API fallback order."""
        cached = anime_cache.get("trending")
        if cached is not None:
            return cached

        candidates = await self._fetch_jikan_top_airing()
        if not candidates:
            logger.warning("Jikan trending unavailable; trying AniList")
            candidates = await self._fetch_anilist_by_genre("Action")

        if not candidates:
            logger.warning("AniList trending unavailable; using fallback list")
            candidates = list(FALLBACK_ANIME)

        anime_cache.set("trending", candidates, ttl=settings.anime_trending_cache_ttl_seconds)
        return candidates

    async def pick_anime_for_mood(self, mood: WeatherMood) -> AnimeRecommendation:
        """Pick one anime recommendation tailored to the given weather mood."""
        ranked = await self.get_ranked_candidates_for_mood(mood)
        if not ranked:
            fallback = random.choice(FALLBACK_ANIME)
            quote, character = self._generated_quote(fallback.title, mood)
            return self._to_recommendation(fallback, quote, character, mood)

        candidate = ranked[0]["candidate"]
        quote, character = await self.fetch_quote(candidate.title, candidate.synopsis, mood)
        return self._to_recommendation(candidate, quote, character, mood)

    async def get_ranked_candidates_for_mood(self, mood: WeatherMood) -> list[dict[str, Any]]:
        """Return ranked anime candidates and scores for a mood."""
        keywords = MOOD_TAGS[mood]
        pool: list[AnimeCandidate] = []

        trending = await self.fetch_trending_anime()
        pool.extend(trending)

        jikan_search_pool: list[AnimeCandidate] = []
        for keyword in keywords[:2]:
            jikan_search_pool.extend(await self._fetch_jikan_search_by_keyword(keyword))
        if jikan_search_pool:
            pool.extend(jikan_search_pool)
        else:
            # Backup discovery path when Jikan search is unavailable.
            anilist_pool: list[AnimeCandidate] = []
            for keyword in keywords[:2]:
                anilist_pool.extend(await self._fetch_anilist_by_genre(keyword))
            pool.extend(anilist_pool)

        unique_pool = self._unique_by_title(pool)
        ranked = self._rank_candidates(unique_pool, keywords)
        return ranked

    async def fetch_quote(
        self,
        title: str,
        synopsis: str,
        mood: WeatherMood,
    ) -> tuple[str, str]:
        """Fetch quote text for an anime with API, synopsis, and generated fallbacks."""
        cache_key = f"quote:{title.strip().lower()}"
        cached = quote_cache.get(cache_key)
        if cached is not None:
            return cached

        params = {"anime": title}
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                response = await client.get(settings.animechan_quote_url, params=params)
                if response.status_code == 200:
                    payload = response.json()
                    quote_data = payload.get("data")
                    if isinstance(quote_data, dict):
                        content = str(quote_data.get("content", "")).strip()
                        character_data = quote_data.get("character")
                        if isinstance(character_data, dict):
                            character_name = str(character_data.get("name", "")).strip()
                        else:
                            character_name = ""

                        if content:
                            result = (_truncate(content, max_len=200), character_name or "Unknown")
                            quote_cache.set(
                                cache_key,
                                result,
                                ttl=settings.quote_cache_ttl_seconds,
                            )
                            return result
        except httpx.HTTPError:
            logger.warning("Animechan quote lookup failed for title=%s", title)

        if synopsis.strip():
            result = (_truncate(synopsis, max_len=200), "Synopsis")
            quote_cache.set(cache_key, result, ttl=settings.quote_cache_ttl_seconds)
            return result

        result = self._generated_quote(title, mood)
        quote_cache.set(cache_key, result, ttl=settings.quote_cache_ttl_seconds)
        return result

    def _generated_quote(self, title: str, mood: WeatherMood) -> tuple[str, str]:
        mood_lines: dict[WeatherMood, str] = {
            WeatherMood.scorching: "It is so hot even the opening theme needs a beach episode.",
            WeatherMood.sunny: "Clear skies call for big dreams and even bigger theme songs.",
            WeatherMood.cloudy: "This forecast is giving 'something weird is about to happen' energy.",
            WeatherMood.rainy: "Rainy days demand dramatic stares out the window and perfect timing.",
            WeatherMood.stormy: "Thunder outside, power-up arcs inside.",
            WeatherMood.snowy: "Snowfall is just nature pressing mute on the world.",
            WeatherMood.foggy: "Low visibility, high suspense, zero trust in anyone.",
        }
        line = mood_lines.get(mood, "The weather picked the vibe, this anime brings the payoff.")
        return (f"[Generated] {title}: {line}", "Tagline")

    async def _respect_jikan_rate_limit(self) -> None:
        last_call = anime_cache.get("_jikan_last_call")
        now = time.monotonic()
        if isinstance(last_call, float):
            wait_for = 0.4 - (now - last_call)
            if wait_for > 0:
                await asyncio.sleep(wait_for)

        anime_cache.set("_jikan_last_call", time.monotonic(), ttl=60)

    async def _fetch_jikan_top_airing(self) -> list[AnimeCandidate]:
        await self._respect_jikan_rate_limit()
        params: dict[str, str | int] = {"filter": "airing", "limit": 25}

        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                response = await client.get(settings.jikan_top_url, params=params)
                self._log_jikan_rate_headers(response)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError:
            logger.warning("Jikan top airing request failed")
            return []

        return self._parse_jikan_list(payload)

    async def _fetch_jikan_search_by_keyword(self, keyword: str) -> list[AnimeCandidate]:
        await self._respect_jikan_rate_limit()
        params: dict[str, str | int] = {
            "q": keyword,
            "order_by": "popularity",
            "status": "airing",
            "limit": 10,
        }

        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                response = await client.get(settings.jikan_search_url, params=params)
                self._log_jikan_rate_headers(response)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError:
            logger.warning("Jikan search failed for keyword=%s", keyword)
            return []

        return self._parse_jikan_list(payload)

    def _log_jikan_rate_headers(self, response: httpx.Response) -> None:
        remaining = response.headers.get("X-RateLimit-Remaining")
        limit = response.headers.get("X-RateLimit-Limit")
        if remaining or limit:
            logger.info("Jikan rate status remaining=%s limit=%s", remaining, limit)

    async def _fetch_anilist_by_genre(self, genre_keyword: str) -> list[AnimeCandidate]:
        variables = {"genre": genre_keyword.title()}
        payload = {"query": ANILIST_QUERY, "variables": variables}

        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                response = await client.post(settings.anilist_graphql_url, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError:
            logger.warning("AniList request failed for genre=%s", genre_keyword)
            return []

        page = data.get("data", {}).get("Page", {})
        media = page.get("media")
        if not isinstance(media, list):
            return []

        parsed: list[AnimeCandidate] = []
        for item in media:
            if not isinstance(item, dict):
                continue
            title_obj = item.get("title") or {}
            if not isinstance(title_obj, dict):
                title_obj = {}

            english = str(title_obj.get("english") or "").strip()
            romaji = str(title_obj.get("romaji") or "").strip()
            native = str(title_obj.get("native") or "").strip()
            title = english or romaji
            if not title:
                continue

            synopsis = _truncate(_strip_html(str(item.get("description") or "")), 300)
            genres = item.get("genres")
            genres_list = [str(g) for g in genres] if isinstance(genres, list) else []

            cover = item.get("coverImage")
            image_url = ""
            if isinstance(cover, dict):
                image_url = str(cover.get("large") or "")

            parsed.append(
                AnimeCandidate(
                    title=title,
                    japanese_title=native,
                    image_url=image_url,
                    synopsis=synopsis,
                    genres=genres_list,
                    external_url=str(item.get("siteUrl") or ""),
                    source="anilist",
                )
            )
        return parsed

    def _parse_jikan_list(self, payload: dict[str, Any]) -> list[AnimeCandidate]:
        data = payload.get("data")
        if not isinstance(data, list):
            return []

        parsed: list[AnimeCandidate] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue

            title = str(entry.get("title") or "").strip()
            if not title:
                continue

            synopsis = _truncate(str(entry.get("synopsis") or "No synopsis available."), 300)
            genres_data = entry.get("genres")
            genres: list[str] = []
            if isinstance(genres_data, list):
                for genre in genres_data:
                    if isinstance(genre, dict) and genre.get("name"):
                        genres.append(str(genre["name"]))

            image_url = ""
            images = entry.get("images")
            if isinstance(images, dict):
                jpg = images.get("jpg")
                if isinstance(jpg, dict):
                    image_url = str(jpg.get("image_url") or "")

            parsed.append(
                AnimeCandidate(
                    title=title,
                    japanese_title=str(entry.get("title_japanese") or ""),
                    image_url=image_url,
                    synopsis=synopsis,
                    genres=genres,
                    external_url=str(entry.get("url") or ""),
                    source="jikan",
                )
            )

        return parsed

    def _unique_by_title(self, candidates: list[AnimeCandidate]) -> list[AnimeCandidate]:
        seen: set[str] = set()
        unique: list[AnimeCandidate] = []
        for item in candidates:
            key = item.title.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    def _rank_candidates(
        self,
        candidates: list[AnimeCandidate],
        mood_keywords: list[str],
    ) -> list[dict[str, Any]]:
        randomizer = random.SystemRandom()
        keyword_set = {keyword.lower() for keyword in mood_keywords}

        scored: list[dict[str, Any]] = []
        for candidate in candidates:
            genres_lower = {genre.lower() for genre in candidate.genres}
            overlap = len(genres_lower.intersection(keyword_set))
            score = overlap * 3 + randomizer.uniform(0.0, 1.0)
            scored.append({"candidate": candidate, "score": round(score, 4), "overlap": overlap})

        scored.sort(key=lambda item: float(item["score"]), reverse=True)
        return scored

    def _build_mood_match_reason(
        self,
        mood: WeatherMood,
        candidate: AnimeCandidate,
    ) -> str:
        mood_openers: dict[WeatherMood, str] = {
            WeatherMood.scorching: "This heat index is illegal, so we need maximum chaos-per-minute.",
            WeatherMood.sunny: "Blue skies demand a show with momentum and zero emotional brakes.",
            WeatherMood.cloudy: "Cloud cover makes everything feel one plot twist away from weird.",
            WeatherMood.rainy: "Rain turns every window into a dramatic anime close-up.",
            WeatherMood.stormy: "If the sky is throwing lightning, your watchlist should throw hands too.",
            WeatherMood.snowy: "Snowy weather deserves comfort, wonder, and a warm drink nearby.",
            WeatherMood.foggy: "Fog means low visibility, high paranoia, and excellent suspense timing.",
        }

        genre_text = ", ".join(candidate.genres[:3]) if candidate.genres else "genre roulette"
        synopsis_piece = _truncate(candidate.synopsis, 120)
        opener = mood_openers.get(mood, "Weather picked a mood and this show understood the assignment.")
        return (
            f"{opener} {candidate.title} leans into {genre_text}, and the premise ('{synopsis_piece}') "
            "matches today's vibe way too perfectly."
        )

    def _to_recommendation(
        self,
        candidate: AnimeCandidate,
        quote: str,
        quote_character: str,
        mood: WeatherMood,
    ) -> AnimeRecommendation:
        genre = " / ".join(candidate.genres) if candidate.genres else "Unknown"
        return AnimeRecommendation(
            title=candidate.title,
            japanese_title=candidate.japanese_title,
            image_url=candidate.image_url,
            synopsis=candidate.synopsis,
            quote=quote,
            quote_character=quote_character,
            genre=genre,
            mood_match_reason=self._build_mood_match_reason(mood, candidate),
            source=candidate.source,
            external_url=candidate.external_url,
        )
