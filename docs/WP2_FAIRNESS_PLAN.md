# WP2 — Fairness Implementation Plan
## Filtrant CV Pre-Screening — v2 Roadmap

Derived from the Gemini deep-research report on algorithmic fairness in ML-based recruitment and mapped to the actual codebase constraints (498 labelled CVs — 204 Invite / 294 Reject, scikit-learn tabular pipeline, FastAPI + React stack).

---

## Context & Key Constraints

| Constraint | Impact on choices |
|---|---|
| 498 labelled CVs | Rules out adversarial debiasing and SMOTE; favours re-weighting and bootstrap CI |
| No explicit protected attributes in training data | Requires proxy inference for audit only — never for prediction |
| EU AI Act enforcement: Aug 2026 | High-risk classification — human override, transparency, and bias testing are mandatory |
| GDPR Art. 22 | Post-processing threshold adjustments per group carry legal risk in prod — use with care |
| scikit-learn pipeline | Fairlearn integrates natively; AIF360 requires BinaryLabelDataset wrapper |

---

## Phase 0 — Proxy Attribute Inference (Audit Only)

**Goal:** Reconstruct inferred demographic labels from existing CV data so fairness metrics can be calculated. These labels are **never fed to any model**.

### 0.1 Gender Inference
- Source: `full_name` field already stored in the DB (cv_data JSON).
- Tool: `gender-guesser` (open-source, no API key).
- Output: binary label `M / F / unknown`; drop `unknown` rows from gender-specific metric calculations.
- Limitation: weak on non-Western names — document the coverage gap.

### 0.2 Age Proxy
- Source: earliest graduation year or first job start year from the parsed CV JSON.
- Formula: `inferred_age = current_year − graduation_year + 22`
- Cohorts: `< 35`, `35–50`, `> 50` (aligned with AARP research thresholds).

### 0.3 Nationality / Origin Proxy
- Source: `language_count` + languages listed + address postal code (if present).
- Method: flag candidates with `language_count ≥ 2` and a non-native language as "multilingual / likely immigrant background" vs "monolingual".
- Note: coarse proxy only — document limitations clearly.

**Deliverable:** `backend/ml/fairness_audit/infer_proxies.py` — outputs a DataFrame with columns `[candidate_id, gender_proxy, age_cohort, multilingual_flag]`.

---

## Phase 1 — Proxy Bias Detection

**Goal:** Prove (or disprove) that the job-related features carry demographic information before assessing model outputs.

### 1.1 Mutual Information Analysis
- Compute `sklearn.feature_selection.mutual_info_classif` between each feature (`years_experience`, `education_score`, `skill_match`, `language_count`, `seniority_score`, `completeness`) and each inferred attribute.
- Flag any feature with MI score > 0.05 as a confirmed proxy carrier.
- Expected findings per Gemini research:
  - `years_experience` → age proxy (strong linear correlation)
  - `language_count` → multilingual/origin proxy
  - `education_score` → possible gender proxy (degree institution bias)

### 1.2 Adversarial Proxy Model
- Train a Random Forest to predict each inferred protected attribute using only the job-related features.
- If ROC AUC > 0.65 for any attribute → confirmed proxy bias in the feature set.
- Script: `backend/ml/fairness_audit/proxy_detection.py`

**Deliverable:** `docs/fairness_audit_report.md` — MI scores table + adversarial AUC per attribute.

---

## Phase 2 — Fairness Audit

**Goal:** Measure disparate impact of the current (WP1) model across inferred demographic groups.

### 2.1 Metric Selection Rationale

| Metric | Why it applies here |
|---|---|
| **Equal Opportunity** (primary) | Our main harm is a False Negative — missing a qualified candidate from a minority group. Focus on equalising TPR. |
| **Demographic Parity** (secondary) | Historical labels may be biased; check raw selection rate differences as a sanity signal. |
| **Calibration by Group** | The UI exposes confidence scores — a 0.85 must mean the same thing regardless of candidate background. |

