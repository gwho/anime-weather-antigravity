# Anime Weather Deployment Runbook
## Vercel (Frontend) + Render (Backend) + Custom Domain

This runbook is the practical companion to the concepts guide.

- Concepts: [VERCEL_RENDER_DEVOPS_GUIDE.md](./VERCEL_RENDER_DEVOPS_GUIDE.md)
- Goal here: exact execution steps to get a public demo URL online.

---

## 0. Outcome You Are Targeting

After finishing this runbook, users should access:
- Frontend: `https://anime-weather.yourdomain.com`
- Backend health: `https://api.anime-weather.yourdomain.com/api/health`

And the frontend should call the backend successfully with no CORS errors.

---

## 1. Prerequisites

## 1.1 Accounts
- GitHub account (repo hosted)
- Vercel account
- Render account
- Domain + DNS provider (Cloudflare, Namecheap, GoDaddy, etc.)

## 1.2 Repo state
From project root, verify:
```bash
make check
cd frontend && npm run build
cd ../backend && ../.venv/bin/python -c "from anime_weather.main import app"
```

## 1.3 Required files already present
- `frontend/` app
- `backend/` app
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `.env.example`

---

## 2. Prepare Production Values

Pick your production domains first:
- `FRONTEND_DOMAIN=anime-weather.yourdomain.com`
- `API_DOMAIN=api.anime-weather.yourdomain.com`

You will use these in both platforms.

---

## 3. Deploy Backend to Render

## 3.1 Create service
1. In Render dashboard, choose **New +** -> **Web Service**.
2. Connect GitHub repo.
3. Select branch (`main`).
4. Service name: `anime-weather-backend`.
5. Region: choose closest to target users.
6. Runtime: **Docker**.
7. Root directory: `backend`.

## 3.2 Configure backend env vars
Set these in Render -> Environment:
- `ANIME_WEATHER_LOG_LEVEL=INFO`
- `ANIME_WEATHER_CACHE_TTL=1800`
- `ANIME_WEATHER_CORS_ORIGINS=https://anime-weather.yourdomain.com`
- `ANIME_WEATHER_REQUEST_TIMEOUT_SECONDS=10`
- `ANIME_WEATHER_CLEANUP_INTERVAL_SECONDS=600`

Do not set `VITE_*` vars here (frontend only).

## 3.3 Health check and instance
- Health check path: `/api/health`
- Plan: start with free/starter appropriate for demo.

## 3.4 Deploy
Click **Create Web Service** and wait until service is live.

## 3.5 Validate backend before domain
Use Render-provided URL first:
```bash
curl -s https://<render-generated-url>/api/health
```
Expected: JSON with `status: "ok"`.

---

## 4. Deploy Frontend to Vercel

## 4.1 Import project
1. In Vercel dashboard, click **Add New** -> **Project**.
2. Import same GitHub repo.
3. Configure project:
   - Framework preset: **Vite**
   - Root directory: `frontend`
   - Build command: `npm run build`
   - Output directory: `dist`

## 4.2 Frontend env vars
Add in Vercel -> Project Settings -> Environment Variables:
- `VITE_API_URL=https://api.anime-weather.yourdomain.com`

Set for Production (and Preview if desired).

## 4.3 Deploy
Click **Deploy**.

## 4.4 Validate frontend before custom domain
Open Vercel URL and confirm:
- App loads.
- Search request attempts hit the configured API URL.

---

## 5. Configure Custom Domains (DNS)

You need two DNS records.

## 5.1 Frontend domain -> Vercel
In Vercel project -> Domains:
1. Add `anime-weather.yourdomain.com`.
2. Follow Vercel-provided DNS target.
   - Usually CNAME to Vercel target value.

## 5.2 API domain -> Render
In Render service -> Custom Domains:
1. Add `api.anime-weather.yourdomain.com`.
2. Add DNS record in your provider using Render target.
   - Usually CNAME to Render hostname.

## 5.3 Wait for SSL issuance
Both platforms will provision TLS automatically after DNS resolves.

## 5.4 Confirm both endpoints
```bash
curl -s https://api.anime-weather.yourdomain.com/api/health
```
Then open:
- `https://anime-weather.yourdomain.com`

---

## 6. CORS Finalization

Set backend CORS strictly to frontend origin:
- `ANIME_WEATHER_CORS_ORIGINS=https://anime-weather.yourdomain.com`

