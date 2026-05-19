# Railway Deployment Guide

Filtrant runs as three Railway services inside a single project:

| Service | Root dir | Build | Port |
|---|---|---|---|
| `filtrant-backend` | `backend/` | `backend/Dockerfile` | auto (`$PORT`) |
| `filtrant-frontend` | `frontend/` | `frontend/Dockerfile` | `80` (hardcoded) |
| `filtrant-postgres` | — | Railway-managed PostgreSQL | — |

Railway picks up `backend/railway.toml` and `frontend/railway.toml` automatically based on each service's root directory.

---

## Backend — Environment Variables

Set these under **filtrant-backend → Variables**:

```
ANTHROPIC_API_KEY=sk-ant-api03-...        # Required for CV parsing via Claude
CORS_ORIGINS=https://filtrant-frontend-production.up.railway.app  # Frontend URL
ENV=production
```

| Variable | Required | Default | Notes |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Recommended | `""` | CV parsing degrades without it; app still starts |
| `CORS_ORIGINS` | Yes | `*` | Set to frontend URL once known; comma-separated for multiple |
| `ENV` | No | `development` | Controls log verbosity and error detail |
| `LOG_LEVEL` | No | `INFO` | |
| `DATABASE_URL` | Auto | — | **Do not set** — Railway Postgres injects this automatically |

> `DATABASE_URL` is injected by the Railway Postgres service. The backend coerces `postgres://` → `postgresql://` automatically so psycopg2 can connect.

---

## Frontend — Build Variables

Set these under **filtrant-frontend → Variables** (they are baked in at build time by Vite, not available at runtime):

```
VITE_API_BASE_URL=https://filtrant-backend-production.up.railway.app
PORT=80
```

| Variable | Required | Notes |
|---|---|---|
| `VITE_API_BASE_URL` | Yes | Full backend URL, no trailing slash. Baked into the JS bundle at build time. |
| `PORT` | Yes | Must be `80` — tells Railway to route traffic to nginx's port. |

> If `VITE_API_BASE_URL` is not set the frontend builds fine but all API calls silently go to the frontend's own origin and fail.

---

## PostgreSQL — No configuration needed

Add the Railway Postgres plugin to the project. It automatically:
- Provisions the database
- Injects `DATABASE_URL` into all services in the project
- The backend creates all tables on first startup (`candidates`, `processing_log`)

---

## Deployment order

1. **Deploy Postgres** first (or add it as a plugin — it's instant).
2. **Deploy backend** — get its public URL from Railway once healthy (`/api/v1/health` returns `{"status":"ok"}`).
3. **Set `VITE_API_BASE_URL`** on the frontend service using the backend URL, then deploy frontend.
4. **Once the frontend URL is known**, update `CORS_ORIGINS` on the backend to the frontend URL and redeploy backend.

---

## Health checks

| Service | Path | Timeout |
|---|---|---|
| Backend | `GET /api/v1/health` | 300 s |
| Frontend | `GET /` | 120 s |

The backend health check verifies DB connectivity and model file presence. It returns `200` even if `db: false` (degraded) so Railway doesn't restart a running instance just because a query failed momentarily.

---

## Troubleshooting

**Frontend 502 / connection refused**
- Confirm `PORT=80` is set in Railway frontend variables.
- nginx listens on port 80. Railway must be told to route to 80 via the `PORT` variable.

**Backend `{"detail": "Not Found"}` at root URL**
- Expected — FastAPI has no route at `/`. Hit `/api/v1/health` to confirm the backend is healthy.

**CV parsing returns no structured data**
- Check that `ANTHROPIC_API_KEY` is set on the backend service.

**CORS errors in browser**
- `CORS_ORIGINS` on the backend must include the exact frontend URL (no trailing slash).