Equalized Odds is logged but not enforced: with biased historical labels, forcing equal FPR could entrench the original discrimination.

### 2.2 Implementation with Fairlearn MetricFrame

```python
from fairlearn.metrics import MetricFrame, selection_rate, true_positive_rate
import pandas as pd

mf = MetricFrame(
    metrics={
        "selection_rate": selection_rate,
        "tpr": true_positive_rate,
    },
    y_true=y_test,
    y_pred=y_pred,
    sensitive_features=sensitive_df[["gender_proxy", "age_cohort"]],
)
print(mf.by_group)
print("Equal Opportunity Difference:", mf.difference(method="between_groups")["tpr"])
```

### 2.3 Statistical Robustness for Small Sample (≈200 CVs)

Small subgroups have high variance — a raw disparity could be noise.

- Use **BCa bootstrap confidence intervals** (10 000 iterations) on the Equal Opportunity Difference.
- If 95% CI includes 0 → disparity not statistically significant.
- If 95% CI strictly above 0.05 → trigger mitigation.
- Script: `backend/ml/fairness_audit/bootstrap_ci.py`

**Deliverable:** Fairness audit notebook `backend/ml/fairness_audit.ipynb` with MetricFrame visualisations and bootstrap CIs.

---

## Phase 3 — Mitigation

Techniques are ordered by suitability for a 498-sample tabular dataset.

### 3.1 Pre-Processing: Sample Re-Weighting (Primary Strategy)

Maintains full dataset size (no information loss from resampling). Assigns higher loss weight to unprivileged-group positives.

- Tool: **AIF360 `Reweighing`**
- Implementation:

```python
from aif360.algorithms.preprocessing import Reweighing
from aif360.datasets import BinaryLabelDataset

reweigher = Reweighing(
    unprivileged_groups=[{"gender_proxy": 0}],  # female
    privileged_groups=[{"gender_proxy": 1}],    # male
)
reweighed = reweigher.fit_transform(train_dataset_aif360)
sample_weights = reweighed.instance_weights

model.fit(X_train, y_train, sample_weight=sample_weights)
```

Apply separately per sensitive attribute or use a combined weight if multiple groups are targeted.

### 3.2 In-Processing: ExponentiatedGradient (Secondary Strategy)

Wraps any scikit-learn estimator and enforces a fairness constraint during training.

- Tool: **Fairlearn `ExponentiatedGradient`**
- Constraint: `EqualizedOdds` or `TruePositiveRateParity` depending on audit findings.

```python
from fairlearn.reductions import ExponentiatedGradient, TruePositiveRateParity
from sklearn.ensemble import RandomForestClassifier

mitigator = ExponentiatedGradient(
    estimator=RandomForestClassifier(n_estimators=100),
    constraints=TruePositiveRateParity(),
)
mitigator.fit(X_train, y_train, sensitive_features=sf_train)
```

### 3.3 What NOT to Use

| Technique | Why excluded |
|---|---|
| Adversarial Debiasing | Requires large data; catastrophic overfitting risk at 200 samples |
| SMOTE on protected groups | Artificially inflates noise; destabilises small datasets |
| Post-processing threshold per group | Legal risk under GDPR Art. 22 in a live prod system — requires explicit legal sign-off |
| Themis-ML | Deprecated; Python 2.7 / sklearn 0.19 only |

### 3.4 Model Comparison

After mitigation, compare WP1 baseline vs WP2 mitigated model:
- Overall accuracy, F1, ROC AUC
- Equal Opportunity Difference (per attribute)
- Demographic Parity Difference (per attribute)
- BCa CI for all fairness metrics

**Deliverable:** `backend/ml/train_fair.py` — new training script producing `model_v2_fair.pkl`.

---

## Phase 4 — Explainability

**Goal:** Every screening decision must be explainable to the HR consultant (AI Act Art. 86, GDPR Art. 22).

### 4.1 SHAP for Local Explanations

