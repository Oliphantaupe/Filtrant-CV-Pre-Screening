# Data Flow — Filtrant WP1

> **LuxTalent Advisory Group S.A.** · Work Package 1

---

## 1. Main Processing Flow (HTTP Upload)

When an HR user uploads a CV through the web interface, the following sequence executes:

```
HR User                Frontend              Backend               External
   │                      │                     │                      │
   │── Drop CV file ──────►│                     │                      │
   │                      │── POST /upload ─────►│                      │
   │                      │                     │                      │
   │                      │              [1] Extract text               │
   │                      │              pdfplumber / python-docx       │
   │                      │              → raw_text (str)               │
   │                      │                     │                      │
   │                      │              [2] Compute file hash          │
   │                      │              SHA-256(file_bytes)            │
   │                      │              → Check duplicate in DB        │
   │                      │                     │── SELECT file_hash ──►│ PostgreSQL
   │                      │                     │◄── exists? ───────────│
   │                      │                     │                      │
   │                      │              [3] Parse with LLM             │
   │                      │                     │── messages[] ────────►│ Anthropic
   │                      │                     │   system: CV schema   │ Claude
   │                      │                     │   user: raw_text      │ Haiku 4.5
   │                      │                     │◄── CVSchema JSON ─────│
   │                      │                     │                      │
   │                      │              [4] Validate schema            │
   │                      │              Pydantic CVSchema(...)         │
   │                      │              → structured CV object         │
   │                      │                     │                      │
   │                      │              [5] Extract features           │
   │                      │              features.py                    │
   │                      │              → 19 numerical features        │
   │                      │                     │                      │
   │                      │              [6] ML prediction              │
   │                      │              predictor.py                   │
   │                      │              model.predict_proba(features)  │
   │                      │              → "Invite" | "Reject"          │
   │                      │              → confidence score             │
   │                      │                     │                      │
   │                      │              [7] Store in DB                │
   │                      │                     │── INSERT candidate ──►│ PostgreSQL
   │                      │                     │── INSERT log ────────►│
   │                      │                     │                      │
   │                      │◄── 201 + result ────│                      │
   │◄── Show badge ────────│                     │                      │
   │    Invite 82%         │                     │                      │
```

**Error handling at each step:**
- Step 1: `400` if format unsupported, `413` if file > 5 MB
- Step 2: `409 Conflict` if duplicate (same SHA-256 hash already in DB)
- Step 3: `502` if Anthropic API call fails
- Step 4: Validation errors → logged as `parse_failed`, stored with quality=`poor`
- Steps 5–7: Any failure → `500` with detail

---

## 2. Automated File Watcher Flow

When a CV file is dropped into `data/incoming_cvs/` (without using the UI):

```
File System                  watcher.py (background task)         Backend
     │                              │                                │
     │── New file detected ─────────►│                               │
     │   (poll every 10s)           │                               │
     │                              │── Read file bytes             │
     │                              │── Call _process_cv_bytes()   │
     │                              │   (same pipeline as upload)  │
     │                              │                               │
     │                    ┌─────────┴──────────┐                   │
     │                    │   Success           │   Failure         │
     │                    │                     │                   │
     │                    │── Move to ──────────│── Move to         │
     │                    │   processed_cvs/    │   failed_cvs/     │
     │                    └─────────────────────┘                   │
     │                              │── Log event ─────────────────►│ processing_log
```

The watcher runs as an `asyncio` background task started at application startup (`lifespan` in `main.py`). It polls the folder every `WATCHER_INTERVAL` seconds (default: 10).

---

## 3. Dashboard Read Flow

When an HR user views the candidates list:

```
HR User          Frontend (React)              Backend              PostgreSQL
   │                   │                          │                      │
   │── Open page ──────►│                          │                      │
   │                   │── GET /candidates ────────►│                      │
   │                   │   ?page=1&page_size=20    │── SELECT + COUNT ────►│
   │                   │   ?recommendation=Invite  │   WHERE filters      │
   │                   │   ?search=john            │   ORDER BY date DESC │
   │                   │                          │◄── rows + total ──────│
   │                   │◄── { total, items[] } ────│                      │
   │◄── Render list ───│                          │                      │
   │                   │                          │                      │
   │── Click candidate ►│                          │                      │
   │                   │── GET /candidates/{id} ───►│                      │
   │                   │                          │── SELECT * WHERE id ─►│
   │                   │                          │◄── full row ──────────│
   │                   │◄── candidate detail ──────│                      │
   │◄── Detail modal ──│                          │                      │
```

---

## 4. ML Training Flow (offline, not part of the runtime)

The model is trained separately from the application, before deployment:

```
training_dataset.csv (500 labelled CVs)
         │
         ▼
    train.py
         │
    [1] Load CSV + compute derived features
         │
    [2] Detect and remove constant features
         │
    [3] Split train (80%) / test (20%) — stratified
         │
    [4] Apply SMOTE on training set (balance Invite/Reject)
         │
    [5] Compare 6 models via StratifiedKFold(5) cross-validation
         │     LogisticRegression · RandomForest · GradientBoosting
         │     SVM_RBF · HistGradientBoosting · XGBoost
         │
    [6] Select best model by mean F1 (cv5)
         │
    [7] Hyperparameter search (RandomizedSearchCV, 20 iterations)
         │
    [8] Retrain best model on full dataset (train + test)
         │
    [9] Save artifact → ml/model.joblib
         │     { pipeline, effective_features, model_name,
         │       best_auc, best_f1_cv, n_training_samples }
         │
    [10] Sanity check
          Strong profile (10 yrs, Master, 15 skills) → Invite ✓
          Weak profile   (0.5 yr, HS, 2 skills)      → Reject ✓
```

At application startup, `predictor.py` loads `model.joblib` once into memory. All subsequent predictions use the in-memory model — no disk I/O per request.

---

## 5. Data Lifecycle

```
CV File (PDF/DOCX/TXT)
      │
      │ [upload or watcher]
      ▼
Raw text extraction
      │
      │ [llm_parser.py → Anthropic Claude]
      ▼
CVSchema (structured JSON)
      │ stored in candidates.cv_data (JSONB)
      │
      │ [features.py]
      ▼
19 numerical features (float array)
      │ never stored — computed on-the-fly
      │
      │ [predictor.py → model.joblib]
      ▼
Recommendation + Confidence
      │ stored in candidates.recommendation / confidence
      │
      │ [REST API]
      ▼
HR Dashboard (read-only)
```

**Key design choice:** the raw text is never stored. Only the structured JSON (`cv_data`) and the numerical features (implicit in the ML output) are persisted. This minimises storage of sensitive personal data in compliance with GDPR data minimisation (Art. 5).
