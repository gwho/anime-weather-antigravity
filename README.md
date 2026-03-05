# Anime Weather
Anime Weather is a full-stack app that combines a 5-day weather forecast with mood-matched anime recommendations and quotes.

![Screenshot placeholder](https://via.placeholder.com/1200x675?text=Anime+Weather+Screenshot)

## 1. Project Overview
- Backend: FastAPI service that fetches weather, classifies weather mood, and picks anime from live sources (Jikan/AniList/Animechan with fallbacks).
- Frontend: React + TypeScript app that displays an animated mood-aware forecast timeline with expandable anime details.
- Integration: Docker Compose, Makefile workflows, and environment-based configuration.

## 2. Architecture Diagram
```text
+-------------------+       HTTP        +-------------------+
| Browser           | <----------------> | Frontend (React)  |
| (User)            |                    | Vite/TypeScript   |
+-------------------+                    +---------+---------+
                                                   |
                                                   | HTTP /api/*
                                                   v
                                        +----------+----------+
                                        | Backend (FastAPI)   |
                                        | Python              |
                                        +----+--------+-------+
                                             |        |
                          +------------------+        +------------------+
                          v                                        v
               +-----------------------+                 +-----------------------+
               | Open-Meteo            |                 | Jikan / AniList /     |
               | Forecast + Geocoding  |                 | Animechan APIs        |
               +-----------------------+                 +-----------------------+
```

## 3. Quick Start
```bash
cp .env.example .env
make install
make dev
```

App URLs:
- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`

## 4. API Documentation
Base URL: `http://localhost:8000`

### Health
```bash
curl -s http://localhost:8000/api/health
```

### Forecast by City
```bash
curl -s "http://localhost:8000/api/forecast?city=Tokyo"
```

### Forecast by Coordinates
```bash
curl -s "http://localhost:8000/api/forecast?lat=35.6762&lon=139.6503"
```

### Mood Mapping (debug)
```bash
curl -s http://localhost:8000/api/moods
```

### Anime Candidates by Mood (debug)
```bash
curl -s http://localhost:8000/api/anime/rainy
```

## 5. Project Structure
```text
anime-weather/
├── backend/
│   ├── anime_weather/
│   │   ├── main.py              # FastAPI app wiring, middleware, lifecycle
│   │   ├── config.py            # Settings + env parsing
│   │   ├── cache.py             # In-memory TTL caches
│   │   ├── models.py            # Pydantic API contracts
│   │   ├── routers/
│   │   │   ├── forecast.py      # /api/forecast and debug endpoints
│   │   │   └── health.py        # /api/health
│   │   └── services/
│   │       ├── weather.py       # Open-Meteo client
│   │       ├── mood.py          # Weather code -> mood classification
│   │       └── anime.py         # Anime discovery + quotes
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/                 # Fetch clients + APIError
│   │   ├── hooks/               # useForecast + useGeolocation
│   │   ├── components/          # UI components and state views
│   │   ├── config/              # Mood visual theme map
│   │   ├── styles/              # Global CSS variables + animations
│   │   ├── types/               # Shared TypeScript interfaces
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── Makefile
├── .env.example
└── README.md
```

## 6. Configuration
Copy `.env.example` to `.env` and edit values.

| Variable | Scope | Default | Description |
|---|---|---|---|
| `ANIME_WEATHER_LOG_LEVEL` | Backend | `INFO` | Python log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `ANIME_WEATHER_CACHE_TTL` | Backend | `1800` | Forecast cache TTL in seconds |
| `ANIME_WEATHER_CORS_ORIGINS` | Backend | `*` | Comma-separated CORS origins for production |
| `ANIME_WEATHER_REQUEST_TIMEOUT_SECONDS` | Backend | `10` | Timeout for external API requests |
| `ANIME_WEATHER_CLEANUP_INTERVAL_SECONDS` | Backend | `600` | Cache cleanup loop interval in seconds |
| `VITE_API_URL` | Frontend | `http://localhost:8000` | Backend API base URL consumed by Vite app |

## 7. Development
### Add a New Weather Mood
1. Update mood enum and tags in `backend/anime_weather/services/mood.py`.
2. Add visual config in `frontend/src/config/moods.ts`.
3. Add or adjust mood-specific background styling in `frontend/src/styles/globals.css`.
4. Validate API + UI behavior with `make check` and manual UI run.

### Add a New Anime Source
1. Extend `backend/anime_weather/services/anime.py` with a new async fetch function.
2. Add source-specific normalization into the internal `AnimeCandidate` shape.
3. Insert it into the fallback chain after Jikan/AniList (or where appropriate).
4. Keep `source` explicit so frontend badges remain accurate.

## 8. Troubleshooting
### CORS errors in browser
- Ensure `ANIME_WEATHER_CORS_ORIGINS` includes your frontend origin in production.
- For local development, `*` is usually acceptable.

### Jikan or AniList rate-limiting
- The backend already includes fallback behavior.
- Retry after a short delay or switch mood/city to test alternate candidates.

### External APIs temporarily down
- Weather API failures return a backend error to the UI.
- Anime provider failures fall back to secondary sources and then evergreen fallback picks.

### Frontend cannot reach backend
- Verify `VITE_API_URL` and backend port (`8000`).
- Check `/api/health` directly: `curl http://localhost:8000/api/health`.

## Docker Workflows
Development profile (hot reload):
```bash
docker compose --profile dev up --build
```

Production profile:
```bash
docker compose --profile prod up --build -d
```
