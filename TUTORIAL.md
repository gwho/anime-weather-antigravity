# Anime Weather — Architecture & Tutorial

## Part 1: The Big Picture (Architecture)

### 1.1 What This App Does
Anime Weather takes a city (or your coordinates), fetches a 5-day forecast, classifies each day into a mood (sunny, rainy, stormy, and so on), then pairs each day with a live anime recommendation and quote. The frontend shows this as an interactive timeline where each day expands into anime details, and the visual style changes with the selected mood.

Trade-off: live recommendations make the app feel fresh, but they also introduce external API reliability risk. The backend handles this with fallback chains and caching.

### 1.2 System Architecture Diagram
```text
[Browser]
   |
   | HTTP(S) request, JSON expected (GET /api/forecast?city=Tokyo) ->
   v
[React Frontend (Vite)]
   |
   | HTTP(S) request, JSON payload (ForecastResponse) ->
   v
[FastAPI Backend]
   |\
   | \-- HTTP(S) GET, JSON <-/-> [Open-Meteo]
   |\
   | \-- HTTP(S) GET, JSON <-/-> [Jikan]
   |\
   | \-- HTTP(S) GET, JSON <-/-> [Animechan]
   |\
   | \-- HTTP(S) POST, JSON <-/-> [AniList] (fallback path)
   v
[Aggregated JSON response]
   ^
   | HTTP(S) response, JSON (200 OK)
[React Frontend] -> renders cards -> [Browser UI]
```

### 1.3 Request Lifecycle
Scenario: user types `Tokyo` and presses Enter.

1. User input event fires in `CitySearch`.
   - File: `frontend/src/components/CitySearch.tsx` (lines 21-28, 38-49)
   - `onSubmit()` calls `onSearch(city)`.
2. `App` receives `onSearch` callback.
   - File: `frontend/src/App.tsx` (lines 58-61, 85-88)
   - `onSearch()` calls `fetchByCity(nextCity)` from the custom hook.
3. `useForecast` begins async fetch state transition.
   - File: `frontend/src/hooks/useForecast.ts` (lines 42-54)
   - Sets `loading=true`, clears previous error.
4. API layer builds URL and timeout controller.
   - File: `frontend/src/api/forecast.ts` (lines 13-20, 52-56)
   - HTTP request: `GET {VITE_API_URL}/api/forecast?city=Tokyo`.
5. Backend router receives the request.
   - File: `backend/anime_weather/routers/forecast.py` (lines 22-27)
   - FastAPI injects `city` from query parameters.
6. Router validates mutually exclusive input shape.
   - File: `backend/anime_weather/routers/forecast.py` (lines 29-45)
   - Invalid combinations return `400 Bad Request`.
7. Router calls geocoding service.
   - File: `backend/anime_weather/routers/forecast.py` (lines 52-56)
   - `OpenMeteoService.geocode_city(city)`.
8. Weather service calls Open-Meteo geocoding API.
   - File: `backend/anime_weather/services/weather.py` (lines 76-93)
   - HTTP request: `GET https://geocoding-api.open-meteo.com/v1/search`.
9. Router calls forecast service with resolved coordinates.
   - File: `backend/anime_weather/routers/forecast.py` (line 63)
   - `fetch_forecast(latitude, longitude)`.
10. Weather service calls Open-Meteo forecast API.
    - File: `backend/anime_weather/services/weather.py` (lines 114-142)
    - HTTP request: `GET https://api.open-meteo.com/v1/forecast`.
11. Router classifies mood and selects anime per day.
    - File: `backend/anime_weather/routers/forecast.py` (lines 70-84)
    - `classify_mood()` in mood service, then `pick_anime_for_mood()`.
12. Anime service runs discovery chain.
    - File: `backend/anime_weather/services/anime.py` (lines 102-118, 226-280)
    - Jikan first, AniList fallback, then hardcoded fallback catalog.
13. Anime service fetches quote.
    - File: `backend/anime_weather/services/anime.py` (lines 156-201)
    - Animechan first, then synopsis, then generated tagline.
14. Router assembles `ForecastResponse` model.
    - File: `backend/anime_weather/routers/forecast.py` (lines 88-94)
    - Successful HTTP status: `200 OK`.
15. Frontend API layer parses JSON or throws typed `APIError`.
    - File: `frontend/src/api/forecast.ts` (lines 38-50)
