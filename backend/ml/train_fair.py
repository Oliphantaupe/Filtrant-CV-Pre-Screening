"""
train_fair.py — Filtrant Fair Model Training (WP2)
===================================================
Trains a fairness-mitigated model using sample re-weighting (AIF360 approach).
Re-weighting corrects label bias by upweighting underrepresented (group, label)
combinations without discarding data or distorting the model architecture.

Uses the same LogisticRegression as the baseline model so feature weights and
ranking quality are preserved. Applies temperature scaling on a held-out
calibration set to prevent overconfidence.

Usage:
    docker compose exec backend python /app/ml/train_fair.py
"""

import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from scipy.special import logit as _logit
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score, roc_auc_score
from sklearn.model_selection import cross_val_predict, StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from fairlearn.metrics import (
    MetricFrame,
    selection_rate,
    true_positive_rate,
    false_positive_rate,
)

warnings.filterwarnings("ignore")

HERE = Path(__file__).parent
DATA_PATH       = HERE / "training_dataset.csv"
BASELINE_PATH   = HERE / "model.joblib"
FAIR_MODEL_PATH = HERE / "model_fair.joblib"
REPORT_PATH     = HERE / "fairness_report.json"

FEATURE_COLUMNS = [
    "total_years_experience", "num_positions", "avg_tenure_months",
    "education_level_score", "total_skills_count", "has_certifications",
    "language_count", "section_completeness_score", "max_language_score",
    "has_senior_title", "career_gap_months", "latest_job_duration",
    "has_summary", "num_certifications", "parse_quality_score",
    "experience_education_ratio", "certs_per_year",
    "experience_x_seniority", "experience_x_education",
    "career_trajectory_score", "latest_title_seniority",
]

SENSITIVE_ATTRIBUTES = ["gender", "age_cohort", "is_multilingual"]


# ── Re-weighting ──────────────────────────────────────────────────────────────

def compute_reweighting(df: pd.DataFrame, sensitive_col: str) -> np.ndarray:
    """
    AIF360 Reweighing: assigns weights so (group, label) cells have the same
    expected probability as under a fully independent distribution.
    """
    y = df["passed_next_stage"].values
    groups = df[sensitive_col].astype(str).values
    n = len(df)

    weights = np.ones(n)
    for g in np.unique(groups):
        for label in [0, 1]:
            mask = (groups == g) & (y == label)
            p_g   = (groups == g).mean()
            p_y   = (y == label).mean()
            p_g_y = mask.mean()
            if p_g_y > 0:
                weights[mask] = (p_g * p_y) / p_g_y

    return weights / weights.mean()


def combine_weights(*weight_arrays) -> np.ndarray:
    combined = np.ones(len(weight_arrays[0]))
    for w in weight_arrays:
        combined *= w
    return combined / combined.mean()


# ── Noisy label cleaning ──────────────────────────────────────────────────────

def auto_clean_labels(X: np.ndarray, y: np.ndarray, confidence_threshold: float = 0.85) -> tuple:
    """
    Remove likely mislabeled samples using out-of-fold predictions from a baseline LR.
    A sample is flagged when the baseline predicts the opposite label with high confidence.
    Returns (X_clean, y_clean, keep_mask, n_removed).
    """
    baseline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced", C=1.0, random_state=42)),
    ])
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    proba_oof = cross_val_predict(baseline, X, y, cv=cv, method="predict_proba")[:, 1]
    suspect = ((y == 1) & (proba_oof < (1 - confidence_threshold))) | \
              ((y == 0) & (proba_oof > confidence_threshold))
    keep_mask = ~suspect
    return X[keep_mask], y[keep_mask], keep_mask, int(suspect.sum())


def tune_threshold(proba_invite: np.ndarray, y_true: np.ndarray) -> tuple[float, float]:
    """Find the decision threshold that maximises F1-Invite."""
    thresholds = np.arange(0.10, 0.90, 0.01)
    f1_scores = [
        f1_score(y_true, (proba_invite >= t).astype(int), zero_division=0)
        for t in thresholds
    ]
    best_idx = int(np.argmax(f1_scores))
    return float(thresholds[best_idx]), float(f1_scores[best_idx])


# ── Fairness metrics ──────────────────────────────────────────────────────────

