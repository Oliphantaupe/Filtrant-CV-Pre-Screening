"""
train.py — Filtrant CV Screening Model (WP2)
=============================================
Trains the baseline screening model on the unified training_dataset.csv
produced by parse_training_cvs.py.

Usage (inside Docker):
    docker compose exec backend python /app/ml/train.py
"""

import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
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

try:
    from imblearn.over_sampling import SMOTE
    from imblearn.pipeline import Pipeline as ImbPipeline
    HAS_IMBLEARN = True
except ImportError:
    HAS_IMBLEARN = False
    ImbPipeline = Pipeline

try:
    from xgboost import XGBClassifier
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

warnings.filterwarnings("ignore")

HERE = Path(__file__).parent
DATA_PATH  = HERE / "training_dataset.csv"
MODEL_PATH = HERE / "model.joblib"

# Demographic columns — never fed to the model
DEMO_COLUMNS = ["gender", "birth_year", "age", "age_cohort", "country", "is_multilingual"]

# All ML feature columns (base + derived) — must match parse_training_cvs.py output
FEATURE_COLUMNS = [
    "total_years_experience",
    "num_positions",
    "avg_tenure_months",
    "education_level_score",
    "total_skills_count",
    "has_certifications",
    "language_count",
    "section_completeness_score",
    "max_language_score",
    "has_senior_title",
    "career_gap_months",
    "latest_job_duration",
    "has_summary",
    "num_certifications",
    "parse_quality_score",
    "experience_education_ratio",
    "certs_per_year",
    "experience_x_seniority",
    "experience_x_education",
    "career_trajectory_score",
    "latest_title_seniority",
]


def detect_noisy_labels(df: pd.DataFrame) -> None:
    print("\n--- Noisy label detection ---")
    strong_reject = df[
        (df["passed_next_stage"] == 0)
        & (df["total_years_experience"] >= 5)
        & (df["education_level_score"] >= 4)
        & (df["has_senior_title"] == 1)
    ]
    weak_invite = df[
        (df["passed_next_stage"] == 1)
        & (df["total_years_experience"] == 0)
        & (df["has_certifications"] == 0)
        & (df["has_senior_title"] == 0)
    ]
    if strong_reject.empty and weak_invite.empty:
        print("  [OK] No obvious inconsistencies detected.")
    if not strong_reject.empty:
        print(f"  [!] {len(strong_reject)} strong profiles (5+ yrs, Master+, Senior) labelled Reject")
    if not weak_invite.empty:
        print(f"  [!] {len(weak_invite)} weak profiles (0 exp, 0 certs, no seniority) labelled Invite")
    total = len(strong_reject) + len(weak_invite)
    if total:
        print(f"  -> {total} potentially noisy labels ({total / len(df) * 100:.0f}%)")


def build_pipeline(clf, use_smote: bool) -> Pipeline:
    steps = []
    if use_smote and HAS_IMBLEARN:
        steps.append(("smote", SMOTE(random_state=42, k_neighbors=3)))
    steps.append(("scaler", StandardScaler()))
    steps.append(("clf", clf))
    return (ImbPipeline if use_smote and HAS_IMBLEARN else Pipeline)(steps)