16. Hook updates UI state; `ForecastList` renders, user expands a day.
    - Files:
      - `frontend/src/hooks/useForecast.ts` (lines 46-48)
      - `frontend/src/App.tsx` (lines 108-110)
      - `frontend/src/components/ForecastList.tsx` (lines 14-30)
      - `frontend/src/components/AnimeDetail.tsx` (lines 26-79)

What would break if `useForecast` skipped `setLoading(true)`? The UI would appear frozen on slow networks, and users would click repeatedly, creating duplicate requests.

### 1.4 Why Separate Backend and Frontend?
This split gives clear ownership boundaries:
- Backend owns data acquisition, fallback logic, caching, and API contracts.
- Frontend owns rendering, interaction, and mood-driven presentation.

Compared options:

1. Single Next.js app
- Upside: one repo, one runtime surface, easy SSR patterns.
- Downside: Python service logic (Pydantic models, Python API integrations) would need a rewrite in Node, or a mixed-runtime architecture anyway.

2. Python + Jinja templates
- Upside: lower moving-part count.
- Downside: richer client interactivity (accordion, animated backgrounds, local geolocation UX) becomes harder and less maintainable.

3. Pure static frontend (no backend)
- Upside: cheapest hosting path.
- Downside: API fallback logic, request normalization, and reliability policies move into browser code where secrets, rate management, and cross-origin behavior are harder to control.

When this split is overkill:
- internal tool with one API and no complex transformation logic,
- one developer, short-lived prototype, no reuse needs.

Trade-off: two deploy targets increase operational complexity (CORS, environment sync, release coordination).

**Try This (<15 min)**
- Open `frontend/src/App.tsx` and trace one render path for `error && !data`.
- Then open `backend/anime_weather/routers/forecast.py` and find where a `502` is produced.
- Write one sentence explaining how backend failure becomes frontend UI state.

---

## Part 2: Python Backend Deep Dive

### 2.1 Project Structure — Why These Files?

`backend/anime_weather/main.py`
- Responsibility: app factory, middleware, router mounting, startup/shutdown tasks.
- Without it: no FastAPI app object, no API process entrypoint.
- Too much signal: business logic appearing inside startup or middleware.

`backend/anime_weather/config.py`
- Responsibility: environment-driven settings and logging bootstrap.
- Without it: constants spread across files, hard-coded runtime values.
- Too much signal: API call logic or request handlers inside config.

`backend/anime_weather/models.py`
- Responsibility: strict API schemas and shared domain types.
- Without it: untyped dictionaries and weak contract guarantees.
- Too much signal: network calls or transformation pipelines inside models.

`backend/anime_weather/cache.py`
- Responsibility: in-memory TTL primitives and cache instances.
- Without it: repeated API calls, poor latency, higher rate-limit pressure.
- Too much signal: provider-specific retrieval logic hidden in cache code.

`backend/anime_weather/routers/forecast.py`
- Responsibility: HTTP boundary, validation, orchestration.
- Without it: no `/api/forecast` endpoint.
- Too much signal: direct `httpx` calls or scoring algorithms inside route functions.

`backend/anime_weather/routers/health.py`
- Responsibility: liveness endpoint for monitoring and orchestration.
- Without it: no lightweight availability probe.
- Too much signal: readiness checks that depend on third-party APIs.

`backend/anime_weather/services/weather.py`
- Responsibility: Open-Meteo integration and weather parsing.
- Without it: forecast/geocoding concerns spread across router code.
- Too much signal: anime logic leaking into weather service.

`backend/anime_weather/services/mood.py`
- Responsibility: pure weather-code-to-mood classification and tags.
- Without it: duplicated mood logic and inconsistent category mapping.
- Too much signal: API calls or cache mutation inside classifier.

`backend/anime_weather/services/anime.py`
- Responsibility: anime discovery, ranking, quote fallback chain.
- Without it: core product differentiation disappears.
- Too much signal: response-model assembly for entire endpoint.

What would break if `services/mood.py` disappeared? Mood tagging and recommendation scoring would drift across files, and weather labels would stop being deterministic.

Trade-off: more files mean more navigation overhead, but the boundaries make testing and debugging faster.

### 2.2 Data Flow: From HTTP Request to JSON Response