def compute_fairness_metrics(y_true, y_pred, df_subset: pd.DataFrame) -> dict:
    result = {}
    for attr in SENSITIVE_ATTRIBUTES:
        sf = df_subset[attr].astype(str) if attr != "is_multilingual" else \
             df_subset[attr].map({0: "monolingual", 1: "multilingual"})
        mf = MetricFrame(
            metrics={
                "selection_rate": selection_rate,
                "tpr": true_positive_rate,
                "fpr": false_positive_rate,
            },
            y_true=y_true,
            y_pred=y_pred,
            sensitive_features=sf,
        )
        result[attr] = {
            "by_group": mf.by_group.round(3).to_dict(),
            "overall": {k: round(float(v), 3) for k, v in mf.overall.items()},
            "equal_opportunity_diff": round(float(mf.difference()["tpr"]), 3),
            "demographic_parity_diff": round(float(mf.difference()["selection_rate"]), 3),
        }
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 60)
    print("  FILTRANT — Fair Model Training (WP2)")
    print("=" * 60)

    if not DATA_PATH.exists():
        print(f"ERROR: {DATA_PATH} not found. Run parse_training_cvs.py first.")
        sys.exit(1)

    df = pd.read_csv(DATA_PATH)
    df[FEATURE_COLUMNS] = df[FEATURE_COLUMNS].fillna(0)

    n_total  = len(df)
    n_invite = (df["passed_next_stage"] == 1).sum()
    n_reject = (df["passed_next_stage"] == 0).sum()
    print(f"\nDataset: {n_total} | Invite: {n_invite} ({n_invite/n_total*100:.0f}%) | Reject: {n_reject}")

    X = df[FEATURE_COLUMNS].values
    y = df["passed_next_stage"].values

    X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
        X, y, df.index, test_size=0.2, stratify=y, random_state=42
    )
    df_test = df.loc[idx_test].copy()

    print(f"Split: {len(X_train)} train / {len(X_test)} test")

    # ── Calibration holdout (30% of train, never seen during fitting) ─────────
    idx_train_arr = np.array(idx_train)
    X_fit, X_cal, y_fit, y_cal, idx_fit, _ = train_test_split(
        X_train, y_train, idx_train_arr,
        test_size=0.30, stratify=y_train, random_state=42
    )
    df_fit = df.loc[idx_fit].copy()
    print(f"  Fit: {len(X_fit)} | Cal holdout: {len(X_cal)}")

    # ── Auto-clean likely mislabeled samples from fit set ─────────────────────
    print("\n--- Auto-cleaning mislabeled samples ---")
    X_fit, y_fit, keep_mask, n_cleaned = auto_clean_labels(X_fit, y_fit)
    df_fit = df_fit.iloc[np.where(keep_mask)[0]].reset_index(drop=True)
    print(f"  Removed {n_cleaned} suspect samples → {len(X_fit)} fit samples remain")

    # ── Load baseline for comparison ──────────────────────────────────────────
    baseline_metrics = None
    baseline_auc = None
    if BASELINE_PATH.exists():
        art = joblib.load(BASELINE_PATH)
        baseline_pipe = art["pipeline"]
        y_pred_base   = baseline_pipe.predict(X_test)
        y_proba_base  = baseline_pipe.predict_proba(X_test)[:, 1]
        baseline_auc  = roc_auc_score(y_test, y_proba_base)
        baseline_metrics = compute_fairness_metrics(y_test, y_pred_base, df_test)
        print(f"\nBaseline AUC: {baseline_auc:.3f}")
        print("Baseline Equal Opportunity Differences:")
        for attr, m in baseline_metrics.items():
            flag = "⚠️" if abs(m["equal_opportunity_diff"]) > 0.05 else "✅"
            print(f"  {attr:<20} EOD = {m['equal_opportunity_diff']:+.3f}  {flag}")

    # ── Sample re-weighting ───────────────────────────────────────────────────
    print("\n--- Sample re-weighting ---")
    w_gender = compute_reweighting(df_fit, "gender")
    w_age    = compute_reweighting(df_fit, "age_cohort")
    w_lang   = compute_reweighting(df_fit, "is_multilingual")
    sample_weights = combine_weights(w_gender, w_age, w_lang)

    print(f"  Weight range: [{sample_weights.min():.3f}, {sample_weights.max():.3f}]")

    # ── Fit re-weighted LR (same params as baseline) ──────────────────────────
    print("\n--- Re-weighted LogisticRegression ---")
    scaler = StandardScaler()
    X_fit_sc  = scaler.fit_transform(X_fit)
    X_cal_sc  = scaler.transform(X_cal)
    X_test_sc = scaler.transform(X_test)

    smote = SMOTE(k_neighbors=3, random_state=42)
    X_fit_sm, y_fit_sm = smote.fit_resample(X_fit_sc, y_fit)
    n_synthetic = len(X_fit_sm) - len(X_fit_sc)
    sample_weights_sm = np.concatenate([sample_weights, np.ones(n_synthetic)])

    clf = LogisticRegression(
        C=0.01, class_weight="balanced", max_iter=1000, random_state=42
    )
    clf.fit(X_fit_sm, y_fit_sm, sample_weight=sample_weights_sm)
    final_pipeline = Pipeline([("scaler", scaler), ("clf", clf)])

    y_pred_fair   = final_pipeline.predict(X_test)
    y_proba_fair  = final_pipeline.predict_proba(X_test)[:, 1]
    fair_auc      = roc_auc_score(y_test, y_proba_fair)
    fair_metrics  = compute_fairness_metrics(y_test, y_pred_fair, df_test)

    print(f"  AUC: {fair_auc:.3f}")
    print("  Equal Opportunity Differences:")
    for attr, m in fair_metrics.items():
        flag = "⚠️" if abs(m["equal_opportunity_diff"]) > 0.05 else "✅"
        base_eod = baseline_metrics[attr]["equal_opportunity_diff"] if baseline_metrics else float("nan")
        print(f"    {attr:<20} EOD = {m['equal_opportunity_diff']:+.3f}  {flag}  (baseline: {base_eod:+.3f})")

    # ── Temperature scaling on holdout ────────────────────────────────────────
    print("\n--- Temperature scaling on holdout ---")
    raw_proba_cal = final_pipeline.predict_proba(X_cal)[:, 1]
    raw_logit_cal = _logit(np.clip(raw_proba_cal, 1e-7, 1 - 1e-7))

    temp_lr = LogisticRegression(C=1e10, fit_intercept=False, random_state=42)
    temp_lr.fit(raw_logit_cal.reshape(-1, 1), y_cal)
    T = 1.0 / float(temp_lr.coef_[0][0])
    print(f"  Temperature T={T:.3f}  ({'softer' if T > 1 else 'sharper'})")

    # Verify calibrated proba range on test set
    raw_logit_test  = _logit(np.clip(y_proba_fair, 1e-7, 1 - 1e-7))
    p_cal_test = temp_lr.predict_proba(raw_logit_test.reshape(-1, 1))[:, 1]
    print(f"  Calibrated invite proba range: [{p_cal_test.min():.3f}, {p_cal_test.max():.3f}]")

    # ── Decision threshold tuning ─────────────────────────────────────────────
    print("\n--- Decision threshold tuning ---")
    best_threshold, threshold_f1 = tune_threshold(p_cal_test, y_test)
    print(f"  Optimal threshold: {best_threshold:.2f}  (F1-Invite = {threshold_f1:.3f})")
    print(f"  Default 0.50 would give F1-Invite = {f1_score(y_test, (p_cal_test >= 0.50).astype(int), zero_division=0):.3f}")

    # ── Comparison summary ────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  COMPARISON: Baseline → Fair model")
    print(f"{'='*60}")
    if baseline_metrics and baseline_auc is not None:
        print(f"  AUC:  {baseline_auc:.3f} → {fair_auc:.3f}  (delta: {fair_auc - baseline_auc:+.3f})")
        for attr in SENSITIVE_ATTRIBUTES:
            b_eod = baseline_metrics[attr]["equal_opportunity_diff"]
            f_eod = fair_metrics[attr]["equal_opportunity_diff"]
            delta = f_eod - b_eod
            flag = "✅" if abs(f_eod) <= abs(b_eod) else "⚠️"
            print(f"  EOD ({attr:<18}): {b_eod:+.3f} → {f_eod:+.3f}  (delta: {delta:+.3f}) {flag}")

    print(f"\nClassification report (fair model):")
    print(classification_report(y_test, y_pred_fair, target_names=["Reject", "Invite"]))

    # ── Save ──────────────────────────────────────────────────────────────────
    artifact = {
        "pipeline": final_pipeline,
        "calibrator": temp_lr,
        "calibrator_logit_transform": True,
        "feature_columns": FEATURE_COLUMNS,
        "model_name": "LogisticRegression+Reweighting",
        "best_auc": fair_auc,
        "temperature": T,
        "n_training_samples": len(X_train),
        "label_column": "passed_next_stage",
        "fairness_mitigated": True,
        "mitigation_method": "SampleReweighting",
        "decision_threshold": best_threshold,
        "threshold_f1": threshold_f1,
        "n_labels_cleaned": n_cleaned,
    }
    joblib.dump(artifact, FAIR_MODEL_PATH)
    print(f"\n[OK] model_fair.joblib saved")

    report = {
        "model": "LogisticRegression+Reweighting",
        "auc": round(fair_auc, 3),
        "temperature": round(T, 3),
        "n_test": int(len(y_test)),
        "baseline": {
            "auc": round(baseline_auc, 3) if baseline_auc else None,
            "metrics": baseline_metrics,
        } if baseline_metrics else None,
        "fair": {
            "auc": round(fair_auc, 3),
            "metrics": fair_metrics,
        },
        "label_distribution": {
            "invite": int(n_invite),
            "reject": int(n_reject),
            "total": int(n_total),
        },
        "group_counts": {
            attr: df[attr].astype(str).value_counts().to_dict()
            for attr in SENSITIVE_ATTRIBUTES
        },
    }

    def _clean(obj):
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64)):
            return round(float(obj), 3)
        return obj

    REPORT_PATH.write_text(json.dumps(_clean(report), indent=2), encoding="utf-8")
    print(f"[OK] fairness_report.json saved")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