def main():
    print("\n" + "=" * 60)
    print("  FILTRANT — Baseline Model Training (WP2)")
    print("=" * 60)

    if not DATA_PATH.exists():
        print(f"\nERROR: {DATA_PATH} not found.")
        print("Run first: python /app/ml/parse_training_cvs.py")
        sys.exit(1)

    # ── Load data ─────────────────────────────────────────────────────────────
    df = pd.read_csv(DATA_PATH)
    df[FEATURE_COLUMNS] = df[FEATURE_COLUMNS].fillna(0)

    n_total  = len(df)
    n_invite = (df["passed_next_stage"] == 1).sum()
    n_reject = (df["passed_next_stage"] == 0).sum()

    print(f"\nDataset: {n_total} candidates")
    print(f"  Invite: {n_invite} ({n_invite / n_total * 100:.0f}%)")
    print(f"  Reject: {n_reject} ({n_reject / n_total * 100:.0f}%)")
    print(f"  Gender — male: {(df['gender']=='male').sum()}  female: {(df['gender']=='female').sum()}")
    print(f"  Age cohorts — " + "  ".join(
        f"{c}: {(df['age_cohort']==c).sum()}" for c in ["22-28","29-32","33-36","37-44"]
    ))

    # ── Feature analysis ──────────────────────────────────────────────────────
    detect_noisy_labels(df)

    X = df[FEATURE_COLUMNS].values
    y = df["passed_next_stage"].values

    print("\n--- Feature discriminant power (Invite vs Reject mean diff) ---")
    invite_means = df[df["passed_next_stage"] == 1][FEATURE_COLUMNS].mean()
    reject_means = df[df["passed_next_stage"] == 0][FEATURE_COLUMNS].mean()
    diffs = (invite_means - reject_means).abs().sort_values(ascending=False)
    for feat, d in diffs.items():
        tag = " <- strong" if d > 3 else (" <- medium" if d > 0.3 else "")
        print(f"  {feat:<35} Invite={invite_means[feat]:5.1f}  Reject={reject_means[feat]:5.1f}{tag}")

    # ── Train / test split ────────────────────────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    print(f"\nSplit: {len(X_train)} train / {len(X_test)} test")

    use_smote = HAS_IMBLEARN and n_invite >= 10
    scale_pos = n_reject / max(n_invite, 1)

    candidates = {
        "LogisticRegression": build_pipeline(LogisticRegression(
            max_iter=1000, class_weight="balanced", C=1.0, random_state=42,
        ), use_smote),
        "RandomForest": build_pipeline(RandomForestClassifier(
            n_estimators=300, class_weight="balanced", max_depth=6, random_state=42,
        ), use_smote),
        "GradientBoosting": build_pipeline(GradientBoostingClassifier(
            n_estimators=200, learning_rate=0.05, max_depth=4, random_state=42,
        ), use_smote),
        "SVM_RBF": build_pipeline(SVC(
            kernel="rbf", class_weight="balanced", probability=True, random_state=42,
        ), use_smote),
    }
    try:
        candidates["HistGradientBoosting"] = build_pipeline(HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.05, max_depth=4, class_weight="balanced", random_state=42,
        ), use_smote)
    except TypeError:
        candidates["HistGradientBoosting"] = build_pipeline(HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.05, max_depth=4, random_state=42,
        ), use_smote)

    if HAS_XGBOOST:
        candidates["XGBoost"] = build_pipeline(XGBClassifier(
            n_estimators=200, learning_rate=0.05, max_depth=4,
            scale_pos_weight=scale_pos, eval_metric="logloss", random_state=42, verbosity=0,
        ), use_smote)

    # ── Model comparison ──────────────────────────────────────────────────────
    print("\n--- Model comparison ---")
    print(f"  {'Model':<25}  AUC (test)  F0.5 Invite (cv5)")
    print(f"  {'-'*25}  ----------  ---------------")

    cv_strat = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    best_name, best_f1_cv, best_auc, best_pipeline = None, 0.0, 0.0, None

    # F0.5 penalises false positives (inviting an unqualified candidate) more than
    # false negatives — better suited for recruitment than symmetric F1.
    SCORING = "f_beta"
    from sklearn.metrics import fbeta_score, make_scorer
    f05_scorer = make_scorer(fbeta_score, beta=0.5)

    for name, pipe in candidates.items():
        try:
            pipe.fit(X_train, y_train)
            y_proba = pipe.predict_proba(X_test)[:, 1]
            auc = roc_auc_score(y_test, y_proba)
            f1_cv = cross_val_score(pipe, X_train, y_train, cv=cv_strat, scoring=f05_scorer).mean()
            marker = ""
            if f1_cv > best_f1_cv:
                marker = "  <- BEST"
                best_f1_cv, best_auc, best_name, best_pipeline = f1_cv, auc, name, pipe
            print(f"  {name:<25}  {auc:.3f}       {f1_cv:.3f}{marker}")
        except Exception as e:
            print(f"  {name:<25}  ERROR: {e}")

    if best_pipeline is None:
        print("\nERROR: no model succeeded.")
        sys.exit(1)

    # ── Hyperparameter tuning ─────────────────────────────────────────────────
    print(f"\n--- Tuning {best_name} ---")
    param_grids = {
        "LogisticRegression": {"clf__C": [0.01, 0.1, 0.5, 1.0, 5.0, 10.0]},
        "RandomForest": {
            "clf__n_estimators": [100, 200, 300, 500],
            "clf__max_depth": [3, 4, 5, 6, None],
            "clf__min_samples_leaf": [1, 2, 5],
        },
        "GradientBoosting": {
            "clf__n_estimators": [100, 200, 300],
            "clf__learning_rate": [0.01, 0.05, 0.1, 0.2],
            "clf__max_depth": [2, 3, 4, 5],
        },
        "SVM_RBF": {"clf__C": [0.1, 1.0, 10.0], "clf__gamma": ["scale", "auto"]},
        "HistGradientBoosting": {
            "clf__max_iter": [100, 200, 300],
            "clf__learning_rate": [0.01, 0.05, 0.1],
            "clf__max_depth": [2, 3, 4, 5],
        },
        "XGBoost": {
            "clf__n_estimators": [100, 200, 300],
            "clf__learning_rate": [0.01, 0.05, 0.1, 0.2],
            "clf__max_depth": [2, 3, 4, 6],
        },
    }

    if best_name in param_grids:
        search = RandomizedSearchCV(
            best_pipeline, param_grids[best_name],
            n_iter=20, cv=cv_strat, scoring=f05_scorer,
            random_state=42, n_jobs=-1, refit=True,
        )
        search.fit(X_train, y_train)
        best_pipeline = search.best_estimator_
        y_proba = best_pipeline.predict_proba(X_test)[:, 1]
        best_auc = roc_auc_score(y_test, y_proba)
        best_f1_cv = search.best_score_
        print(f"  Best params: {search.best_params_}")
        print(f"  F1 (cv5): {best_f1_cv:.3f}")

    # ── Evaluation ────────────────────────────────────────────────────────────
    print(f"\n--- Evaluation: {best_name} ---")
    y_pred = best_pipeline.predict(X_test)
    print(classification_report(y_test, y_pred, target_names=["Reject", "Invite"]))
    cm = confusion_matrix(y_test, y_pred)
    print(f"Confusion matrix:")
    print(f"  Correctly rejected: {cm[0,0]}  Falsely invited:   {cm[0,1]}")
    print(f"  Falsely rejected:   {cm[1,0]}  Correctly invited: {cm[1,1]}")

    # ── Feature importance ────────────────────────────────────────────────────
    clf = best_pipeline.named_steps["clf"]
    if hasattr(clf, "feature_importances_"):
        importances = clf.feature_importances_
    elif hasattr(clf, "coef_"):
        importances = np.abs(clf.coef_[0])
    else:
        # HistGradientBoosting/SVM expose neither feature_importances_ nor coef_, so
        # fall back to permutation importance (model-agnostic) instead of printing a
        # meaningless flat vector.
        from sklearn.inspection import permutation_importance
        perm = permutation_importance(
            best_pipeline, X_test, y_test, n_repeats=10,
            random_state=42, scoring="roc_auc",
        )
        importances = perm.importances_mean

    fi = sorted(zip(FEATURE_COLUMNS, importances), key=lambda x: x[1], reverse=True)
    print("\n--- Feature importance ---")
    max_imp = fi[0][1] if fi else 1
    for feat, imp in fi:
        bar = "#" * int((imp / max_imp) * 25)
        print(f"  {feat:<35} {bar} {imp:.4f}")

    # ── Retrain on full data + save ───────────────────────────────────────────
    best_pipeline.fit(X, y)
    artifact = {
        "pipeline": best_pipeline,
        "feature_columns": FEATURE_COLUMNS,
        "model_name": best_name,
        "best_auc": best_auc,
        "best_f1_cv": best_f1_cv,
        "n_training_samples": len(X),
        "smote_used": use_smote and HAS_IMBLEARN,
        "label_column": "passed_next_stage",
    }
    joblib.dump(artifact, MODEL_PATH)

    print(f"\n{'='*60}")
    print(f"  [OK] model.joblib saved")
    print(f"  Model    : {best_name}")
    print(f"  AUC      : {best_auc:.3f}")
    print(f"  F1 (cv5) : {best_f1_cv:.3f}")
    print(f"  Features : {len(FEATURE_COLUMNS)}")
    print(f"  Trained on {len(X)} candidates")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
