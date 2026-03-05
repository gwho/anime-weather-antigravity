# Anime Weather DevOps Guide (Option 3)
## Vercel (Frontend) + Render (Backend)

This guide explains how to operate **Anime Weather** online as a demo using:
- **Frontend**: Vercel (React/Vite static hosting + CDN)
- **Backend**: Render (FastAPI service)

It is intentionally written as a **DevOps learning document**, not just a checklist.

---

## 1. Why This Architecture

For a demo app, this split is a strong balance:
- Vercel is optimized for frontend deploys and global edge delivery.
- Render is simple for backend services and supports Docker or native Python deploys.
- Each tier can scale independently.
- You avoid managing your own VM, TLS, reverse proxy, and patching.

Tradeoff:
- You manage two platforms, two dashboards, and cross-origin settings (CORS).

---

## 2. Target Architecture

```text
User Browser
   |
   | HTTPS (anime-weather.yourdomain.com)
   v
Vercel (Frontend CDN + Static Assets)
   |
   | HTTPS API calls (api.anime-weather.yourdomain.com)
   v
Render Web Service (FastAPI)
   |
   +--> Open-Meteo API
   +--> Jikan API
   +--> AniList API
   +--> Animechan API
```

Key point: Browser talks to two origins unless you configure custom domains under one parent domain.

---

## 3. Core DevOps Concepts You’ll Use

## 3.1 Environment Separation
Use at least:
- `local` (your laptop)
- `preview` (PR/test deploys)
- `production` (public demo)

Why it matters:
- Avoid testing experimental code directly in production.
- Keep environment-specific URLs and settings out of source code.

## 3.2 Configuration as Environment Variables (12-Factor)
Never hardcode environment-specific values. Use:
- Frontend: `VITE_API_URL`
- Backend: `ANIME_WEATHER_*` variables

Why:
- Same code artifact can run in different environments.
- Safer secret handling.

## 3.3 CI vs CD
- **CI**: run checks on every push/PR (type checks, build, lint, tests).
- **CD**: deploy automatically when main branch is updated.

You want fast CI feedback before deployment.

## 3.4 Immutable Build Artifacts
Each commit should produce a deterministic build:
- Frontend: locked via `package-lock.json`
- Backend Docker image: pinned base image tag

This helps reproducibility and rollback reliability.

## 3.5 Health Checks and Readiness
Your backend exposes `/api/health`.
Use it to detect startup failures early and verify service status during incidents.

## 3.6 Observability
Three pillars:
- **Logs**: request errors, external API failures, stack traces
- **Metrics**: request count, latency, error rate
- **Tracing** (optional): request journey across components

For demo stage, logs + uptime checks are enough.

## 3.7 Reliability Basics
- Timeouts on external API calls (already in backend)
- Graceful fallbacks (already in backend anime sourcing)
- Retry strategy for transient failures (careful with rate limits)
- Clear user-facing error states in frontend (already implemented)

## 3.8 Security Basics
- Principle of least privilege on platform access
- No secrets in git
- Restrictive CORS in production (no `*` once domain is known)
- Keep dependencies updated

---

## 4. Deployment Blueprint (Conceptual)

## 4.1 Frontend on Vercel
Project source: `frontend/`

Typical settings:
- Framework preset: Vite
- Build command: `npm run build`
- Output directory: `dist`
- Root directory: `frontend`
- Env var: `VITE_API_URL=https://api.anime-weather.yourdomain.com`

Result:
- Static assets served via CDN
- Fast global loading

## 4.2 Backend on Render
Project source: `backend/`

Two possible modes:
1. Native Python service (start command using uvicorn)
2. Docker service (uses `backend/Dockerfile`)

Recommended for your repo consistency: **Docker deploy**.

Key env vars on Render:
- `ANIME_WEATHER_LOG_LEVEL=INFO`
- `ANIME_WEATHER_CACHE_TTL=1800`
- `ANIME_WEATHER_CORS_ORIGINS=https://anime-weather.yourdomain.com`
- Any additional backend settings you expose

Health check path:
- `/api/health`

---

## 5. DNS and Domain Strategy

Recommended domain split:
- Frontend: `anime-weather.yourdomain.com`
- API: `api.anime-weather.yourdomain.com`

Why this is better than random provider URLs:
- Stable branding and cleaner API URL management
- Easier future migration without frontend code churn

DNS flow:
1. Point frontend domain to Vercel
2. Point API subdomain to Render
3. Update `VITE_API_URL` to API subdomain
4. Tighten backend CORS to frontend domain

---

