# Filtrant — Claude Rules

## Session Protocol (MANDATORY)

At the **start of every session**, before doing anything else:
1. Read `docs/PLAN.md` — architecture, schema, stack
2. Read `docs/SPECS.md` — client requirements
3. Read `docs/PROGRESS.md` — what's done and what's next

At the **end of every session** (when the user is done or says stop):
1. Update `docs/PROGRESS.md`: check off completed tasks, update the session log table

## Project

- Client: LuxTalent Advisory Group S.A.
- Goal: Automated CV pre-screening — binary output Invite / Reject
- All docs live in `docs/`

## Stack

FastAPI · Claude API (claude-sonnet-4-6) · scikit-learn LogisticRegression · PostgreSQL (psycopg2) · n8n · React + Vite + TypeScript + Tailwind

## Key Conventions

- Backend entry: `backend/src/main.py`
- Config via env vars, loaded in `backend/src/config.py` (pydantic-settings)
- No ORM — raw psycopg2
- CV JSON schema defined in `backend/src/models/cv_schema.py` (Pydantic)
- ML features defined in `backend/src/services/features.py`
- Model returns `"pending"` until `backend/ml/model.joblib` exists
- All API routes prefixed `/api/v1/`
- Frontend proxies `/api` → backend in dev (vite.config.ts)
