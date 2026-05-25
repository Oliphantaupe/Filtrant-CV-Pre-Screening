# System Architecture — Filtrant WP1

> **LuxTalent Advisory Group S.A.** · Work Package 1 · Automated CV Pre-Screening System

---

## 1. Overview

Filtrant is an end-to-end automated CV screening system. It ingests CVs in any format (PDF, DOCX, TXT), extracts structured information using a large language model, applies a trained ML classifier, and exposes the results through a web dashboard for HR staff.

```
┌─────────────────────────────────────────────────────────────────┐
│                        HR Staff (Browser)                       │
│              React Dashboard  ·  Upload UI  ·  Candidates list  │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP (REST API)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend (:8000)                    │
│                                                                 │
│   ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│   │  /upload    │  │  /candidates │  │  /candidates/{id}    │  │
│   │  POST       │  │  GET (list)  │  │  GET (detail)        │  │
│   └──────┬──────┘  └──────────────┘  └──────────────────────┘  │
│          │                                                       │
│   ┌──────▼──────────────────────────────────────────────────┐   │
│   │                  Processing Pipeline                    │   │
│   │                                                         │   │
│   │  extractor.py  →  llm_parser.py  →  features.py  →     │   │
│   │  Text extract     Claude Haiku      19 features         │   │
│   │  (PDF/DOCX/TXT)   structured JSON   engineered          │   │
│   │                                         │               │   │
│   │                                  predictor.py           │   │
│   │                                  ML model inference     │   │
│   │                                  Invite / Reject        │   │
│   └─────────────────────────────────────────────────────────┘   │
│                               │                                  │
│                        ┌──────▼──────┐                          │
│                        │  PostgreSQL  │                          │
│                        │  candidates  │                          │
│                        │  proc. log   │                          │
│                        └─────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
                               ▲
                               │ File system polling (every 10s)
                    ┌──────────┴──────────┐
                    │   data/incoming_cvs/ │  ← Drop CV files here
                    │   watcher.py         │     for auto-processing
                    └─────────────────────┘
```

---

## 2. Component Description

### 2.1 Frontend — React Dashboard

**Technology:** React 18 · TypeScript · Vite · Tailwind CSS · Framer Motion

| Page | Purpose |
|---|---|
| **Dashboard** | Overview stats (total CVs, invite rate, avg confidence, activity chart) |
| **Candidates** | Paginated list with filters (recommendation, date range, search) · Detail modal |
| **Upload CV** | Drag-and-drop multi-file upload with real-time status per file |

The frontend communicates exclusively with the backend REST API. It holds no business logic — all processing happens server-side.

### 2.2 Backend — FastAPI

**Technology:** Python 3.11 · FastAPI · Pydantic · psycopg2

The backend exposes a REST API and orchestrates the processing pipeline. It runs two concurrent tasks at startup:
- The **HTTP server** (uvicorn) handling API requests
- The **file watcher** (asyncio background task) polling `data/incoming_cvs/`

Key modules:

| Module | Role |
|---|---|
| `routers/upload.py` | Receives CV files via HTTP, runs the full pipeline, stores result |
| `routers/export.py` | Lists candidates, exports CSV, serves candidate detail |
| `services/extractor.py` | Extracts raw text from PDF / DOCX / TXT files |
| `services/llm_parser.py` | Calls Anthropic Claude Haiku 4.5 to parse CV text into structured JSON |
| `services/features.py` | Computes 19 numerical features from the structured CV |
| `services/predictor.py` | Loads the ML model and returns Invite/Reject + confidence score |
| `services/watcher.py` | Background task that processes files dropped in `data/incoming_cvs/` |

### 2.3 ML Model

**Technology:** scikit-learn · joblib · imbalanced-learn

The model is a **Logistic Regression** (L2, `class_weight='balanced'`) selected automatically from 6 candidate algorithms by cross-validated F1 score. It is trained offline on `training_dataset.csv` (500 labelled CVs) and saved as `ml/model.joblib`.

At inference time, `predictor.py` loads the artifact and computes:
1. The binary prediction (Invite / Reject)
2. The confidence score (probability of the predicted class)

### 2.4 Database — PostgreSQL

**Technology:** PostgreSQL 16 · psycopg2 connection pool

Two tables, created automatically on first boot:

| Table | Purpose |
|---|---|
| `candidates` | One row per processed CV — stores structured data, recommendation, confidence |
| `processing_log` | Audit trail — one row per event (uploaded, parse_failed, etc.) |

### 2.5 File Watcher

`services/watcher.py` polls `data/incoming_cvs/` every 10 seconds. When a new file appears, it runs the same pipeline as the HTTP upload endpoint. Processed files move to `data/processed_cvs/`; failed files move to `data/failed_cvs/`.

This enables **drop-and-forget** automation: HR staff can drop CVs into a shared folder without touching the web interface.

---

## 3. Deployment Architecture

```
┌──────────────────────────────────────────────────────┐
│                    Docker Compose                    │
│                                                      │
│  ┌─────────────────┐      ┌──────────────────────┐  │
│  │    backend      │      │      postgres         │  │
│  │  FastAPI :8000  │ ───► │  PostgreSQL :5432     │  │
│  │  Python 3.11    │      │  Volume: pg_data       │  │
│  └────────┬────────┘      └──────────────────────┘  │
│           │ health check → /api/v1/health            │
│           │ depends_on: postgres (healthy)           │
│  ┌────────┴────────┐                                 │
│  │  Shared volumes │                                 │
│  │  ./data:/app/data  (CVs)                          │
│  │  ./ml:/app/ml      (model.joblib)                 │
│  └─────────────────┘                                 │
└──────────────────────────────────────────────────────┘

Frontend: served separately (npm run dev locally / Vercel in prod)
```

**Environment variables** (`.env`):

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude Haiku |
| `DATABASE_URL` | PostgreSQL connection string |
| `CORS_ORIGINS` | Allowed frontend origins (comma-separated or `*`) |
| `MAX_FILE_SIZE_MB` | Maximum uploaded file size (default: 5 MB) |

---

## 4. Technology Stack Summary

| Layer | Technology | Version | Justification |
|---|---|---|---|
| Frontend | React + TypeScript | 18 / 5.x | Component-based UI, type safety |
| Frontend build | Vite | 5.x | Fast HMR, optimised production builds |
| Frontend styling | Tailwind CSS + Framer Motion | 3.x / 12.x | Utility-first, smooth animations |
| Backend | FastAPI | 0.111 | Async, auto-docs, Pydantic validation |
| LLM | Anthropic Claude Haiku 4.5 | latest | Best-in-class structured extraction |
| ML | scikit-learn + imbalanced-learn | 1.5 / 0.12 | Standard, reproducible, explainable |
| Database | PostgreSQL | 16 | Reliable, JSONB for CV data |
| Containerisation | Docker Compose | v2 | Single-command startup |
| ORM/driver | psycopg2 | 2.9 | Direct SQL, connection pool |