Code path summary:
- `main.py` wires routers and middleware.
- `routers/forecast.py` validates inputs and orchestrates services.
- `services/weather.py` pulls geocoding and forecast data.
- `services/mood.py` maps weather code to mood.
- `services/anime.py` finds anime + quotes via provider chain.
- `models.py` ensures response shape.

Sequence diagram:
```text
Browser
  | GET /api/forecast?city=Tokyo
  v
forecast.get_forecast() [routers/forecast.py:22-94]
  |-- geocode_city("Tokyo") ------------------------------>
  |   OpenMeteoService [services/weather.py:76-113]
  |   |-- HTTP GET geocoding-api.open-meteo.com ---------->
  |   <-- JSON geocoding result ---------------------------
  |
  |-- fetch_forecast(lat, lon) ---------------------------->
  |   OpenMeteoService [services/weather.py:114-190]
  |   |-- HTTP GET api.open-meteo.com --------------------->
  |   <-- JSON daily arrays --------------------------------
  |
  |-- classify_mood(code, temp) --------------------------->
  |   [services/mood.py:35-43]
  |
  |-- pick_anime_for_mood(mood) --------------------------->
  |   AnimeService [services/anime.py:120-130]
  |   |-- fetch_trending_anime() [102-118]
  |   |   |-- Jikan top airing [226-240] OR
  |   |   |-- AniList backup [269-322] OR
  |   |   |-- fallback list [36-57]
  |   |-- fetch_quote() [156-201]
  |       |-- Animechan [168-193]
  |       |-- synopsis fallback [194-197]
  |       |-- generated fallback [203-214]
  |
  <-- ForecastResponse JSON (200)
```

Trade-off: orchestrating several async services inside one route increases latency variance. Caching reduces this variance.

### 2.3 Python Patterns Explained

#### a) Pydantic Models — Why use models instead of dicts?
Code reference:
- File: `backend/anime_weather/models.py` (lines 21-50)
```python
class AnimeRecommendation(BaseModel):
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
```

`extra="forbid"` means unexpected fields trigger validation errors instead of silently passing.

If you passed invalid data:
- example: `precipitation_chance=300` violates `Field(ge=0, le=100)` in `DayForecast` (line 46).
- Pydantic raises a `ValidationError` before malformed data reaches clients.

Benefits:
- Validation at boundaries.
- Serialization consistency.
- Better editor autocomplete vs free-form dictionaries.

What would break if responses were plain dicts? Frontend could receive shape drift without immediate failure, producing hard-to-debug UI behavior.

Trade-off: validation adds runtime overhead. For this app, correctness benefits are higher than the small cost.

#### b) Async/Await — Why is this backend async?
Code references:
- `backend/anime_weather/services/weather.py` (lines 86-89, 130-133)
- `backend/anime_weather/services/anime.py` (lines 170-172, 231-235, 274-277)

The server spends significant time waiting on remote APIs. With async I/O, the event loop can serve other requests during waits.

Sync vs async timeline for 3 users (A, B, C):
```text
SYNC (single worker)
Time ->
A: [wait weather........][wait anime.....][response]
B:                           [wait weather........][wait anime.....][response]
C:                                                       [wait weather........][wait anime.....][response]

ASYNC (single event loop)
Time ->
A: [start][await weather.....][await anime....][response]
B:    [start][await weather.....][await anime....][response]
C:       [start][await weather.....][await anime....][response]
```

Trade-off: async code has more moving parts (event loop semantics, cancellation behavior), but it handles I/O-heavy workloads much better.

#### c) Dependency Injection via Parameters — FastAPI `Query()` and signature parsing
Code reference:
- File: `backend/anime_weather/routers/forecast.py` (lines 23-27)
```python
async def get_forecast(
    lat: float | None = Query(default=None, ge=-90, le=90),
    lon: float | None = Query(default=None, ge=-180, le=180),
    city: str | None = Query(default=None, min_length=1, max_length=100),
) -> ForecastResponse:
```

FastAPI reads the function signature and injects parsed query values automatically. Validation errors become automatic `422` responses before your logic runs.

Current codebase note:
- It uses signature-based injection with `Query()`.
- There is no active `Depends()` usage yet.

Trade-off: implicit parameter wiring is concise, but debugging unfamiliar FastAPI signatures can confuse new contributors.

#### d) Enum vs Literal — Why `WeatherMood` is an Enum
Code reference:
- File: `backend/anime_weather/models.py` (lines 9-18)
```python
class WeatherMood(str, Enum):
    scorching = "scorching"
    sunny = "sunny"
    cloudy = "cloudy"
    rainy = "rainy"
    stormy = "stormy"
    snowy = "snowy"
    foggy = "foggy"
```