- Tool: `shap` with `TreeExplainer` for Random Forest / XGBoost, `LinearExplainer` for Logistic Regression.
- Compute per-candidate SHAP values at inference time in `predictor.py`.
- Return top-3 positive and top-3 negative contributing features alongside the score.

```python
import shap
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_candidate)
top_features = sorted(zip(feature_names, shap_values[1]), key=lambda x: abs(x[1]), reverse=True)[:6]
```

### 4.2 Backend API Change

Add `explanation` field to the prediction response:

```json
{
  "recommendation": "invite",
  "confidence": 0.82,
  "explanation": {
    "positive": [
      {"feature": "years_experience", "contribution": +0.18},
      {"feature": "skill_match", "contribution": +0.12}
    ],
    "negative": [
      {"feature": "completeness", "contribution": -0.06}
    ]
  }
}
```

**Deliverable:** Updated `backend/src/services/predictor.py` + updated API response schema.

---

## Phase 5 — UI Updates (v2)

### 5.1 Explanation Panel on Candidate Detail
- Show top contributing features as a horizontal bar chart (positive = green, negative = red).
- Label each bar with plain-language text: `"5 years of experience"` not `"years_experience = 5"`.

### 5.2 Fairness Dashboard (HR Admin View)
- New tab or section in the dashboard showing:
  - Overall selection rate by inferred gender cohort
  - TPR by age cohort
  - A plain warning banner if Equal Opportunity Difference > 0.10
- Data sourced from a new `/api/fairness-metrics` endpoint computed at batch level.

### 5.3 Mandatory Human Override UI
- Requirement from AI Act Art. 14: human must be able to meaningfully override.
- Add an explicit `Override` button on each candidate card that logs the HR consultant's decision separately from the model recommendation.
- Audit log: `model_recommendation`, `human_decision`, `override_reason`, `timestamp`.

---

## Phase 6 — Legal & Compliance Checklist

| Requirement | Source | Status |
|---|---|---|
| Bias testing documented before deployment | AI Act Art. 10 | To do (Phase 1–2) |
| Human override possible and logged | AI Act Art. 14 | To do (Phase 5.3) |
| Candidates notified that AI processes their CV | AI Act Art. 26 & 86 | To do (UI copy) |
| Candidates can request explanation of rejection | AI Act Art. 86 | To do (Phase 4–5) |
| No solely automated decision binding | GDPR Art. 22 | To do (Phase 5.3) |
| Threshold post-processing reviewed by legal | GDPR Art. 22 | Deferred / out of scope v2 |
| Protected attributes not stored for prediction | GDPR data minimisation | Done (WP1) |

---

## Deliverables Summary

| # | Deliverable | Location |
|---|---|---|
| 1 | Proxy inference script | `backend/ml/fairness_audit/infer_proxies.py` |
| 2 | Proxy bias detection script | `backend/ml/fairness_audit/proxy_detection.py` |
| 3 | Bootstrap CI script | `backend/ml/fairness_audit/bootstrap_ci.py` |
| 4 | Fairness audit notebook | `backend/ml/fairness_audit.ipynb` |
| 5 | Mitigated training script | `backend/ml/train_fair.py` |
| 6 | Updated predictor with SHAP | `backend/src/services/predictor.py` |
| 7 | Fairness metrics API endpoint | `backend/src/routers/fairness.py` |
| 8 | Explanation + fairness UI | `frontend/src/` (detail panel + dashboard tab) |
| 9 | Audit report doc | `docs/fairness_audit_report.md` |
| 10 | Expert lecture reflection | `docs/expert_lecture_reflection.md` |

---

## Recommended Build Order

1. Phase 0 — infer proxies (fast, no model changes)
2. Phase 1 — proxy detection (confirms which features to watch)
3. Phase 2 — audit current model (establishes baseline metrics)
4. Phase 3 — retrain with re-weighting, compare (core mitigation)
5. Phase 4 — add SHAP to predictor
6. Phase 5 — UI explainability panel + fairness dashboard
7. Phase 5.3 — human override logging
8. Phase 6 — compliance checklist sign-off
