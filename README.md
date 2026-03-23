# Anime Weather
A full-stack app that combines a 5-day weather forecast with mood-matched anime recommendations, quotes, and atmospheric UI themes.

## Overview
Anime Weather answers a simple question: _"What anime should I watch for today’s weather mood?"_

The system takes a city name (or coordinates), fetches a 5-day forecast, classifies each day into a mood, discovers trending anime from public APIs, applies fallback logic when providers are unavailable, and returns a stable JSON contract consumed by a React frontend.

## Core Features
- 5-day weather forecast via Open-Meteo
- Mood classification (`sunny`, `rainy`, `stormy`, `snowy`, etc.)
- Dynamic anime discovery (Jikan primary, AniList fallback)
- Quote enrichment (Animechan with synopsis/generated fallback)
- Mood-adaptive frontend visuals and animated backgrounds
- In-memory TTL caching for weather, geocoding, trending anime, and quotes
- Health endpoint and debug endpoints for mood and candidate inspection
- Docker + Makefile workflows for local development and production-like runs

## Architecture
```text
+-----------------------+    HTTPS/JSON    +------------------------+
| Browser               | <--------------> | Frontend (React + Vite)|
+-----------------------+                  +-----------+------------+
                                                       |
                                                       | HTTPS/JSON
                                                       v
                                           +-----------+------------+
                                           | Backend (FastAPI)      |
                                           +----+-----------+-------+
                                                |           |
                           +--------------------+           +---------------------+
                           v                                              v
                +-------------------------+                     +-------------------------+
                | Open-Meteo APIs         |                     | Jikan / AniList /       |
                | (forecast + geocoding)  |                     | Animechan APIs          |
                +-------------------------+                     +-------------------------+
```

## Repository Layout
```text
anime-weather-antigravity/
├── backend/
│   ├── anime_weather/
│   │   ├── main.py                  # FastAPI app, middleware, startup/shutdown
│   │   ├── config.py                # Env-driven settings and logging config
│   │   ├── models.py                # Pydantic API schemas
│   │   ├── cache.py                 # In-memory TTL cache implementation
│   │   ├── routers/
│   │   │   ├── forecast.py          # /api/forecast, /api/moods, /api/anime/{mood}
│   │   │   └── health.py            # /api/health
│   │   └── services/
│   │       ├── weather.py           # Open-Meteo client + parsing
│   │       ├── mood.py              # Weather code → mood classification
│   │       └── anime.py             # Anime discovery/ranking/quote fallback chain
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/                     # Fetch layer + typed API errors
│   │   ├── hooks/                   # useForecast + useGeolocation
│   │   ├── components/              # UI components and state views
│   │   ├── config/                  # Mood-to-visual mapping
│   │   ├── styles/                  # Global CSS variables + animation system
│   │   ├── types/                   # TS interfaces mirroring backend models
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── Dockerfile
├── docs/
│   ├── VERCEL_RENDER_DEVOPS_GUIDE.md
│   └── VERCEL_RENDER_RUNBOOK.md
├── docker-compose.yml
├── Makefile
├── .env.example
├── mypy.ini
├── TUTORIAL.md
└── README.md
```

## Tech Stack
- Backend: Python 3.11+, FastAPI, Pydantic v2, httpx
- Frontend: React 18, TypeScript (strict), Vite
- Tooling: Docker, Docker Compose, Makefile, mypy, TypeScript compiler
- External APIs: Open-Meteo, Jikan, AniList, Animechan

## Quick Start (Local)
### 1) Prepare environment
```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies
```bash
make install
```

### 3) Start both apps with hot reload
```bash
make dev
```

Local URLs:
- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Health: `http://localhost:8000/api/health`

## Makefile Commands
- `make dev` → runs backend + frontend concurrently
- `make backend` → backend only (`uvicorn --reload`)
- `make frontend` → frontend only (`vite` dev server)
- `make install` → backend pip install + frontend npm install
- `make check` → backend mypy + frontend `tsc --noEmit`
- `make clean` → removes caches/build artifacts

## Docker Workflows
Development profile (hot reload):
```bash
docker compose --profile dev up --build
```

Production profile:
```bash
docker compose --profile prod up --build -d
```

Ports:
- Dev frontend: `5173`
- Dev backend: `8000`
- Prod frontend (nginx): `3000`
- Prod backend: `8000`

## API Endpoints
Base URL (local): `http://localhost:8000`

### `GET /api/health`
Liveness probe.

```bash
curl -s http://localhost:8000/api/health
```

### `GET /api/forecast?city={name}`
Forecast + anime recommendations by city.

```bash
curl -s "http://localhost:8000/api/forecast?city=Tokyo"
```

