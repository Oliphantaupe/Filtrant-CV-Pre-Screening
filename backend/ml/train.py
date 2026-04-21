"""
ML model training script for CV screening — Filtrant (v2)
==========================================================
Improvements vs v1:
  - Automatic removal of constant features (zero variance)
  - Derived features (interactions, ratios)
  - SMOTE for oversampling the minority class
  - More models: SVM, XGBoost, HistGradientBoosting
  - Hyperparameter search via RandomizedSearchCV
  - Best model selected by mean F1 in cross-validation
  - Detection of potentially noisy labels

Usage (inside Docker):
    docker compose exec backend python /app/ml/train.py
"""

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import warnings
from sklearn.ensemble import (
    GradientBoostingClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
from sklearn.model_selection import (
    RandomizedSearchCV,
    StratifiedKFold,
    cross_val_score,
    train_test_split,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

# SMOTE for oversampling
try:
    from imblearn.over_sampling import SMOTE
    from imblearn.pipeline import Pipeline as ImbPipeline

    HAS_IMBLEARN = True
except ImportError:
    HAS_IMBLEARN = False
    ImbPipeline = Pipeline  # fallback

# XGBoost
try:
    from xgboost import XGBClassifier

    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

warnings.filterwarnings("ignore")

# ─── Paths ────────────────────────────────────────────────────────────────────
HERE = Path(__file__).parent
DATA_PATH = HERE / "candidates_export.csv"
MODEL_PATH = HERE / "model.joblib"

# ─── Features — same order as features.py ────────────────────────────────────
#
# Each feature is a number extracted from the parsed CV.
# The model does not read text — it only sees these numbers.
#
FEATURE_COLUMNS = [
    # ── Experience ────────────────────────────────────────────────────────────
    "total_years_experience",     # Total years of experience (e.g. 5.5)
    "num_positions",              # Number of distinct positions (e.g. 3)
    "avg_tenure_months",          # Average tenure per position in months (e.g. 22.0)
    # ── Education ─────────────────────────────────────────────────────────────
    "education_level_score",      # Degree level: 1=high school 2=associate 3=bachelor 4=master 5=PhD
    # ── Skills ────────────────────────────────────────────────────────────────
    "total_skills_count",         # Total skill count (technical + methods + management)
    "has_certifications",         # Has at least one certification (0 or 1)
    # ── Languages ─────────────────────────────────────────────────────────────
    "language_count",             # Number of languages spoken
    # ── CV completeness ───────────────────────────────────────────────────────
    "section_completeness_score", # Sections filled out of 6 (name, summary, education, experience, skills, languages)
    "max_language_score",         # Best CEFR level: 1=A1 2=A2 3=B1 4=B2 5=C1 6=C2
    # ── Seniority signals ─────────────────────────────────────────────────────
    "has_senior_title",           # Title contains Senior/Lead/Manager/Director... (0 or 1)
    "career_gap_months",          # Total career gap in months
    "latest_job_duration",        # Duration of most recent position in months
    # ── CV quality ────────────────────────────────────────────────────────────
    "has_summary",                # CV contains a professional summary (0 or 1)
    "num_certifications",         # Number of certifications (not just 0/1)
    "parse_quality_score",        # Parsing quality: 0=poor 1=partial 2=complete
]

# ── Derived features (computed from base features) ───────────────────────────
DERIVED_FEATURE_NAMES = [
    "experience_education_ratio",  # total_years / education_level_score
    "certs_per_year",              # num_certifications / max(total_years, 0.5)
    "experience_x_seniority",      # total_years * has_senior_title
    "experience_x_education",      # total_years * education_level_score
]


def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """Adds derived features to the DataFrame (in-place + return)."""
    df["experience_education_ratio"] = df["total_years_experience"] / df["education_level_score"].clip(lower=1)
    df["certs_per_year"] = df["num_certifications"] / df["total_years_experience"].clip(lower=0.5)
    df["experience_x_seniority"] = df["total_years_experience"] * df["has_senior_title"]
    df["experience_x_education"] = df["total_years_experience"] * df["education_level_score"]
    return df


def remove_constant_features(df: pd.DataFrame, feature_cols: list[str]) -> list[str]:
    """Removes zero-variance features and returns the filtered list."""
    constant = [col for col in feature_cols if df[col].nunique() <= 1]
    if constant:
        print(f"\n  [!] Constant features removed (variance=0): {constant}")
    return [col for col in feature_cols if col not in constant]


def detect_noisy_labels(df: pd.DataFrame) -> None:
    """Detects potentially inconsistent labels."""
    print("\n--- Noisy label detection ---")

    # Strong profiles labelled Reject
    strong_reject = df[
        (df["recommendation"] == "Reject")
        & (df["total_years_experience"] >= 5)
        & (df["education_level_score"] >= 4)
        & (df["has_senior_title"] == 1)
    ]

    # Weak profiles labelled Invite
    weak_invite = df[
        (df["recommendation"] == "Invite")
        & (df["total_years_experience"] == 0)
        & (df["has_certifications"] == 0)
        & (df["has_senior_title"] == 0)
    ]

    n_strong_reject = len(strong_reject)
    n_weak_invite = len(weak_invite)

    if n_strong_reject > 0:
        print(f"  [!] {n_strong_reject} strong profiles (5+ years, Master+, Senior) labelled Reject")
    if n_weak_invite > 0:
        print(f"  [!] {n_weak_invite} weak profiles (0 exp, 0 certs, not Senior) labelled Invite")
    if n_strong_reject == 0 and n_weak_invite == 0:
        print("  [OK] No obvious inconsistencies detected.")

    total_noisy = n_strong_reject + n_weak_invite
    if total_noisy > 0:
        print(f"  -> {total_noisy} potentially noisy labels out of {len(df)} ({total_noisy/len(df)*100:.0f}%)")
        print("  -> Tip: review these labels manually to improve model quality.")


def build_pipeline(name: str, clf, use_smote: bool = True) -> Pipeline:
    """Builds a pipeline: [optional SMOTE] -> StandardScaler -> Classifier."""
    steps = []
    if use_smote and HAS_IMBLEARN:
        steps.append(("smote", SMOTE(random_state=42, k_neighbors=3)))
    steps.append(("scaler", StandardScaler()))
    steps.append(("clf", clf))

    if use_smote and HAS_IMBLEARN:
        return ImbPipeline(steps)
    return Pipeline(steps)


def main():
    print("\n" + "=" * 60)
    print("  FILTRANT — CV Screening ML Model Training (v2)")
    print("=" * 60)

    if HAS_IMBLEARN:
        print("  [OK] imbalanced-learn available — SMOTE enabled")
    else:
        print("  [X] imbalanced-learn not available — SMOTE disabled")

    if HAS_XGBOOST:
        print("  [OK] xgboost available")
    else:
        print("  [X] xgboost not available")

    # ─── 1. Load data ─────────────────────────────────────────────────────────
    if not DATA_PATH.exists():
        print(f"\nERROR: file not found -> {DATA_PATH}")
        print("Run first: curl http://localhost:8000/api/v1/candidates/export.csv -o /app/ml/candidates_export.csv")
        sys.exit(1)

    df = pd.read_csv(DATA_PATH)
    df = df[df["recommendation"].isin(["Invite", "Reject"])].copy()
    df[FEATURE_COLUMNS] = df[FEATURE_COLUMNS].fillna(0)

    n_total  = len(df)
    n_invite = (df["recommendation"] == "Invite").sum()
    n_reject = (df["recommendation"] == "Reject").sum()

    print(f"\nDataset loaded: {n_total} candidates")
    print(f"  Invite: {n_invite} ({n_invite / n_total * 100:.0f}%)")
    print(f"  Reject: {n_reject} ({n_reject / n_total * 100:.0f}%)")

    if n_total < 50:
        print("\nWARNING: fewer than 50 rows — results will not be reliable.")

    # ─── 2. Feature engineering ───────────────────────────────────────────────
    add_derived_features(df)

    all_features = FEATURE_COLUMNS + DERIVED_FEATURE_NAMES
    df[all_features] = df[all_features].fillna(0)

    # Remove constant features
    effective_features = remove_constant_features(df, all_features)

    # ─── 3. Feature analysis ──────────────────────────────────────────────────
    print("\n--- Discriminant power of each feature ---")
    print("    (mean difference: Invite vs Reject)")
    print()

    means    = df.groupby("recommendation")[effective_features].mean()
    invite_m = means.loc["Invite"]
    reject_m = means.loc["Reject"]
    diff = (invite_m - reject_m).abs().sort_values(ascending=False)

    for feat, d in diff.items():
        inv_val = invite_m[feat]
        rej_val = reject_m[feat]
        bar     = "#" * min(int(d * 2), 25)
        tag     = " <- strong signal" if d > 3 else (" <- medium signal" if d > 0.3 else " · weak signal")
        print(f"  {feat:<35} Invite={inv_val:5.1f}  Reject={rej_val:5.1f}  {bar}{tag}")

    # ─── 4. Noisy label detection ─────────────────────────────────────────────
    detect_noisy_labels(df)

    # ─── 5. Prepare X and y ───────────────────────────────────────────────────
    X = df[effective_features].values
    y = (df["recommendation"] == "Invite").astype(int).values
    # y = 1 -> Invite,  y = 0 -> Reject

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    print(f"\nSplit: {len(X_train)} train / {len(X_test)} test")

    # ─── 6. Define candidate models ───────────────────────────────────────────
    #
    # Each pipeline = [SMOTE] + StandardScaler + classifier
    # SMOTE generates synthetic examples of the minority class
    # StandardScaler is required for LogReg and SVM
    #
    use_smote = HAS_IMBLEARN and n_invite >= 10  # SMOTE needs at least k_neighbors+1 examples

    candidates = {
        "LogisticRegression": build_pipeline("lr", LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            C=1.0,
            random_state=42,
        ), use_smote=use_smote),
        "RandomForest": build_pipeline("rf", RandomForestClassifier(
            n_estimators=300,
            class_weight="balanced",
            max_depth=6,
            random_state=42,
        ), use_smote=use_smote),
        "GradientBoosting": build_pipeline("gb", GradientBoostingClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=4,
            random_state=42,
        ), use_smote=use_smote),
        "SVM_RBF": build_pipeline("svm", SVC(
            kernel="rbf",
            class_weight="balanced",
            probability=True,
            random_state=42,
        ), use_smote=use_smote),
    }

    # HistGradientBoosting natively supports class_weight (sklearn >= 1.3)
    try:
        candidates["HistGradientBoosting"] = build_pipeline("hgb", HistGradientBoostingClassifier(
            max_iter=200,
            learning_rate=0.05,
            max_depth=4,
            class_weight="balanced",
            random_state=42,
        ), use_smote=use_smote)
    except TypeError:
        # class_weight not supported in this version
        candidates["HistGradientBoosting"] = build_pipeline("hgb", HistGradientBoostingClassifier(
            max_iter=200,
            learning_rate=0.05,
            max_depth=4,
            random_state=42,
        ), use_smote=use_smote)

    if HAS_XGBOOST:
        # scale_pos_weight natively handles class imbalance
        scale_pos = n_reject / max(n_invite, 1)
        candidates["XGBoost"] = build_pipeline("xgb", XGBClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=4,
            scale_pos_weight=scale_pos,
            eval_metric="logloss",
            random_state=42,
            verbosity=0,
        ), use_smote=use_smote)

    # ─── 7. Compare models ────────────────────────────────────────────────────
    print("\n--- Model comparison ---")
    print(f"  {'Model':<25}  AUC (test)  F1 Invite (cv5)  F1 Reject (cv5)")
    print(f"  {'-'*25}  ----------  ---------------  ---------------")

    cv_strat = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    best_name, best_f1_cv, best_auc, best_pipeline = None, 0.0, 0.0, None

    for name, pipe in candidates.items():
        try:
            pipe.fit(X_train, y_train)

            # AUC on test set
            y_proba = pipe.predict_proba(X_test)[:, 1]
            auc = roc_auc_score(y_test, y_proba)

            # F1 in cross-validation (primary selection metric)
            f1_invite_cv = cross_val_score(pipe, X_train, y_train, cv=cv_strat, scoring="f1").mean()
            f1_reject_cv = cross_val_score(pipe, X_train, y_train, cv=cv_strat, scoring="f1_macro").mean()

            # Select by Invite F1 in CV (more stable than AUC on 1 split)
            marker = ""
            if f1_invite_cv > best_f1_cv:
                marker = "  <- BEST"
                best_f1_cv, best_auc, best_name, best_pipeline = f1_invite_cv, auc, name, pipe

            print(f"  {name:<25}  {auc:.3f}       {f1_invite_cv:.3f}            {f1_reject_cv:.3f}{marker}")

        except Exception as e:
            print(f"  {name:<25}  ERROR: {e}")

    if best_pipeline is None:
        print("\nERROR: No model succeeded.")
        sys.exit(1)

    # ─── 8. Hyperparameter search for the best model ──────────────────────────
    print(f"\n--- Hyperparameter tuning for {best_name} ---")

    param_grids = {
        "LogisticRegression": {
            "clf__C": [0.01, 0.1, 0.5, 1.0, 5.0, 10.0],
            "clf__penalty": ["l2"],
        },
        "RandomForest": {
            "clf__n_estimators": [100, 200, 300, 500],
            "clf__max_depth": [3, 4, 5, 6, 8, None],
            "clf__min_samples_leaf": [1, 2, 5],
        },
        "GradientBoosting": {
            "clf__n_estimators": [100, 200, 300],
            "clf__learning_rate": [0.01, 0.05, 0.1, 0.2],
            "clf__max_depth": [2, 3, 4, 5],
        },
        "SVM_RBF": {
            "clf__C": [0.1, 1.0, 10.0],
            "clf__gamma": ["scale", "auto", 0.01, 0.1],
        },
        "HistGradientBoosting": {
            "clf__max_iter": [100, 200, 300],
            "clf__learning_rate": [0.01, 0.05, 0.1, 0.2],
            "clf__max_depth": [2, 3, 4, 5],
        },
    }

    if HAS_XGBOOST:
        param_grids["XGBoost"] = {
            "clf__n_estimators": [100, 200, 300],
            "clf__learning_rate": [0.01, 0.05, 0.1, 0.2],
            "clf__max_depth": [2, 3, 4, 5, 6],
            "clf__subsample": [0.7, 0.8, 1.0],
        }

    if best_name in param_grids:
        search = RandomizedSearchCV(
            best_pipeline,
            param_grids[best_name],
            n_iter=min(20, len(param_grids[best_name])),
            cv=cv_strat,
            scoring="f1",
            random_state=42,
            n_jobs=-1,
            refit=True,
        )
        search.fit(X_train, y_train)
        best_pipeline = search.best_estimator_
        print(f"  Best parameters: {search.best_params_}")
        print(f"  Optimised F1 (cv5): {search.best_score_:.3f}")

        # Recompute AUC with optimised model
        y_proba = best_pipeline.predict_proba(X_test)[:, 1]
        best_auc = roc_auc_score(y_test, y_proba)
        best_f1_cv = search.best_score_
    else:
        print(f"  No param grid for {best_name}, keeping default parameters.")

    # ─── 9. Detailed evaluation of the best model ─────────────────────────────
    print(f"\n--- Detailed report: {best_name} ---")
    y_pred = best_pipeline.predict(X_test)

    print(classification_report(y_test, y_pred, target_names=["Reject", "Invite"]))

    cm = confusion_matrix(y_test, y_pred)
    print("Confusion matrix:")
    print(f"  Correctly rejected : {cm[0, 0]}   |  Falsely invited  : {cm[0, 1]}")
    print(f"  Falsely rejected   : {cm[1, 0]}   |  Correctly invited: {cm[1, 1]}")

    # ─── 10. Feature importance ───────────────────────────────────────────────
    clf = best_pipeline.named_steps["clf"]

    if hasattr(clf, "feature_importances_"):
        importances = clf.feature_importances_
    elif hasattr(clf, "coef_"):
        importances = np.abs(clf.coef_[0])
    else:
        importances = np.ones(len(effective_features))

    fi = sorted(zip(effective_features, importances), key=lambda x: x[1], reverse=True)
    print("\n--- Feature importance (what the model actually uses) ---")
    max_imp = fi[0][1] if fi else 1
    for feat, imp in fi:
        bar = "#" * int((imp / max_imp) * 25)
        print(f"  {feat:<35} {bar} {imp:.4f}")

    # ─── 11. Retrain on 100% of data then save ────────────────────────────────
    best_pipeline.fit(X, y)

    # Save model + effective features used
    model_artifact = {
        "pipeline": best_pipeline,
        "effective_features": effective_features,
        "all_feature_columns": FEATURE_COLUMNS,
        "derived_feature_names": DERIVED_FEATURE_NAMES,
        "model_name": best_name,
        "best_auc": best_auc,
        "best_f1_cv": best_f1_cv,
        "n_training_samples": len(X),
        "smote_used": use_smote and HAS_IMBLEARN,
    }
    joblib.dump(model_artifact, MODEL_PATH)

    print(f"\n{'=' * 60}")
    print(f"  [OK] model.joblib saved to {MODEL_PATH}")
    print(f"  Model          : {best_name}")
    print(f"  AUC (test)     : {best_auc:.3f}")
    print(f"  F1 Invite (cv) : {best_f1_cv:.3f}")
    print(f"  SMOTE          : {'Yes' if use_smote and HAS_IMBLEARN else 'No'}")
    print(f"  Features       : {len(effective_features)} effective / {len(all_features)} total")
    print(f"  Trained on     : {len(X)} candidates")
    print(f"{'=' * 60}")

    # Sanity test — strong profile vs weak profile
    # Build vectors using effective features
    strong_profile = {
        "total_years_experience": 10.0, "num_positions": 4, "avg_tenure_months": 30.0,
        "education_level_score": 4, "total_skills_count": 15, "has_certifications": 1,
        "language_count": 3, "section_completeness_score": 6, "max_language_score": 5,
        "has_senior_title": 1, "career_gap_months": 0, "latest_job_duration": 36,
        "has_summary": 1, "num_certifications": 3, "parse_quality_score": 2,
    }
    weak_profile = {
        "total_years_experience": 0.5, "num_positions": 1, "avg_tenure_months": 6.0,
        "education_level_score": 1, "total_skills_count": 2, "has_certifications": 0,
        "language_count": 1, "section_completeness_score": 3, "max_language_score": 3,
        "has_senior_title": 0, "career_gap_months": 6, "latest_job_duration": 6,
        "has_summary": 0, "num_certifications": 0, "parse_quality_score": 0,
    }

    # Add derived features
    for d in [strong_profile, weak_profile]:
        d["experience_education_ratio"] = d["total_years_experience"] / max(d["education_level_score"], 1)
        d["certs_per_year"] = d["num_certifications"] / max(d["total_years_experience"], 0.5)
        d["experience_x_seniority"] = d["total_years_experience"] * d["has_senior_title"]
        d["experience_x_education"] = d["total_years_experience"] * d["education_level_score"]

    vec_strong = np.array([[strong_profile[f] for f in effective_features]])
    vec_weak   = np.array([[weak_profile[f]   for f in effective_features]])

    pred_strong = best_pipeline.predict(vec_strong)[0]
    conf_strong = best_pipeline.predict_proba(vec_strong)[0].max()
    pred_weak   = best_pipeline.predict(vec_weak)[0]
    conf_weak   = best_pipeline.predict_proba(vec_weak)[0].max()

    print("\nSanity check:")
    print(f"  Strong profile (10 yrs, Master, 15 skills) -> {'Invite' if pred_strong == 1 else 'Reject'}  {conf_strong:.0%}")
    print(f"  Weak profile   (0.5 yr, high school, 2 skills) -> {'Invite' if pred_weak == 1 else 'Reject'} {conf_weak:.0%}")
    print()


if __name__ == "__main__":
    main()
