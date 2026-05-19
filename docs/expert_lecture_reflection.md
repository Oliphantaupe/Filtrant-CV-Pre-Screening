# Expert Lecture Reflection — Algorithmic Fairness in Recruitment

> **Instructions:** Fill in each section based on the expert lecture(s) or external sources you consulted during WP2. This document is a required deliverable for EU AI Act Art. 10 compliance — it evidences that the fairness mitigation choices were informed by domain expertise, not made arbitrarily.

---

## Lecture / Source

- **Speaker / Author:**
- **Title / Event:**
- **Date:**
- **Format:** (conference talk / guest lecture / paper / podcast / ...)
- **Link / Reference:**

---

## Key Takeaways

_What were the 3–5 most important points from this lecture that are relevant to algorithmic fairness in hiring?_

1.
2.
3.
4.
5.

---

## How It Shaped WP2 Decisions

_For each key WP2 design choice, explain whether/how the lecture influenced it._

| WP2 Decision | Without lecture | After lecture | Rationale |
|---|---|---|---|
| Choice of Equal Opportunity as primary metric | | | |
| Sample re-weighting (AIF360) over adversarial debiasing | | | |
| Not using post-processing threshold per group (GDPR Art. 22) | | | |
| Using BCa bootstrap CI for small-sample significance testing | | | |
| Keeping SHAP explanations in the backend (AI Act Art. 86) | | | |

---

## Proxy Inference Method

_The lecture recommended / we chose to infer demographic proxies using:_

- **Gender:** Explicit `Gender:` field in CV header (not name-based inference). Coverage: N/A for rows where field is absent (flagged as "other").
- **Age:** Derived from `Date of Birth` → age cohort buckets (22–28, 29–32, 33–36, 37–44). Aligned with AARP research thresholds.
- **Multilingual background:** `language_count ≥ 2` flag. Coarse proxy for immigrant/diverse background.

_How does this align (or not align) with the lecture's recommended approach?_

> _Your answer here._

---

## Limitations and Open Questions

_What did the lecture highlight as limitations that still apply to our implementation?_

1.
2.
3.

_What questions remain unresolved after WP2?_

- [ ]
- [ ]
- [ ]

---

## Compliance Mapping

| AI Act / GDPR Requirement | How WP2 addresses it | Evidence |
|---|---|---|
| Art. 10 — Bias testing before deployment | Proxy detection + bootstrap CI run and documented | `docs/fairness_audit_report.md` |
| Art. 14 — Human override possible and logged | Override UI + processing_log audit trail | `export.py`, `CandidatesPage.tsx` |
| Art. 26 & 86 — Candidates notified / can request explanation | _To do — add UI copy_ | |
| Art. 22 GDPR — No solely automated binding decision | HR override required before action | Override flow enforced in UI |
| GDPR data minimisation — Protected attrs not used for prediction | Proxy columns excluded from FEATURE_COLUMNS | `train_fair.py`, `predictor.py` |