If you need multiple origins, comma-separate:
- `https://anime-weather.yourdomain.com,https://preview-domain.vercel.app`

After changing env vars, trigger backend redeploy.

---

## 7. Post-Deploy Smoke Tests

Run these checks in order.

## 7.1 Backend API checks
```bash
curl -s https://api.anime-weather.yourdomain.com/api/health
curl -s "https://api.anime-weather.yourdomain.com/api/forecast?city=Tokyo"
curl -s "https://api.anime-weather.yourdomain.com/api/forecast?lat=35.6762&lon=139.6503"
```

## 7.2 Browser checks
1. Open frontend domain.
2. Search city (`Tokyo`, `Hong Kong`, `New York`).
3. Expand day cards; verify anime details render.
4. Check browser devtools:
   - no CORS errors
   - no mixed-content warnings
   - API requests target `api.anime-weather.yourdomain.com`

## 7.3 Failure checks
Temporarily test a bad city (`zzzzzzzz`) and confirm user-friendly error state.

---

## 8. Git-Based Auto Deploy (CD)

Recommended settings:
- Vercel: auto deploy on push to `main`
- Render: auto deploy on push to `main`

Optional safer flow:
- Preview deploys from PRs
- Production deploy only from `main`

---

## 9. CI Quality Gate (Before Merge)

Add a GitHub Actions workflow (recommended) that runs:
```bash
make check
cd frontend && npm run build
```

Rule: merges to `main` only when CI passes.

---

## 10. Rollback Runbook

## 10.1 Frontend rollback (Vercel)
1. Open project -> Deployments.
2. Pick last healthy deployment.
3. Promote/redeploy it.

## 10.2 Backend rollback (Render)
1. Open service -> Deploys.
2. Pick previous healthy deploy.
3. Roll back.

## 10.3 Immediate triage
1. Check `/api/health`.
2. Check backend logs for traceback.
3. Verify env vars didn’t regress.
4. Validate CORS origin value.

---

## 11. Observability Setup (Minimum)

## 11.1 Logs
- Render logs: monitor errors/timeouts.
- Vercel logs: monitor frontend runtime/build failures.

## 11.2 Uptime monitor
Add external monitor for:
- `https://api.anime-weather.yourdomain.com/api/health`

Alert on non-200 responses.

## 11.3 Error budget mindset
For demo app, target simple SLO:
- health endpoint uptime >= 99%

---

## 12. Security Checklist

- [ ] `.env` is ignored by git
- [ ] no secrets in repo history
- [ ] MFA enabled on GitHub/Vercel/Render
- [ ] least-privilege tokens for CI
- [ ] production CORS does not use wildcard unless unavoidable
- [ ] dependencies updated periodically

---

## 13. Cost Control Checklist

- [ ] understand free-tier sleep/cold-start behavior
- [ ] set usage alerts if available
- [ ] disable unnecessary preview deployments if costs rise
- [ ] keep log retention lean

---

## 14. Common Problems and Fixes

## Problem: frontend shows "Network error"
Checks:
1. Is `VITE_API_URL` correct in Vercel env vars?
2. Did frontend redeploy after env var change?
3. Is backend domain healthy in browser/curl?

## Problem: CORS blocked in browser
Fix:
1. Set `ANIME_WEATHER_CORS_ORIGINS` to exact frontend origin.
2. Redeploy backend.
3. Hard refresh frontend.

## Problem: first request is slow
Cause:
- free-tier cold start.
Mitigation:
- Accept for demo, or upgrade backend plan.

## Problem: anime provider throttled/down
Behavior:
- backend fallback chain should still return recommendations.
Action:
- inspect backend logs; verify graceful fallback is active.

---

## 15. Operations Cheat Sheet

## Local
```bash
make install
make dev
make check
```

## Docker local dev
```bash
docker compose --profile dev up --build
```

## Docker production-like
```bash
docker compose --profile prod up --build -d
```

---

## 16. Launch Day Sequence (Fast Path)

1. Merge latest stable code to `main`.
2. Deploy backend on Render (root `backend`).
3. Deploy frontend on Vercel (root `frontend`).
4. Configure custom domains (frontend + api).
5. Set/update env vars (`VITE_API_URL`, CORS).
6. Redeploy both services.
7. Run smoke tests.
8. Share public URL.

---

## 17. Optional Next Improvements

- Add GitHub Actions workflow with required checks.
- Add status page link in README.
- Add structured JSON logging in backend.
- Add synthetic monitor for a full forecast request path.