Enum benefits in Python:
- central source of truth,
- serializes as stable string values,
- works directly in Pydantic models.

TypeScript counterpart:
- File: `frontend/src/types/index.ts` (lines 1-8), string union type.

Trade-off:
- Enum carries richer runtime identity in Python.
- TS union is lightweight and ergonomically pleasant in frontend code.

#### e) Service Layer Pattern — Why not put API calls in the router?
Current router orchestration:
- File: `backend/anime_weather/routers/forecast.py` (lines 51-73)

It delegates heavy logic to services:
- weather service (geocode + forecast),
- mood service,
- anime service.

If everything were inline in router, that function would own:
- HTTP input parsing,
- external API request details,
- ranking math,
- quote fallback policy.

The first testability problem would appear quickly: mocking provider responses becomes difficult when all logic is in one endpoint function.

Trade-off: service boundaries add indirection, but testing and maintenance improve significantly.

#### f) Graceful Degradation — The fallback chain
Code reference:
- File: `backend/anime_weather/services/anime.py` (lines 108-116)
```python
candidates = await self._fetch_jikan_top_airing()
if not candidates:
    logger.warning("Jikan trending unavailable; trying AniList")
    candidates = await self._fetch_anilist_by_genre("Action")

if not candidates:
    logger.warning("AniList trending unavailable; using fallback list")
    candidates = list(FALLBACK_ANIME)
```

Quote fallback chain:
- File: `backend/anime_weather/services/anime.py` (lines 168-201)

Why catch specific exceptions?
- Example: catching `httpx.HTTPError` (lines 191-192, 236-237, 257-258, 278-279) isolates network/protocol failures.
- Catching broad `Exception` around normal request flow can hide programmer errors.

What would break if fallback chain was removed? Any transient Jikan outage would convert to endpoint failure, increasing user-visible errors.

Trade-off: fallback content may be less fresh, but availability stays high.

#### g) In-Memory Cache — When is this enough?
Code reference:
- File: `backend/anime_weather/cache.py` (lines 12-55)

TTL logic:
- values store `(expiry, value)` in `_store`,
- reads drop expired entries (lines 28-31),
- `clear_expired()` performs sweep (lines 42-49).

Enough when:
- single-instance demo deployment,
- moderate request volume,
- acceptable cache loss on restart.

Breaks when:
- multiple backend instances need shared cache coherence,
- strict cache durability is required,
- horizontal scaling is required.

Redis comparison:
- Redis gives shared, durable, cross-process cache.
- In-memory cache is operationally lighter and faster to start.

Trade-off: this choice optimizes developer speed and cost, not distributed consistency.

### 2.4 External API Integration Patterns

#### Open-Meteo
- Base URLs:
  - `https://api.open-meteo.com/v1/forecast`
  - `https://geocoding-api.open-meteo.com/v1/search`
- Auth: none.
- Rate limits: provider-specific fair-use guidance.
- Code references:
  - `services/weather.py` lines 83-87 (geocode params)
  - `services/weather.py` lines 121-131 (forecast params)
- Fields used:
  - geocoding: `name`, `country`, `latitude`, `longitude`
  - forecast: `daily.time`, `daily.weather_code`, `daily.temperature_2m_max`, `daily.temperature_2m_min`, `daily.precipitation_probability_max`
- When down: raises `WeatherAPIError`, router returns `502`.

Manual curl tests:
```bash
curl -s "https://geocoding-api.open-meteo.com/v1/search?name=Tokyo&count=1&language=en"
curl -s "https://api.open-meteo.com/v1/forecast?latitude=35.68&longitude=139.69&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=auto&forecast_days=5"
```

#### Jikan
- Base URLs:
  - `https://api.jikan.moe/v4/top/anime`
  - `https://api.jikan.moe/v4/anime`
- Auth: none.
- Rate limit handling in code:
  - local delay in `_respect_jikan_rate_limit()` (lines 216-224)
- Fields used:
  - `title`, `title_japanese`, `images.jpg.image_url`, `synopsis`, `genres`, `url`
- When down: warning logged, AniList fallback path used.

