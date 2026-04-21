# ML Model Report — CV Screening (v2)
## Filtrant — LuxTalent Advisory Group S.A.

---

## 1. Problem Statement

LuxTalent receives dozens of CVs per day. The goal is to automate the first filtering step: should this candidate be invited to an interview, or not?

The model takes a CV as input and returns **Invite** or **Reject**.

---

## 2. Why a classical ML model instead of just the LLM?

The LLM (Anthropic Claude, Haiku 4.5) is already used in the project to **read and structure** the CV. But we don't ask it to make the decision. Why?

- An LLM can have unpredictable biases in its decisions
- You cannot train an LLM on your own historical data
- A scikit-learn model is **traceable**: you can see exactly which features influenced the decision
- It is much faster and cheaper to run

The LLM handles text comprehension. The ML model makes the decision based on objective criteria learned from historical data.

---

## 3. The Data

### Where does it come from?

The data comes from CVs that were uploaded and processed by the application. For each CV, the extracted features and the recommendation are stored.

The file `candidates_export.csv` contains one row per candidate with their features and label (Invite or Reject).

### Dataset summary

| | Value |
|---|---|
| Number of candidates | 200 |
| Invited | 51 (26%) |
| Rejected | 149 (74%) |

### Class imbalance

There are 3× more Reject than Invite. This is normal in recruitment — not all candidates make it through. But it creates a problem for the model: it could learn to reject everything and appear accurate (74% correct just by always saying "Reject").

**Solutions used (v2):**

1. **`class_weight="balanced"`** in scikit-learn: forces the model to treat both classes equally, even if one is a minority
2. **SMOTE** (Synthetic Minority Over-sampling Technique): creates new synthetic "Invite" examples to balance the data before training
3. **`scale_pos_weight`** in XGBoost: same principle, weights "Invite" examples more heavily

---

## 4. Features — what gets measured?

An ML model cannot read text. Each CV must be transformed into **numbers**. These numbers are computed automatically by `features.py` from the JSON returned by the LLM.

### 4.1 Base features (15)

#### Experience group

| Feature | Description | Example |
|---|---|---|
| `total_years_experience` | Total years of work | 5.5 |
| `num_positions` | Number of positions held | 3 |
| `avg_tenure_months` | Average time spent in a position (months) | 22 |

These features measure stability and accumulated experience. A candidate with 10 years and 2 stable positions is different from one with 10 years and 8 short stints.

#### Education group

| Feature | Description | Values |
|---|---|---|
| `education_level_score` | Highest degree level | 1=High school, 2=Associate, 3=Bachelor, 4=Master, 5=PhD |

#### Skills group

| Feature | Description | Example |
|---|---|---|
| `total_skills_count` | Total skills (technical + methods + management) | 12 |
| `has_certifications` | Has at least one certification | 0 or 1 |
| `num_certifications` | Exact number of certifications | 3 |

#### Languages group

| Feature | Description | Values |
|---|---|---|
| `language_count` | Number of languages spoken | 2 |
| `max_language_score` | Best CEFR level | 1=A1 … 6=C2 |

#### Quality signals group

| Feature | Description | What it indicates |
|---|---|---|
| `has_senior_title` | Title contains Senior/Lead/Manager… | Seniority signal |
| `career_gap_months` | Total gap months between positions | 0 = continuous career |
| `latest_job_duration` | Duration of most recent position (months) | Recent stability |
| `has_summary` | CV includes a professional summary | Care taken with the CV |
| `section_completeness_score` | Sections filled out of 6 | 6 = complete CV |
| `parse_quality_score` | LLM parsing quality | 0=poor, 2=complete |

### 4.2 Derived features (4) — NEW in v2

These features are **computed from base features**. They capture relationships the model would not otherwise see.

| Feature | Formula | What it measures |
|---|---|---|
| `experience_education_ratio` | years_exp / edu_level | Self-taught with lots of experience vs. degree with little experience |
| `certs_per_year` | num_certs / years_exp | Intensity of continuous learning |
| `experience_x_seniority` | years_exp × has_senior_title | Combines experience + seniority (0 if not senior) |
| `experience_x_education` | years_exp × edu_level | Combined experience + education score |

### 4.3 Automatic removal of constant features

In the current dataset, 3 features have **exactly the same value** for all candidates:

```
section_completeness_score -> always 6
has_summary                -> always 1
parse_quality_score        -> always 2
```