### `GET /api/forecast?lat={n}&lon={n}`
Forecast + anime recommendations by coordinates.

```bash
curl -s "http://localhost:8000/api/forecast?lat=35.6762&lon=139.6503"
```

### `GET /api/moods`
Debug endpoint returning mood tags used for matching.

```bash
curl -s http://localhost:8000/api/moods
```

### `GET /api/anime/{mood}`
Debug endpoint returning ranked candidates for a mood.

```bash
curl -s http://localhost:8000/api/anime/rainy
```

## Environment Variables
Copy `.env.example` and adjust values per environment.

| Variable | Scope | Default | Purpose |
|---|---|---|---|
| `ANIME_WEATHER_LOG_LEVEL` | Backend | `INFO` | Log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `ANIME_WEATHER_CACHE_TTL` | Backend | `1800` | Forecast cache TTL override (seconds) |
| `ANIME_WEATHER_CORS_ORIGINS` | Backend | `*` | Allowed origins (comma-separated for production) |
| `ANIME_WEATHER_REQUEST_TIMEOUT_SECONDS` | Backend | `10` | External API timeout |
| `ANIME_WEATHER_CLEANUP_INTERVAL_SECONDS` | Backend | `600` | Cache cleanup interval |
| `VITE_API_URL` | Frontend | `http://localhost:8000` | Backend API base URL for frontend |

## Reliability and Fallback Strategy
Anime sourcing uses a degradation chain:
1. Jikan top/trending + mood keyword search
2. AniList genre-trending backup
3. Embedded evergreen fallback catalog

Quote sourcing chain:
1. Animechan quote
2. Anime synopsis as pseudo-quote
3. Generated weather-themed tagline

This keeps the API responsive even when third-party providers fail or throttle.

## Development Notes
- Backend responses are strongly typed with Pydantic models.
- Frontend contracts mirror backend schemas via strict TypeScript interfaces.
- Caching is in-memory (good for single-instance demos, not multi-instance production).
- UI animations respect `prefers-reduced-motion`.

## Learning Resources Included
- Full architecture/tutorial walkthrough: [TUTORIAL.md](./TUTORIAL.md)
- Deployment concepts (Vercel + Render): [docs/VERCEL_RENDER_DEVOPS_GUIDE.md](./docs/VERCEL_RENDER_DEVOPS_GUIDE.md)
- Practical deployment runbook: [docs/VERCEL_RENDER_RUNBOOK.md](./docs/VERCEL_RENDER_RUNBOOK.md)

## Troubleshooting
### Frontend cannot reach backend
- Verify `VITE_API_URL` in `.env` or deployment env settings.
- Check backend health: `curl http://localhost:8000/api/health`.

### Browser CORS errors
- Set `ANIME_WEATHER_CORS_ORIGINS` to exact frontend origin(s) in production.

### External anime/weather APIs fail intermittently
- This is expected occasionally; the backend fallback chain should still return data.
- Check backend logs for provider-specific failures.

### Rate-limit behavior from Jikan
- The backend applies request pacing and backup provider fallbacks.
- Repeated manual refreshes may still hit upstream limits.

## Security and Production Considerations
- Do not commit `.env` files or secrets.
- Enable HTTPS for frontend and backend domains.
- Restrict CORS origins in production.
- Add centralized error monitoring and alerting for `5xx` spikes.
- Consider Redis if you scale backend instances.

## Ideas for Further Improvement
### Product Enhancements
- User profiles with favorites and watch history
- Genre filters and content warning filters
- Temperature unit preference (C/F)
- Localization (UI + city names + weather text)
- Daily anime digest sharing links

### Backend Improvements
- Add persistent cache layer (Redis)
- Add request-level rate limiting middleware
- Add contract tests for third-party API schema drift
- Add structured logs with request IDs and latency metrics
- Add background warmup jobs for popular cities

### Frontend Improvements
- Add route-based state (`/city/:name` deep links)
- Add optimistic UI for city switching
- Add image placeholders/shimmer loading per card
- Add accessibility audit automation (axe/lighthouse)
- Add visual regression tests for mood themes

### DevOps Improvements
- GitHub Actions CI for lint/type/build/test gates
- Preview environments on PRs
- Canary deployment strategy for backend
- Uptime monitoring + synthetic forecast checks
- Terraform-based provisioning for reproducible infra

## Contributing
1. Create a feature branch from `main`.
2. Keep changes scoped (backend, frontend, docs, or infra).
3. Run checks before opening a PR:
   ```bash
   make check
   cd frontend && npm run build
   ```
4. Submit PR with summary, testing notes, and screenshots/GIFs for UI changes.

## License
Add your preferred license file (`MIT`, `Apache-2.0`, etc.) and reference it here.