Manual curl tests:
```bash
curl -s "https://api.jikan.moe/v4/top/anime?filter=airing&limit=5"
curl -s "https://api.jikan.moe/v4/anime?q=comedy&order_by=popularity&status=airing&limit=5"
```

#### Animechan
- Base URL: `https://animechan.io/api/v1/quotes/random`
- Auth: none.
- Fields used:
  - `data.content`, `data.character.name`
- When down: synopsis fallback, then generated quote.

Manual curl test:
```bash
curl -s "https://animechan.io/api/v1/quotes/random?anime=One%20Piece"
```

What would break if you consumed entire third-party payloads without transformation? Your API contract would become coupled to provider schema changes.

Trade-off: mapping fields costs development time, but contract stability improves.

**Try This (<15 min)**
- Temporarily disconnect network and call `/api/forecast`.
- Inspect logs to identify where errors are converted into fallback behavior vs hard failures.
- Then restore network and compare response latency with warm cache vs cold cache.

---

## Part 3: TypeScript Frontend Deep Dive

### 3.1 Project Structure — Why These Files?

`frontend/src/main.tsx`
Bootstraps React root and global CSS import. If missing, nothing mounts.

`frontend/src/App.tsx`
Top-level orchestration for async data, selected day state, and major conditional rendering. If it grows too much, state transitions become hard to reason about.

`frontend/src/types/index.ts`
Defines API contract and frontend domain types. Missing this file means implicit shape assumptions spread across components.

`frontend/src/config/moods.ts`
Central mapping from mood to visual theme tokens. Missing this file leads to duplicated style conditionals in multiple components.

`frontend/src/api/forecast.ts`
Owns network calls, timeouts, and `APIError`. Without it, every component repeats fetch/error boilerplate.

`frontend/src/hooks/useForecast.ts`
Encapsulates request lifecycle and retry strategy. Without it, `App.tsx` would mix UI with complex async state logic.

`frontend/src/hooks/useGeolocation.ts`
Encapsulates browser geolocation API and error normalization. Without it, browser API edge cases leak into UI components.

`frontend/src/components/CitySearch.tsx`
Input UX and submission behavior (`onSubmit`, `onKeyDown`, location button). If overloaded, it starts handling API logic and becomes difficult to test.

`frontend/src/components/ForecastList.tsx`
Renders list/accordion composition and animation delay pattern. If overloaded, each card’s UI logic becomes duplicated.

`frontend/src/components/DayCard.tsx`
Compact daily summary and user click target. If overloaded, expanded anime content blurs with summary responsibilities.

`frontend/src/components/AnimeDetail.tsx`
Expanded anime panel (poster, metadata, reason, external link). If overloaded, quote and fallback image logic becomes tangled with parent list control.

`frontend/src/components/QuoteBlock.tsx`
Quote formatting, attribution labels, generated/synopsis badges. Missing it causes repeated quote styling logic.

`frontend/src/components/MoodBackground.tsx`
Background particle layer and mood-transition structure. Missing it forces effect logic into `App.tsx` and CSS selectors become brittle.

`frontend/src/components/LoadingState.tsx`
Loading skeleton and rotating message animation. Missing it causes inconsistent loading UX patterns.

`frontend/src/components/ErrorState.tsx`
Error classification and retry call-to-action. Missing it results in scattered and inconsistent error language.

`frontend/src/styles/globals.css`
Global design tokens, layout rules, animations, reduced-motion policy. Missing it means theme behavior becomes fragmented and inaccessible motion defaults can slip in.

Trade-off: component granularity increases file count, but local reasoning gets easier.

### 3.2 TypeScript vs JavaScript — What’s the Point?

Concrete examples from this project:

1. API contract explicitness
- File: `frontend/src/types/index.ts` (lines 34-39)
- `ForecastResponse` forces every caller to acknowledge `location`, `latitude`, `longitude`, and `forecasts`.

2. Union type prevents invalid moods
- File: `frontend/src/types/index.ts` (lines 1-8)
- If someone writes `const mood: WeatherMood = 'windy'`, compiler fails before runtime.

3. Typed custom hook interface
- File: `frontend/src/hooks/useForecast.ts` (lines 11-18)
- Components get strict signatures for `fetchByCity`, `fetchByCoords`, and `retry`.

4. Error narrowing
- File: `frontend/src/hooks/useForecast.ts` (lines 20-34)
- `unknown` error is narrowed safely by `instanceof` checks.

