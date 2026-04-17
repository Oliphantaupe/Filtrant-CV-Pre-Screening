# Filtrant — Automated CV Pre-Screening System

Automated CV screening for **LuxTalent Advisory Group S.A.**
Uploads a CV (PDF, DOCX, or image) → OpenRouter (Gemini 2.0 Flash) parses it into structured JSON → ML model predicts **Invite** or **Reject** → stored in PostgreSQL → visible in a React dashboard.

---

## Architecture

```
[HR uploads via React UI]
              ↓
         FastAPI (backend :8000)
              ↓
    1. Text extraction (pdfplumber / python-docx)
    2. OpenRouter (Gemini 2.0 Flash)  →  Universal JSON schema
    3. ML model  →  Invite / Reject + confidence
    4. Store in PostgreSQL
              ↓
         React dashboard (:3000) reads /api/v1/candidates
```

**Stack:** FastAPI · OpenRouter (`gemini-2.0-flash`) · scikit-learn · PostgreSQL · React + Vite + TypeScript + Tailwind · Docker Compose

---

## Prerequisites

| Tool | Minimum version | Notes |
|---|---|---|
| Docker Desktop or OrbStack | — | Docker Compose v2 required |
| Node.js | 18 LTS | For the frontend dev server |
| Python | 3.11+ | For the local IDE venv and ML retraining |
| OpenRouter API key | — | `sk-or-...` from openrouter.ai/keys |

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
OPENROUTER_API_KEY=sk-or-YOUR_KEY_HERE
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

Then install pre-built wheels (**requires Python 3.11** — see note below):

```bash
# Windows
.venv\Scripts\pip install --only-binary=:all: fastapi uvicorn[standard] python-multipart httpx python-docx pdfplumber scikit-learn pandas numpy joblib pydantic pydantic-settings python-dotenv psycopg2-binary

# macOS / Linux
.venv/bin/pip install --only-binary=:all: fastapi "uvicorn[standard]" python-multipart httpx python-docx pdfplumber scikit-learn pandas numpy joblib pydantic pydantic-settings python-dotenv psycopg2-binary
```

> **Python version** : use **Python 3.11.x** exclusively. Python 3.12+ can cause compatibility issues with scikit-learn and psycopg2. The Docker image is pinned to `python:3.11.12-slim`. Locally, install Python 3.11 from [python.org](https://python.org) and create the venv with it explicitly:
> ```bash
> # Windows — point to your 3.11 install
> "C:\Users\<you>\AppData\Local\Programs\Python\Python311\python.exe" -m venv .venv
> ```

### Point VS Code to the venv

The repo includes `.vscode/settings.json` which sets the interpreter automatically. If VS Code doesn't pick it up:

1. `Ctrl+Shift+P` → **Python: Select Interpreter**
2. Choose `backend/.venv/Scripts/python.exe` (Windows) or `backend/.venv/bin/python` (macOS/Linux)

> This venv is for IDE use only — the application always runs through `docker compose up`.

---

## ML Model

`backend/ml/model.joblib` is gitignored and must be generated before predictions work. Without it, every candidate returns `pending`.

### Training the model

Once you have candidates in the system, export them and run `train.py`:

```bash
# 1 — Export labelled candidates
curl http://localhost:8000/api/v1/candidates/export.csv -o backend/ml/candidates_export.csv

# 2 — Train (picks the best of 3 classifiers, saves model.joblib)
docker compose exec backend python /app/ml/train.py
```

`train.py` compares LogisticRegression, RandomForest, and GradientBoosting, selects the best by AUC-ROC, and saves the pipeline to `model.joblib`. The updated model is loaded on the next prediction call — no restart needed.

### Exploratory analysis

`backend/ml/cv_screening_ml.ipynb` contains the full EDA — distributions, correlation matrix, feature importance charts. Open it in VS Code or JupyterLab.

### First-time setup — raw CV data

The raw CV files and labels are not stored in the repo (private client data). To set them up:

1. Place `student_labels.csv` and `CVs/` folder next to `backend/ml/setup_data.py`
2. Run:
```bash
cd backend/ml
python setup_data.py
```
This processes the raw data into the format the system expects.
3. Upload the CVs through the UI or drop them in `data/incoming_cvs/`, then export and retrain.

---

## File Watcher (auto-processing)

The backend includes a built-in file watcher that polls `data/incoming_cvs/` every 10 seconds. Drop any CV into that folder and it will be processed automatically — parsed, scored, saved to PostgreSQL, and moved to `data/processed_cvs/` on success or `data/failed_cvs/` on failure.

The interval is configurable via the `WATCHER_INTERVAL` env variable (seconds).

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
│   │   ├── cv_screening_ml.ipynb  # EDA notebook (distributions, feature importance)
│   │   ├── train.py               # Training script (compare 3 models → save best)
│   │   ├── setup_data.py          # One-time raw data import helper
│   │   └── model.joblib           # Trained model (gitignored, generated by train.py)
│   └── src/
│       ├── main.py           # FastAPI app entry point
│       ├── config.py         # Env vars (pydantic-settings)
│       ├── db.py             # psycopg2 pool, table creation
│       ├── models/
│       │   └── cv_schema.py  # Pydantic CV schema (universal JSON)
│       ├── services/
│       │   ├── extractor.py       # PDF/DOCX/TXT → raw text + SHA-256
│       │   ├── llm_parser.py      # OpenRouter (Gemini 2.0 Flash) → structured JSON
│       │   ├── features.py        # JSON → ML feature vector
│       │   ├── predictor.py       # Load model, run prediction
│       │   └── watcher.py         # Background task: polls incoming_cvs/ auto-processes
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
├── data/
│   ├── incoming_cvs/         # Drop CVs here — watcher picks them up automatically
│   ├── processed_cvs/        # Moved here on success
│   └── failed_cvs/           # Moved here on failure
│
└── docs/
    └── SPECS.md              # Client requirements (Work Package 1)
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | Your OpenRouter API key (`sk-or-...` from openrouter.ai/keys) |
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
4. Set the `OPENROUTER_API_KEY` environment variable in Railway.

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