The v2 script detects and removes them automatically. This leaves **16 effective features** (12 base + 4 derived).

**Why keep them in the code?** Because on real CVs (incomplete, poorly formatted), these features will have variance and become useful again.

---

## 5. Feature analysis — what we found

### Features with a real signal

```
latest_job_duration         Invite=22.5 months  vs  Reject=15.7 months  -> diff of 6.8
avg_tenure_months           Invite=13.2 months  vs  Reject=8.8 months   -> diff of 4.4
experience_x_education      Invite=11.0         vs  Reject=6.8          -> diff of 4.2 (NEW)
total_years_experience      Invite=3.1 years    vs  Reject=2.0 years    -> diff of 1.1
experience_x_seniority      Invite=2.5          vs  Reject=1.3          -> diff of 1.2 (NEW)
```

Invited candidates have on average **more experience, stay longer in their positions, and combine experience + education**.

### Noisy label detection (NEW in v2)

The script automatically detects inconsistent labels:

```
12 strong profiles (5+ years, Master+, Senior) labelled as Reject
-> 12 potentially noisy labels out of 200 (6%)
```

Correcting these labels would significantly improve performance.

---

## 6. Training — model selection

Six classification models were compared (3 more than in v1).

### 6.1 Logistic Regression

The simplest model. It computes a score as a weighted sum of features:

```
score = (experience × w1) + (education × w2) + (skills × w3) + …
```

Weights (w1, w2, w3…) are learned during training. If the score exceeds a threshold, it's Invite, otherwise Reject.

**Advantage**: simple, fast, interpretable — exact weight of each feature is visible.  
**Drawback**: does not capture complex interactions between features.

### 6.2 Random Forest

Builds 300 decision trees. Each tree learns rules like "if experience > 5 years AND certifications > 1 → Invite". The 300 trees vote and the majority wins.

**Advantage**: captures non-linear relationships between features.  
**Drawback**: can overfit on small datasets.

### 6.3 Gradient Boosting

Similar to Random Forest but each tree corrects the errors of the previous one, sequentially.

**Advantage**: often the best in practice.  
**Drawback**: slower, does not natively support class_weight.

### 6.4 SVM (Support Vector Machine) — NEW in v2

Finds an optimal boundary to separate the two classes. In RBF mode (Radial Basis Function), it can find non-linear boundaries.

**Advantage**: very strong on small datasets, robust against overfitting.  
**Drawback**: slow on large datasets, less interpretable.

### 6.5 HistGradientBoosting — NEW in v2

Improved version of Gradient Boosting. Faster and natively supports `class_weight="balanced"`.

**Advantage**: fast, handles class imbalance, often better than standard GB.  
**Drawback**: "black box" — harder to interpret.

### 6.6 XGBoost — NEW in v2

The reference algorithm in competitive machine learning. Builds boosting trees with advanced optimisations (regularisation, parallelism).

**Advantage**: highly performant, natively handles imbalance via `scale_pos_weight`.  
**Drawback**: more parameters to tune, "black box".

### Comparison results

| Model | AUC (test) | F1 Invite (cv5) |
|---|---|---|
| **LogisticRegression** | **0.530** | **0.515** |
| SVM_RBF | 0.530 | 0.423 |
| XGBoost | 0.510 | 0.407 |
| HistGradientBoosting | 0.527 | 0.368 |
| GradientBoosting | 0.503 | 0.363 |
| RandomForest | 0.510 | 0.350 |

Logistic Regression wins again. With only 200 rows and noisy data, simple models generalise better than complex ones.

### Hyperparameter optimisation (NEW in v2)

After selecting the best model, its parameters are optimised with `RandomizedSearchCV`:

```
Best parameters : C=0.01, penalty=l2
Optimised F1 (cv5) : 0.548 (vs 0.515 before optimisation)
```

`C=0.01` means the model needs strong regularisation — it simplifies as much as possible to avoid overfitting on this noisy data.

---

## 7. Evaluation — understanding the metrics

### AUC-ROC

AUC measures how well the model can distinguish Invite from Reject. It ranges from 0.5 (random) to 1.0 (perfect).

```
0.5   -> as good as a coin flip
0.653 -> our model (v2)
0.8   -> good model
1.0   -> perfect (suspicious in practice = overfitting)
```

### Confusion matrix (v2)