TypeScript pain points (honest):
- upfront type definitions slow initial feature spikes,
- strict mode can produce non-trivial narrowing work (especially with optional/nullable values),
- refactoring APIs requires coordinated updates across multiple files.

What would break if `any` were used everywhere? compile-time guardrails disappear and contract drift reaches production UI.

Trade-off: TypeScript adds friction early, then saves debugging time during integration and refactoring.

### 3.3 React Patterns Explained

#### a) Component Composition
Code references:
- `frontend/src/components/ForecastList.tsx` (lines 22-30)
- `frontend/src/components/AnimeDetail.tsx` (line 66 uses `QuoteBlock`)

Hierarchy:
```text
ForecastList
  -> DayCard (collapsed summary)
  -> AnimeDetail (expanded panel)
      -> QuoteBlock (quote-specific UI)
```

Why this split:
- small components keep props focused,
- style and behavior boundaries stay clear,
- reuse opportunities increase.

Trade-off: more prop drilling as component tree deepens.

#### b) State Management
State in `App.tsx`:
- File: `frontend/src/App.tsx` (lines 32-33)
- `selectedDay` and `city` live near route-level orchestration.

Why not inside each card?
- selected card affects list-wide behavior,
- data loading status affects multiple sibling components.

When state should move down:
- UI-local concerns (for example, poster image error state lives in `AnimeDetail`, lines 16 and 39).

Trade-off: top-level state centralizes control but can grow dense.

#### c) Custom Hooks (`useForecast`, `useGeolocation`)
What is a hook here?
- a reusable function containing state + side effects.

Before (inline in App) problems:
- repeated `loading/error` transitions,
- harder retry logic,
- browser API branching mixed with rendering.

After (current):
- data fetching is isolated (`useForecast.ts`, lines 36-85),
- geolocation concerns are isolated (`useGeolocation.ts`, lines 28-62).

Trade-off: debugging moves across files, but logic becomes reusable and testable.

#### d) Conditional Rendering Patterns
1. Short-circuit `&&`
- File: `frontend/src/App.tsx` (line 95)
```tsx
{geoError && !data && !loading && <p className="app-geo-hint">{geoError}</p>}
```

2. Ternary `? :`
- File: `frontend/src/App.tsx` (lines 99-106)
```tsx
{error && !data ? <ErrorState ... /> : null}
```

3. Early return
- File: `frontend/src/hooks/useGeolocation.ts` (lines 34-37)
```ts
if (!navigator.geolocation) {
  setError('Geolocation is not supported by this browser.')
  return
}
```

When to use which:
- `&&`: one-sided optional render.
- ternary: choose between two explicit alternatives.
- early return: guard clause to reduce nesting.

Trade-off: mixing all three in one component can reduce readability unless conditions are well named.

#### e) Event Handling
Code references:
- `onSubmit`: `frontend/src/components/CitySearch.tsx` (lines 21-28, 38)
- `onClick`: `frontend/src/components/CitySearch.tsx` (lines 59-63), `frontend/src/components/DayCard.tsx` (line 49)
- `onKeyDown`: `frontend/src/components/CitySearch.tsx` (lines 30-34, 48)

React event object note:
- React wraps native events in synthetic events for cross-browser consistency.
- In modern React, pooling behavior changed, yet event timing assumptions can still cause bugs if you store event objects asynchronously.

Trade-off: synthetic events standardize behavior, with subtle differences from direct DOM listeners.

#### f) CSS-in-JS vs CSS files
Current project approach:
- global CSS + CSS variables (`globals.css`, lines 1-16),
- component-level dynamic accent via inline style object (`App.tsx` line 75, `DayCard.tsx` line 43, `AnimeDetail.tsx` line 30).

Compared approaches:
- styled-components: colocated styles and props integration, extra runtime and tooling conventions.
- Tailwind: rapid composition, utility-heavy markup and design-token governance trade-offs.
- CSS Modules: local scoping, weaker global token discoverability unless conventions are strict.

Trade-off: this project’s hybrid approach keeps runtime light and theming explicit, while requiring discipline to avoid global CSS sprawl.

### 3.4 The API Layer
Why isolate fetch calls in `api/forecast.ts`?
- central timeout policy (`withTimeout`, lines 18-35),
- central HTTP error normalization (`parseForecast`, lines 38-50),
- frontend components stay UI-oriented.

Error handling levels:

