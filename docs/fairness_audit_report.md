# Fairness Audit — Proxy Bias Detection Report

Dataset: 500 candidates | Invite: 100 | Reject: 400

---

## 1. Mutual Information Analysis

MI > 0.05 indicates a feature carries significant demographic signal.

### gender

**Flagged (MI > 0.05):**
- `num_certifications`: MI = 0.0550 ⚠️

**Below threshold:**
- `max_language_score`: MI = 0.0325
- `experience_x_seniority`: MI = 0.0266
- `total_years_experience`: MI = 0.0242
- `total_skills_count`: MI = 0.0120
- `avg_tenure_months`: MI = 0.0117

### age_cohort

**Flagged (MI > 0.05):**
- `total_years_experience`: MI = 0.4716 ⚠️
- `experience_education_ratio`: MI = 0.4526 ⚠️
- `experience_x_education`: MI = 0.4446 ⚠️
- `experience_x_seniority`: MI = 0.3525 ⚠️
- `has_senior_title`: MI = 0.3107 ⚠️
- `certs_per_year`: MI = 0.2265 ⚠️
- `num_positions`: MI = 0.2009 ⚠️
- `avg_tenure_months`: MI = 0.1953 ⚠️
- `career_gap_months`: MI = 0.1689 ⚠️
- `latest_job_duration`: MI = 0.1093 ⚠️

**Below threshold:**
- `section_completeness_score`: MI = 0.0404
- `num_certifications`: MI = 0.0374
- `parse_quality_score`: MI = 0.0311
- `education_level_score`: MI = 0.0294
- `max_language_score`: MI = 0.0277

### is_multilingual

**Flagged (MI > 0.05):**
- `language_count`: MI = 0.3758 ⚠️

**Below threshold:**
- `max_language_score`: MI = 0.0328
- `education_level_score`: MI = 0.0187
- `experience_x_seniority`: MI = 0.0172
- `latest_job_duration`: MI = 0.0138
- `has_senior_title`: MI = 0.0096

---

## 2. Adversarial Probe

A Random Forest is trained on ML features only to predict each protected attribute. AUC > 0.65 = exploitable proxy bias.

- **gender**: AUC = 0.493 ± 0.021  ✅ OK
- **age_cohort**: AUC = 0.802 ± 0.019  ⚠️  PROXY BIAS CONFIRMED
- **is_multilingual**: AUC = 1.000 ± 0.000  ⚠️  PROXY BIAS CONFIRMED

---

## 3. Interpretation

At least one sensitive attribute is predictable from the ML feature set. This means the model can reconstruct demographic information even without explicit protected attributes — **mitigation is required** (see train_fair.py).

**Key proxy features to monitor:**
- gender: `num_certifications` (0.055), `max_language_score` (0.032), `experience_x_seniority` (0.027)
- age_cohort: `total_years_experience` (0.472), `experience_education_ratio` (0.453), `experience_x_education` (0.445)
- is_multilingual: `language_count` (0.376), `max_language_score` (0.033), `education_level_score` (0.019)