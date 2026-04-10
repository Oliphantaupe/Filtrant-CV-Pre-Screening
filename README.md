# Filtrant — Automated CV Pre-Screening System

Automated CV screening for **LuxTalent Advisory Group S.A.**
Uploads a CV (PDF, DOCX, or image) → Claude API parses it into structured JSON → ML model predicts **Invite** or **Reject** → stored in PostgreSQL → visible in a React dashboard.

---

## Architecture

```
[HR uploads via React UI]
              ↓
         FastAPI (backend :8000)
              ↓
    1. Text extraction (pdfplumber / python-docx)
    2. Claude API  →  Universal JSON schema
    3. ML model  →  Invite / Reject + confidence
    4. Store in PostgreSQL
              ↓
         React dashboard (:3000) reads /api/v1/candidates
```

**Stack:** FastAPI · Claude API (`claude-haiku-4-5`) · scikit-learn · PostgreSQL · React + Vite + TypeScript + Tailwind · Docker Compose

---

## Prerequisites

| Tool | Minimum version | Notes |
|---|---|---|
| Docker Desktop | 4.x | Includes Docker Compose v2 |
| Node.js | 18 LTS | For the frontend dev server |
| Python | 3.11+ | For the local IDE venv and ML retraining |
| Anthropic API key | — | `sk-ant-...` from console.anthropic.com |

