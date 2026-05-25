# Data Schema — Filtrant WP1

> **LuxTalent Advisory Group S.A.** · Work Package 1

---

## 1. Database Schema (PostgreSQL)

### Table: `candidates`

Stores one row per processed CV. The raw structured data is stored as JSONB to preserve flexibility across different CV formats.

```sql
CREATE TABLE candidates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    processed_at    TIMESTAMPTZ DEFAULT NOW(),
    source_filename TEXT NOT NULL,           -- original filename (e.g. "john_doe_cv.pdf")
    source_format   TEXT NOT NULL,           -- "pdf" | "docx" | "txt"
    parse_quality   TEXT NOT NULL,           -- "complete" | "partial" | "poor"
    cv_data         JSONB NOT NULL,          -- structured CV (see CVSchema below)
    recommendation  TEXT NOT NULL,           -- "Invite" | "Reject" | "pending"
    confidence      NUMERIC(4,3),            -- 0.000 to 1.000
    file_hash       TEXT UNIQUE,             -- SHA-256 of raw file bytes (dedup)
    missing_fields  JSONB DEFAULT '[]'       -- list of fields LLM could not extract
);
```

**Indexes:**
```sql
CREATE INDEX idx_candidates_processed_at   ON candidates (processed_at DESC);
CREATE INDEX idx_candidates_recommendation ON candidates (recommendation);
```

### Table: `processing_log`

Audit trail. Every significant event in the lifecycle of a candidate record is logged here.

```sql
CREATE TABLE processing_log (
    id           SERIAL PRIMARY KEY,
    candidate_id UUID REFERENCES candidates(id),
    event        TEXT NOT NULL,    -- "uploaded" | "parse_failed" | "watcher_processed"
    detail       TEXT,             -- free-text description
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 2. CV Structured Schema (CVSchema — Pydantic)

When a CV is parsed by Claude Haiku, the raw text is transformed into this structured JSON object. It is stored in `candidates.cv_data`.

```
CVSchema
├── personal
│   ├── full_name      : str | null
│   ├── email          : str | null
│   ├── phone          : str | null
│   └── address        : str | null
│
├── target_role        : str | null          — job title the candidate is applying for
├── summary            : str | null          — professional summary / objective
│
├── education[]
│   ├── degree         : str | null          — "Bachelor of Science", "Master", etc.
│   ├── field          : str | null          — "Computer Science", "Finance", etc.
│   ├── institution    : str | null
│   ├── year           : int | null          — graduation year
│   └── level_score    : int                 — 1=High school  2=Associate  3=Bachelor
│                                              4=Master  5=PhD
│
├── experience[]
│   ├── title          : str | null          — job title
│   ├── company        : str | null
│   ├── start          : str | null          — "YYYY-MM" format
│   ├── end            : str | null          — "YYYY-MM" or null if current
│   └── duration_months: int | null          — computed from start/end
│
├── skills
│   ├── technical      : str[]               — Python, SQL, React, etc.
│   ├── methods        : str[]               — Agile, Risk assessment, etc.
│   └── management     : str[]               — Team leadership, etc.
│
├── languages[]
│   ├── language       : str                 — "English", "French", etc.
│   ├── level          : str | null          — "C2", "B2", "Native", etc.
│   └── level_score    : int                 — 1=A1  2=A2  3=B1  4=B2  5=C1  6=C2
│
├── certifications[]
│   ├── name           : str
│   └── year           : int | null
│
├── parse_quality      : str                 — "complete" | "partial" | "poor"
└── missing_fields     : str[]               — fields LLM could not extract
```

**Parse quality rules:**
- `complete` — all 6 main sections present (personal, summary, education, experience, skills, languages)
- `partial` — 3–5 sections present
- `poor` — fewer than 3 sections, or extraction failed

---

## 3. ML Feature Schema

Features computed by `services/features.py` from a validated `CVSchema` object. These 19 numbers are the model's actual input.

### Base Features (15)

| Feature | Type | Description | Example |
|---|---|---|---|
| `total_years_experience` | float | Sum of all experience durations in years | 5.5 |
| `num_positions` | int | Number of distinct positions | 3 |
| `avg_tenure_months` | float | Average duration per position | 22.0 |
| `education_level_score` | int | Highest degree: 1=HS · 2=Assoc · 3=Bach · 4=Master · 5=PhD | 4 |
| `total_skills_count` | int | technical + methods + management | 12 |
| `has_certifications` | int | 1 if at least one certification, else 0 | 1 |
| `language_count` | int | Number of languages listed | 2 |
| `section_completeness_score` | int | Sections filled out of 6 | 6 |
| `max_language_score` | int | Best CEFR score (1–6) | 5 |
| `has_senior_title` | int | 1 if any title contains Senior/Lead/Manager/Director/Head/Principal/VP/Chief | 1 |
| `career_gap_months` | float | Total gap between consecutive positions (months) | 4.0 |
| `latest_job_duration` | float | Duration of most recent position (months) | 24.0 |
| `has_summary` | int | 1 if professional summary is present | 1 |
| `num_certifications` | int | Exact number of certifications | 2 |
| `parse_quality_score` | int | 0=poor · 1=partial · 2=complete | 2 |

### Derived Features (4)

Interaction terms that capture relationships between base features.

| Feature | Formula | What it captures |
|---|---|---|
| `experience_education_ratio` | `total_years_experience / max(education_level_score, 1)` | Self-taught practitioner vs. recent graduate |
| `certs_per_year` | `num_certifications / max(total_years_experience, 0.5)` | Intensity of continuous learning |
| `experience_x_seniority` | `total_years_experience × has_senior_title` | Experience amplified by current seniority (0 if not senior) |
| `experience_x_education` | `total_years_experience × education_level_score` | Combined experience + academic level |

---

## 4. API Response Schema

### `POST /api/v1/upload` — Upload response

```json
{
  "id": "uuid",
  "name": "John Doe",
  "target_role": "Software Engineer",
  "recommendation": "Invite",
  "confidence": 0.823,
  "parse_quality": "complete",
  "missing_fields": []
}
```

### `GET /api/v1/candidates` — List response

```json
{
  "total": 42,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "id": "uuid",
      "processed_at": "2026-05-25T14:30:00Z",
      "source_filename": "john_doe_cv.pdf",
      "source_format": "pdf",
      "parse_quality": "complete",
      "recommendation": "Invite",
      "confidence": 0.823,
      "name": "John Doe",
      "email": "john@example.com",
      "target_role": "Software Engineer"
    }
  ]
}
```

### `GET /api/v1/candidates/{id}` — Detail response

Full object including `cv_data` (complete CVSchema JSON) and `missing_fields`.