## 6. CORS Knowledge (Important)

CORS controls browser access from one origin to another.

For this architecture:
- Browser origin: `https://anime-weather.yourdomain.com`
- API origin: `https://api.anime-weather.yourdomain.com`

Backend must allow the frontend origin explicitly.

Common failure symptom:
- App works in curl/Postman but fails in browser console with CORS errors.

Production best practice:
- `ANIME_WEATHER_CORS_ORIGINS=https://anime-weather.yourdomain.com`
- Avoid wildcard (`*`) in production when possible.

---

## 7. CI/CD Pipeline Design (Recommended)

## 7.1 PR Pipeline (Quality Gate)
On pull request:
1. Backend static checks (mypy/lint/tests)
2. Frontend type check + build
3. Optional security scan (dependencies)

Goal: block broken code before merge.

## 7.2 Main Branch Pipeline (Release)
On merge to `main`:
1. Re-run checks
2. Deploy backend (Render auto deploy)
3. Deploy frontend (Vercel auto deploy)
4. Run smoke checks:
   - `GET /api/health`
   - frontend loads and fetches forecast

## 7.3 Rollback Strategy
- Vercel: redeploy previous successful deployment
- Render: rollback to previous service deploy/image

Always keep last-known-good release noted in changelog/release notes.

---

## 8. Infrastructure as Code (IaC) in This Setup

You can still apply IaC principles even with managed platforms:

1. **Git as source of truth**
- Dockerfiles, compose, Makefile, env templates in repo

2. **Automated provisioning where possible**
- Vercel has Terraform provider support
- Render has API/blueprint approaches (and community tooling)

3. **Declarative environment docs**
- `.env.example` defines required configuration contract

Pragmatic approach for demo:
- Start with platform UI for first deploy
- Then codify repeated settings in scripts/Terraform over time

---

## 9. Security and Secrets Management

## 9.1 What to keep out of git
- `.env`
- API keys if added later
- provider access tokens

## 9.2 Where to store secrets
- Vercel project env vars
- Render service env vars
- GitHub Actions secrets for CI/CD tokens

## 9.3 Access controls
- Enable MFA on GitHub/Vercel/Render
- Restrict production deploy permissions
- Prefer scoped tokens over full-access tokens

---

## 10. Cost and Usage Controls (Demo-Friendly)

Even on hobby tiers:
- Set uptime expectations (free tiers may sleep/cold start)
- Add usage limits/alerts in provider dashboards
- Keep logs retention minimal unless debugging

If backend sleeps and first request is slow:
- Explain this in README as expected demo behavior.

---

## 11. Monitoring and Incident Playbook

Minimal but effective playbook:

1. **Symptom**: frontend shows API error
2. Check backend health endpoint
3. Check Render logs for stack traces/timeouts
4. Confirm CORS/env var correctness
5. Verify third-party API status/rate limiting
6. Roll back recent deployment if needed

Add an external uptime monitor for:
- `https://api.anime-weather.yourdomain.com/api/health`

---

## 12. Performance Notes

Frontend:
- Vite build is already optimized
- CDN caches static assets
- Keep bundle size in check (lazy loading if needed)

Backend:
- In-memory TTL cache reduces external API calls
- Keep request timeouts conservative
- Avoid over-aggressive retries to external APIs

---

## 13. Suggested Operational Standards

Use simple standards even for demo:
- Branch naming: `feature/*`, `fix/*`
- Conventional commit messages (optional but useful)
- One-line release notes per production deploy
- A short runbook in repo (`docs/`) for common failures

---

## 14. Pre-Launch Checklist

- [ ] `make check` passes locally
- [ ] Frontend build passes (`npm run build`)
- [ ] Backend health endpoint works
- [ ] Correct production `VITE_API_URL`
- [ ] Correct production `ANIME_WEATHER_CORS_ORIGINS`
- [ ] Custom domains configured
- [ ] HTTPS verified on both domains
- [ ] Smoke test: city search + geolocation path
- [ ] Rollback path tested at least once

---

## 15. What to Learn Next (High-ROI)

1. Add GitHub Actions CI workflow for `make check`
2. Add preview deploy validation on pull requests
3. Add lightweight uptime monitoring + alerting
4. Add structured logging fields (request ID, endpoint, latency)
5. Add dependency security scanning in CI

---

## 16. Summary

Option 3 is a strong demo architecture:
- fast to publish,
- low operational burden,
- still teaches real DevOps practices (CI/CD, env management, CORS, observability, rollback, and IaC mindset).

You can start simple and evolve toward full IaC incrementally without re-platforming.