1. API layer
- File: `frontend/src/api/forecast.ts` (lines 39-46)
- Converts non-2xx responses into `APIError(status, message)`.

2. Hook layer
- File: `frontend/src/hooks/useForecast.ts` (lines 20-34, 49-51)
- Maps raw exceptions to user-friendly strings.

3. Component layer
- File: `frontend/src/App.tsx` (lines 99-106)
- Chooses error UI state.

4. User-visible message
- File: `frontend/src/components/ErrorState.tsx` (lines 6-26, 32-38)
- Classifies network/location/API errors and provides retry action.

What would break if `fetch()` calls were inside multiple components? duplicate timeout logic and inconsistent error messaging would accumulate quickly.

Trade-off: extra abstraction file (`api/`) adds indirection, but this indirection stabilizes behavior.

**Try This (<15 min)**
- In `frontend/src/api/forecast.ts`, temporarily change timeout from `15_000` to `10`.
- Reload the app and trigger a search.
- Observe how the error transforms across API layer -> hook -> `ErrorState` UI.

---

## Part 4: Python ↔ TypeScript Comparison

### 4.1 Side-by-Side Patterns

| Concept | Python (from backend) | TypeScript (from frontend) |
|---------|------------------------|----------------------------|
| Type definition | `class ForecastResponse(BaseModel)` in `backend/anime_weather/models.py:53-61` | `interface ForecastResponse` in `frontend/src/types/index.ts:34-39` |
| Enum / Union | `class WeatherMood(str, Enum)` in `backend/anime_weather/models.py:9-18` | `type WeatherMood = ...` in `frontend/src/types/index.ts:1-8` |
| Async function | `async def fetch_forecast(...)` in `backend/anime_weather/services/weather.py:114-142` | `const fetchForecastByCity = async (...)` in `frontend/src/api/forecast.ts:52-56` |
| HTTP client | `httpx.AsyncClient` in `backend/anime_weather/services/weather.py:86-87` | `fetch()` + `AbortController` in `frontend/src/api/forecast.ts:18-35` |
| Error handling | `try/except ... raise WeatherAPIError` in `backend/anime_weather/services/weather.py:85-93` | `try/catch ... setError(...)` in `frontend/src/hooks/useForecast.ts:45-53` |
| Dict/Object access | `payload.get("results")` in `backend/anime_weather/services/weather.py:94` | `payload?.detail ?? message` style via checks in `frontend/src/api/forecast.ts:41-44` |
| List transform | list comprehension in `backend/anime_weather/services/weather.py:46` (`expired_keys = [...]`) | `.map()` and `.filter()` in `frontend/src/components/AnimeDetail.tsx:20` |
| String interpolation | `f"weather:{latitude:.3f}:{longitude:.3f}"` in `backend/anime_weather/services/weather.py:116` | `` `${API_BASE}${path}` `` in `frontend/src/api/forecast.ts:16` |
| Module system | `from anime_weather.services.anime import AnimeService` in `backend/anime_weather/routers/forecast.py:10` | `import { useForecast } from './hooks/useForecast'` in `frontend/src/App.tsx:9` |
| Nullable | `lat: float | None` in `backend/anime_weather/routers/forecast.py:24` | `data: ForecastResponse | null` in `frontend/src/hooks/useForecast.ts:12` |

### 4.2 What Each Language Does Better (Be Honest)

Python strengths in this project:
- Fast API integration and transformation work.
  - Example: parsing provider payloads in `services/weather.py` and `services/anime.py` with concise dictionary handling.
- Pydantic model validation is highly ergonomic for backend contracts.
  - Example: `DayForecast.precipitation_chance` constraints in `models.py:46`.
- Readable fallback chains.
  - Example: Jikan -> AniList -> fallback in `anime.py:108-116`.

TypeScript strengths in this project:
- Frontend contract fidelity and compile-time guarantees.
  - Example: union-based mood safety in `types/index.ts:1-8`.
- Safer refactoring in component trees.
  - Example: changing `AnimeRecommendation` shape propagates compile errors across all users.
- Strong editor feedback for React event signatures.
  - Example: typed `KeyboardEvent<HTMLInputElement>` in `CitySearch.tsx:2,30`.

Where each side is weaker:
- Python: type guarantees are not as strict at compile-time as TypeScript in UI code.
- TypeScript: verbose narrowing and interface maintenance can slow rapid backend-style data exploration.