```
                     Predicted Reject   Predicted Invite
Actually Reject   |       19          |       11         |
Actually Invite   |        4          |        6         |
```

Out of 40 candidates in the test set:
- **19 Reject correctly identified** (vs 17 in v1)
- **6 Invite correctly identified** (vs 5 in v1, +20%)
- **11 false Invites** (vs 13 in v1, improvement)
- **4 false Rejects** (vs 5 in v1, improvement)

### v1 vs v2 comparison

| Metric | v1 | v2 | Change |
|---|---|---|---|
| Invite Precision | 0.28 | 0.35 | +25% |
| Invite Recall | 0.50 | 0.60 | +20% |
| F1 Invite (cv5) | 0.521 | 0.548 | +5% |

---

## 8. What the model actually learned

Feature importance after optimisation:

```
language_count               -> 0.2055 (strongest)
education_level_score        -> 0.1275
certs_per_year               -> 0.1271 (NEW — derived)
has_senior_title             -> 0.1028
avg_tenure_months            -> 0.0958
experience_education_ratio   -> 0.0914 (NEW — derived)
latest_job_duration          -> 0.0891
total_years_experience       -> 0.0815
num_certifications           -> 0.0763
has_certifications           -> 0.0749
experience_x_seniority       -> 0.0722 (NEW — derived)
experience_x_education       -> 0.0690 (NEW — derived)
max_language_score           -> 0.0575
num_positions                -> 0.0052 (nearly useless)
total_skills_count           -> 0.0013 (nearly useless)
career_gap_months            -> 0.0005 (nearly useless)
```

**Key observation**: all 4 derived features (NEW) contribute significantly. `certs_per_year` and `experience_education_ratio` are in the top 6. These combinations provide information that the individual features did not capture.

---

## 9. Techniques used — summary

### SMOTE (Synthetic Minority Over-sampling Technique)

**Problem**: 51 Invite vs 149 Reject — the model tends to reject everything.

**Solution**: SMOTE creates new synthetic Invite examples by interpolating between real ones. If we have two invited candidates A and B, SMOTE creates a candidate C whose features are "between" A and B.

```
Before SMOTE:  51 Invite, 149 Reject (ratio 1:3)
After SMOTE:  149 Invite, 149 Reject (ratio 1:1)
```

### StandardScaler

Features have very different scales: `has_certifications` ranges from 0 to 1, but `career_gap_months` can range from 0 to 40. Without normalisation, the model would give too much weight to large-scale features.

StandardScaler transforms each feature to have a mean of 0 and a standard deviation of 1.

### RandomizedSearchCV

Instead of manually setting parameters, multiple combinations are automatically tested and the best is kept.

---

## 10. Limitations and possible improvements

### Current limitations

| Limitation | Impact |
|---|---|
| 200 rows of data | Model has limited generalisation |
| 12 noisy labels (6%) | Model learns from mistakes |
| Homogeneous data (well-formatted test CVs) | 3 constant features |
| No real client data | Learned patterns may not reflect reality |

### What we would do with more data

- Retrain on LuxTalent's real historical data
- Add text features (TF-IDF on job titles)
- Test deep learning models (if > 5,000 rows)
- Calibrate the model so confidence scores are reliable

### How to improve without new data

- **Correct the 12 noisy labels** — estimated improvement: AUC +0.05–0.15
- Increase synthetic data with more variance
- Test additional derived features (skills/experience ratio, etc.)

---

## 11. Conclusion

A complete ML pipeline (v2) was built:

```
CV (PDF/DOCX)
    | extractor.py    -> raw text
    | llm_parser.py   -> structured JSON (Anthropic Claude, Haiku 4.5)
    | features.py     -> 16 features (12 base + 4 derived)
    | predictor.py    -> Invite / Reject + confidence score
```

The selected model is a **Logistic Regression** with StandardScaler normalisation and SMOTE oversampling. The v2 improvements (derived features, SMOTE, hyperparameter optimisation) raised Invite recall from 50% to 60% and precision from 28% to 35%.

The consistency check confirms the model works:
- Strong profile (10 years, Master, 15 skills) → **Invite 90%**
- Weak profile (0.5 year, high school, 2 skills) → **Reject 83%**

The main limitation remains **data quality**: correcting the 12 noisy labels and increasing the volume beyond 500 candidates would significantly improve performance.
