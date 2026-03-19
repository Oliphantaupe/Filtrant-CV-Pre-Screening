# Filtrant — Architecture Plan

## Overview

CV received in any format → Claude API extracts structured JSON → ML model predicts Invite/Reject → stored in PostgreSQL → displayed in React dashboard.

---

## Architecture

```
[HR uploads CV via React UI]  OR  [n8n file-watch trigger]
              ↓
         FastAPI (Railway)
              ↓
    1. Extract text (PyPDF2 / python-docx / Claude vision for images)
    2. Claude API → Universal JSON schema
    3. ML model → Invite/Reject + confidence
    4. Store in PostgreSQL (Railway)
              ↓
         React (Vercel) reads candidates API
```

---

## Tool Stack

| Tool | Role |
|---|---|
| **FastAPI** | REST API backend |
| **Claude API** | CV parsing → universal JSON (any format, any layout, image OCR) |
| **PyPDF2 + python-docx** | Text extraction from PDF/DOCX before Claude |
| **scikit-learn** | LogisticRegression — Invite/Reject (trained on real historical data) |
| **PostgreSQL** | Candidate storage (Railway add-on) |
| **psycopg2** | Direct DB access, no ORM |
| **pandas** | ML-ready CSV export |
| **n8n** | Automation: file-watch → POST /api/v1/upload |
| **React + Vite + TypeScript** | Frontend dashboard |
| **Tailwind CSS** | Styling |
| **Railway** | Backend + PostgreSQL + n8n (premium) |
| **Vercel** | Frontend public URL |
| **Docker Compose** | Local development |

---

## Universal JSON Schema

Every CV becomes this structure (Claude API output, Pydantic-validated):

```json
{
  "personal": {
    "full_name": "Olivia Martinez",
    "email": "olivia@example.com",
    "phone": "+1-555-214-7783",
    "address": "Denver, CO, USA"
  },
  "target_role": "Senior Data Analyst",
  "summary": "...",
  "education": [
    { "degree": "BSc", "field": "Statistics", "institution": "...", "year": 2012, "level_score": 3 }
  ],
  "experience": [
    { "title": "Senior Data Analyst", "company": "...", "start": "2016-10", "end": "2025-12", "duration_months": 110 }
  ],
  "skills": {
    "technical": ["Python", "SQL", "Tableau"],
    "methods": ["A/B testing", "Regression"],
    "management": ["Team leadership"]
  },
  "languages": [{ "language": "English", "level": "C2", "level_score": 6 }],
  "certifications": [{ "name": "Certified Analytics Professional", "year": 2018 }],
  "parse_quality": "complete",
  "missing_fields": []
}
```

---

## ML Features

Derived from the parsed JSON (pure Python, `features.py`):

| Feature | Type |
|---|---|
| `total_years_experience` | float |
| `num_positions` | int |
| `avg_tenure_months` | float |
| `education_level_score` | int (1–5) |
| `total_skills_count` | int |
| `has_certifications` | 0/1 |
| `language_count` | int |
| `section_completeness_score` | int (0–5) |

Model: `LogisticRegression` (scikit-learn). Trained on real historical data when available. Until then, prediction returns `"pending"`.

---

## Database Schema

```sql
CREATE TABLE candidates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  processed_at TIMESTAMPTZ DEFAULT NOW(),
  source_filename TEXT NOT NULL,
  source_format TEXT NOT NULL,
  parse_quality TEXT NOT NULL,
  cv_data JSONB NOT NULL,
  recommendation TEXT NOT NULL,   -- "Invite" | "Reject" | "pending"
  confidence NUMERIC(4,3),
  file_hash TEXT UNIQUE,
  missing_fields JSONB DEFAULT '[]'
);

CREATE TABLE processing_log (
  id SERIAL PRIMARY KEY,
  candidate_id UUID REFERENCES candidates(id),
  event TEXT NOT NULL,
  detail TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/upload` | Upload file → parse → predict → store → return result |
| `GET` | `/api/v1/candidates` | List (paginated, filter by date/recommendation) |
| `GET` | `/api/v1/candidates/{id}` | Full CV JSON |
| `GET` | `/api/v1/candidates/export.csv` | ML-ready CSV |
| `GET` | `/api/v1/health` | DB + Claude health check |

---

## Project Structure

```
filtrant/
├── docker-compose.yml           # backend + n8n
├── .env.example
├── .gitignore
├── PLAN.md                      # this file
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── ml/
│   │   ├── train.py             # run when data is ready
│   │   └── model.joblib         # committed after training
│   └── src/
│       ├── main.py
│       ├── config.py
│       ├── db.py
│       ├── models/cv_schema.py
│       └── services/
│           ├── extractor.py
│           ├── claude_parser.py
│           ├── features.py
│           └── predictor.py
│       └── routers/
│           ├── upload.py
│           └── export.py
│
├── frontend/
│   └── src/
│       ├── App.tsx
│       ├── api/client.ts
│       ├── types/cv.ts
│       └── pages/
│           ├── UploadPage.tsx
│           └── CandidatesPage.tsx
│
├── n8n/
│   └── workflows/cv-screening.json
│
└── data/
    ├── incoming_cvs/
    ├── processed_cvs/
    └── failed_cvs/
```

---

## n8n Automation

1. **File Watch** → polls `data/incoming_cvs/` every 30s
2. **HTTP Request** → `POST /api/v1/upload` with file
3. **IF success** → move to `processed_cvs/`, else → `failed_cvs/`

---

## Deployment

**Railway (backend + DB + n8n):**
- `backend` service: root `backend/`, Dockerfile
- `postgres` service: Railway PostgreSQL add-on (auto-injects `DATABASE_URL`)
- `n8n` service: image `n8nio/n8n`

**Vercel (frontend):**
- Root `frontend/`, Vite auto-detected
- Env: `VITE_API_BASE_URL=https://filtrant-backend.railway.app`