Trade-off: pairing both languages lets each side handle the work it is strongest at.

**Try This (<15 min)**
- Change one field name in backend `AnimeRecommendation` (`source` -> `provider`) and run `make check`.
- Observe how quickly TypeScript shows every frontend usage that needs updating.

---

## Part 5: How to Extend This Project

### 5.1 Adding a New Weather Mood
Checklist:
- [ ] Add enum value in `backend/anime_weather/models.py` (`WeatherMood`, lines 9-18).
- [ ] Extend mood tags in `backend/anime_weather/services/mood.py` (`MOOD_TAGS`, lines 8-16).
- [ ] Update `WMO_TO_MOOD` / `classify_mood()` rules in `backend/anime_weather/services/mood.py` (lines 19-43).
- [ ] Add frontend union value in `frontend/src/types/index.ts` (lines 1-8).
- [ ] Add theme token in `frontend/src/config/moods.ts` (lines 3-74).
- [ ] Add background effect styles in `frontend/src/styles/globals.css` (`.mood-background--...` sections, lines 546-651).
- [ ] Run `make check` and manual UI validation.

What would break if you skipped frontend type update? TypeScript compile will fail where `Record<WeatherMood, MoodTheme>` expects exhaustive keys.

Trade-off: explicit mood additions across layers increase work, but prevent hidden partial support.

### 5.2 Adding a New Anime Source
Checklist:
- [ ] Add provider URL/settings in `backend/anime_weather/config.py` (lines 24-30 pattern).
- [ ] Implement fetch + normalization method in `backend/anime_weather/services/anime.py` (pattern from `_fetch_anilist_by_genre`, lines 269-322).
- [ ] Insert provider into fallback chain in `fetch_trending_anime()` (lines 108-116).
- [ ] Keep normalized output as `AnimeCandidate` (lines 23-34).
- [ ] Ensure `source` is set to provider id for UI badge behavior (`AnimeDetail`, line 24).
- [ ] Add tests/manual logs to verify fallback order under failure.

What would break if provider normalization is skipped? `AnimeRecommendation` construction (`_to_recommendation`, lines 425-438) can receive missing fields and either fail or degrade quality.

Trade-off: each provider increases resilience and freshness, while increasing maintenance surface.

### 5.3 Adding User Preferences
Design sketch (no code):

Feature examples:
- favorites list,
- preferred genres,
- temperature unit toggle (C/F).

Possible architecture:
```text
Browser UI Preferences State
  -> Frontend store (component or context)
  -> API endpoints for persistence (if user accounts exist)
  -> Backend profile model + storage
  -> Recommendation ranking adjusts with preference weights
```

Suggested incremental plan:
1. Start with client-only preferences (non-persistent) to validate UX.
2. Add backend preference endpoint and storage later.
3. Introduce auth only when persistence across devices is needed.

Trade-off: preference persistence improves personalization but introduces identity/auth complexity.

### 5.4 Going to Production
Checklist:
- [ ] CORS: set `ANIME_WEATHER_CORS_ORIGINS` to real frontend domain (`config.py:55-62`, `main.py:30-36`).
- [ ] Caching: evaluate move from in-memory TTL to Redis for multi-instance deployment.
- [ ] Rate limiting: add per-client and provider-protection limits.
- [ ] Error monitoring: centralize logs and alerts for `5xx` and provider timeouts.
- [ ] HTTPS: enforce TLS on frontend and backend domains.
- [ ] Environment variables: no secrets in git; managed in provider dashboard.
- [ ] Health monitoring: uptime checks for `/api/health` (`health.py:12-18`).
- [ ] Deployment strategy: enable rollback path and smoke tests after deploy.

What would break if you scale to two backend instances with current cache? cache hits become inconsistent across instances and third-party call volume rises.

Trade-off: production hardening increases operational overhead, while reducing incident frequency and user-facing errors.

**Try This (<15 min)**
- Pick one extension: add a new mood label in frontend only, run build, then identify all failing contracts.
- Repeat by adding the same mood end-to-end across backend + frontend and compare effort.

---

## Closing Note
Use this project as a reference for boundary-driven design:
- Python backend handles reliability, transformation, and contracts.
- TypeScript frontend handles interaction, rendering, and presentation safety.
- The most reusable lesson is not any single library. The reusable lesson is how each file has a constrained responsibility, and how failures are contained near system boundaries.