> **VS Code users:** the Python extension (`ms-python.python`) is strongly recommended. The repo ships a `.vscode/settings.json` that points to the local venv automatically — see [IDE Setup](#ide-setup-vs-code) below.

---

## Quick Start (local, Docker Compose)

### 1 — Clone and configure

```bash
git clone https://github.com/<your-org>/filtrant.git
cd filtrant
cp .env.example .env
```

Open `.env` and fill in your key:

```
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
```

Leave the rest as-is for local development.

### 2 — Start the stack

```bash
docker compose up --build
```

This starts two containers:

| Container | Port | Description |
|---|---|---|
| `backend` | 8000 | FastAPI + auto-creates DB tables on first boot |
| `postgres` | 5432 | PostgreSQL 16, data persisted in a named volume |

Wait until you see:
```
backend   | INFO:     Application startup complete.
```

### 3 — Start the frontend

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### 4 — Test it

1. Go to the **Upload** tab in the UI.
2. Drag and drop any PDF or DOCX CV.
3. The system returns `Invite` or `Reject` with a confidence score within a few seconds.
4. Switch to **Candidates** to see all processed CVs with filters.

Or test directly via curl:

```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@path/to/cv.pdf"
```

Health check:

```bash
curl http://localhost:8000/api/v1/health
```

---

## IDE Setup (VS Code)

The app runs inside Docker, but your IDE needs the packages locally to resolve imports and show IntelliSense instead of red underlines.

### Create the local venv (one-time, per machine)

```bash
cd backend
python -m venv .venv
```

Then install pre-built wheels (no compiler required — works on Python 3.11–3.13):

```bash
# Windows
.venv\Scripts\pip install --only-binary=:all: fastapi uvicorn[standard] python-multipart "anthropic>=0.40.0" python-docx pdfplumber scikit-learn pandas numpy joblib pydantic pydantic-settings python-dotenv psycopg2-binary

# macOS / Linux
.venv/bin/pip install --only-binary=:all: fastapi "uvicorn[standard]" python-multipart "anthropic>=0.40.0" python-docx pdfplumber scikit-learn pandas numpy joblib pydantic pydantic-settings python-dotenv psycopg2-binary
```

### Point VS Code to the venv

The repo includes `.vscode/settings.json` which sets the interpreter automatically. If VS Code doesn't pick it up:

1. `Ctrl+Shift+P` → **Python: Select Interpreter**
2. Choose `backend/.venv/Scripts/python.exe` (Windows) or `backend/.venv/bin/python` (macOS/Linux)

> This venv is for IDE use only — the application always runs through `docker compose up`.

---

## ML Model

The repo ships with a pre-trained `backend/ml/model.joblib` (LogisticRegression, trained on a synthetic 40-row dataset). It is gitignored by default — commit it intentionally once you have a real trained model.

### Retraining on real data

Export labelled candidates first:

```bash
curl http://localhost:8000/api/v1/candidates/export.csv -o candidates.csv
```

Manually add a `recommendation` column (`Invite` / `Reject`) to the CSV if it is not already labelled, then:

```bash
cd backend
pip install -r requirements.txt
python ml/train.py --data path/to/candidates.csv
```

The updated `ml/model.joblib` is loaded automatically on the next container restart (the volume mounts `./backend/ml` into the container).

---

## API Reference

All endpoints are prefixed `/api/v1/`.

| Method | Path | Description |
|---|---|---|
| `POST` | `/upload` | Upload a CV file (multipart) → parse → predict → store. Returns the full candidate record. |
| `GET` | `/candidates` | Paginated list. Query params: `page`, `page_size`, `recommendation` (`Invite`/`Reject`/`pending`), `date_from`, `date_to`. |
| `GET` | `/candidates/{id}` | Full candidate record including raw CV JSON. |
| `GET` | `/candidates/export.csv` | ML-ready CSV of all candidates (features + recommendation). |
| `GET` | `/health` | Returns DB status and model file presence. |

---

## Project Structure

```
filtrant/
├── .env.example              # Copy to .env and fill in your key
├── docker-compose.yml        # backend + postgres
├── .gitignore
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── ml/
│   │   ├── train.py          # Run to retrain the model
│   │   └── model.joblib      # Pre-trained model (gitignored, commit manually)
│   └── src/
│       ├── main.py           # FastAPI app entry point
│       ├── config.py         # Env vars (pydantic-settings)
│       ├── db.py             # psycopg2 pool, table creation
│       ├── models/
│       │   └── cv_schema.py  # Pydantic CV schema (universal JSON)
│       ├── services/
│       │   ├── extractor.py       # PDF/DOCX/TXT → raw text + SHA-256
│       │   ├── claude_parser.py   # Claude API → structured JSON
│       │   ├── features.py        # JSON → ML feature vector
│       │   └── predictor.py       # Load model, run prediction
│       └── routers/
│           ├── upload.py     # POST /upload
│           └── export.py     # GET /candidates, /export.csv
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts        # Proxies /api → backend in dev
│   └── src/
│       ├── App.tsx
│       ├── api/client.ts     # Typed API client
│       ├── types/cv.ts       # TypeScript types matching Pydantic schema
│       ├── utils/date.ts     # Shared date helpers
│       ├── components/       # AnimatedBackground, DatePicker, ScrollArea, etc.
│       └── pages/
│           ├── DashboardPage.tsx    # Stats, activity chart, recent uploads
│           ├── UploadPage.tsx       # Drag-and-drop upload + result
│           └── CandidatesPage.tsx   # Paginated candidates + detail modal
│
└── docs/
    └── SPECS.md              # Client requirements (Work Package 1)
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key |
| `DATABASE_URL` | Yes | PostgreSQL connection string. Set automatically by Railway in production. |
| `ENV` | No | `development` (default) or `production` |
| `LOG_LEVEL` | No | `INFO` (default) |
| `VITE_API_BASE_URL` | Frontend only | API base URL. Defaults to `http://localhost:8000` in dev (proxy handles it). Set to the Railway backend URL in production. |

---

## Deployment

### Railway (backend + PostgreSQL)

1. Create a new Railway project.
2. Add a **PostgreSQL** plugin — Railway injects `DATABASE_URL` automatically.
3. Add a service from this repo, set root to `backend/`, Dockerfile is auto-detected.
4. Set the `ANTHROPIC_API_KEY` environment variable in Railway.

### Vercel (frontend)

1. Import the repo in Vercel, set root to `frontend/`.
2. Vite is auto-detected.
3. Add env var: `VITE_API_BASE_URL=https://<your-railway-backend-url>`.

---

## Stopping / Cleaning Up

```bash
# Stop containers (preserves data volumes)
docker compose down

# Stop and remove volumes (wipes the database)
docker compose down -v
```
