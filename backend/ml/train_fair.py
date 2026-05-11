"""
train_fair.py — Filtrant Fair Model Training (WP2)
===================================================
Trains a fairness-mitigated model using:
  1. Sample re-weighting (primary) — corrects label bias by upweighting
     underrepresented (group, label) combinations without discarding data.
  2. ExponentiatedGradient (secondary) — enforces TruePositiveRateParity
     constraint during training if re-weighting alone is insufficient.

Saves model_fair.joblib and fairness_report.json for the API.

Usage:
    docker compose exec backend python /app/ml/train_fair.py
"""

import json
import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from fairlearn.metrics import (
    MetricFrame,
    selection_rate,
    true_positive_rate,
    false_positive_rate,
)
from fairlearn.reductions import ExponentiatedGradient, TruePositiveRateParity

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
]

SENSITIVE_ATTRIBUTES = ["gender", "age_cohort", "is_multilingual"]


# ── EG wrapper (module-level so joblib can pickle it) ─────────────────────────

class EGWrapper:
    """Wraps ExponentiatedGradient + scaler into a sklearn-compatible object."""
    def __init__(self, scaler, eg):
        self.scaler = scaler
        self.eg = eg

    def predict(self, X):
        return self.eg.predict(self.scaler.transform(X))

    def predict_proba(self, X):
        return self.eg._pmf_predict(self.scaler.transform(X))


# ── Re-weighting ──────────────────────────────────────────────────────────────

def compute_reweighting(df: pd.DataFrame, sensitive_col: str) -> np.ndarray:
    """
    Manual implementation of AIF360's Reweighing algorithm.
    Assigns each sample a weight so that every (group, label) cell
    has the same expected probability as under a fully independent distribution.
    """
    y = df["passed_next_stage"].values
    groups = df[sensitive_col].astype(str).values
    n = len(df)

    weights = np.ones(n)
    for g in np.unique(groups):
        for label in [0, 1]:
            mask = (groups == g) & (y == label)
            p_g     = (groups == g).mean()
            p_y     = (y == label).mean()
            p_g_y   = mask.mean()
            if p_g_y > 0:
                weights[mask] = (p_g * p_y) / p_g_y

    # Normalise so weights sum to n
    weights = weights / weights.mean()
    return weights


def combine_weights(*weight_arrays) -> np.ndarray:
    """Element-wise product of multiple weight vectors, then renormalise."""
    combined = np.ones(len(weight_arrays[0]))
    for w in weight_arrays:
        combined *= w
    return combined / combined.mean()


# ── Fairness metrics helper ───────────────────────────────────────────────────

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
    df_train = df.loc[idx_train].copy()
    df_test  = df.loc[idx_test].copy()

    print(f"Split: {len(X_train)} train / {len(X_test)} test")

    # ── Load baseline for comparison ──────────────────────────────────────────
    baseline_metrics = None
    if BASELINE_PATH.exists():
        artifact = joblib.load(BASELINE_PATH)
        baseline_pipe = artifact["pipeline"]
        y_pred_base = baseline_pipe.predict(X_test)
        y_proba_base = baseline_pipe.predict_proba(X_test)[:, 1]
        baseline_auc = roc_auc_score(y_test, y_proba_base)
        baseline_metrics = compute_fairness_metrics(y_test, y_pred_base, df_test)
        print(f"\nBaseline AUC: {baseline_auc:.3f}")
        print("Baseline Equal Opportunity Differences:")
        for attr, m in baseline_metrics.items():
            flag = "⚠️" if abs(m["equal_opportunity_diff"]) > 0.05 else "✅"
            print(f"  {attr:<20} EOD = {m['equal_opportunity_diff']:+.3f}  {flag}")

    # ── Step 1: Re-weighting ──────────────────────────────────────────────────
    print("\n--- Step 1: Sample re-weighting ---")
    w_gender = compute_reweighting(df_train, "gender")
    w_age    = compute_reweighting(df_train, "age_cohort")
    w_lang   = compute_reweighting(df_train, "is_multilingual")
    sample_weights = combine_weights(w_gender, w_age, w_lang)

    print(f"  Weight range: [{sample_weights.min():.3f}, {sample_weights.max():.3f}]")
    print(f"  Weight mean:  {sample_weights.mean():.3f}")

    # Base estimator for re-weighted training
    scaler = StandardScaler()
    X_train_sc = scaler.fit_transform(X_train)
    X_test_sc  = scaler.transform(X_test)

    rf_rw = RandomForestClassifier(
        n_estimators=300, class_weight="balanced", max_depth=6, random_state=42
    )
    rf_rw.fit(X_train_sc, y_train, sample_weight=sample_weights)

    y_pred_rw   = rf_rw.predict(X_test_sc)
    y_proba_rw  = rf_rw.predict_proba(X_test_sc)[:, 1]
    auc_rw      = roc_auc_score(y_test, y_proba_rw)
    metrics_rw  = compute_fairness_metrics(y_test, y_pred_rw, df_test)

    print(f"\n  Re-weighted AUC: {auc_rw:.3f}")
    print("  Equal Opportunity Differences after re-weighting:")
    for attr, m in metrics_rw.items():
        flag = "⚠️" if abs(m["equal_opportunity_diff"]) > 0.05 else "✅"
        print(f"    {attr:<20} EOD = {m['equal_opportunity_diff']:+.3f}  {flag}")

    # ── Step 2: ExponentiatedGradient (if needed) ─────────────────────────────
    max_eod_rw = max(abs(m["equal_opportunity_diff"]) for m in metrics_rw.values())
    use_eg = max_eod_rw > 0.05

    if use_eg:
        print(f"\n--- Step 2: ExponentiatedGradient (max EOD {max_eod_rw:.3f} > 0.05) ---")
        base_clf = LogisticRegression(max_iter=1000, random_state=42)
        mitigator = ExponentiatedGradient(
            estimator=base_clf,
            constraints=TruePositiveRateParity(),
            eps=0.01,
        )
        # Use gender as primary sensitive feature (most binary, most interpretable)
        sf_train = df_train["gender"].values
        mitigator.fit(X_train_sc, y_train, sensitive_features=sf_train)

        y_pred_eg  = mitigator.predict(X_test_sc)
        y_proba_eg = mitigator._pmf_predict(X_test_sc)[:, 1]
        auc_eg     = roc_auc_score(y_test, y_proba_eg)
        metrics_eg = compute_fairness_metrics(y_test, y_pred_eg, df_test)

        print(f"  ExponentiatedGradient AUC: {auc_eg:.3f}")
        print("  Equal Opportunity Differences after EG:")
        for attr, m in metrics_eg.items():
            flag = "⚠️" if abs(m["equal_opportunity_diff"]) > 0.05 else "✅"
            print(f"    {attr:<20} EOD = {m['equal_opportunity_diff']:+.3f}  {flag}")

        # Pick better of the two
        max_eod_eg = max(abs(m["equal_opportunity_diff"]) for m in metrics_eg.values())
        if max_eod_eg < max_eod_rw:
            print("  -> ExponentiatedGradient selected as final model")
            final_pred, final_proba, final_auc, final_metrics = y_pred_eg, y_proba_eg, auc_eg, metrics_eg
            final_method = "ExponentiatedGradient"

            final_pipeline = EGWrapper(scaler, mitigator)
        else:
            print("  -> Re-weighted RandomForest selected (better EOD)")
            final_pred, final_proba, final_auc, final_metrics = y_pred_rw, y_proba_rw, auc_rw, metrics_rw
            final_method = "RandomForest+Reweighting"
            final_pipeline = Pipeline([("scaler", scaler), ("clf", rf_rw)])
    else:
        print(f"\n  Max EOD after re-weighting: {max_eod_rw:.3f} — ExponentiatedGradient not needed.")
        final_pred, final_proba, final_auc, final_metrics = y_pred_rw, y_proba_rw, auc_rw, metrics_rw
        final_method = "RandomForest+Reweighting"
        final_pipeline = Pipeline([("scaler", scaler), ("clf", rf_rw)])

    # ── Comparison summary ────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  COMPARISON: Baseline → Fair model")
    print(f"{'='*60}")
    if baseline_metrics:
        print(f"  AUC:  {baseline_auc:.3f} → {final_auc:.3f}  (delta: {final_auc - baseline_auc:+.3f})")
        for attr in SENSITIVE_ATTRIBUTES:
            b_eod = baseline_metrics[attr]["equal_opportunity_diff"]
            f_eod = final_metrics[attr]["equal_opportunity_diff"]
            print(f"  EOD ({attr:<18}): {b_eod:+.3f} → {f_eod:+.3f}  (delta: {f_eod - b_eod:+.3f})")

    print(f"\nClassification report (fair model):")
    print(classification_report(y_test, final_pred, target_names=["Reject", "Invite"]))

    # ── Save model ────────────────────────────────────────────────────────────
    artifact = {
        "pipeline": final_pipeline,
        "feature_columns": FEATURE_COLUMNS,
        "model_name": final_method,
        "best_auc": final_auc,
        "n_training_samples": len(X_train),
        "label_column": "passed_next_stage",
        "fairness_mitigated": True,
        "mitigation_method": final_method,
    }
    joblib.dump(artifact, FAIR_MODEL_PATH)
    print(f"\n[OK] model_fair.joblib saved")

    # ── Save fairness report for API ──────────────────────────────────────────
    report = {
        "model": final_method,
        "auc": round(final_auc, 3),
        "n_test": int(len(y_test)),
        "baseline": {
            "auc": round(baseline_auc, 3) if baseline_metrics else None,
            "metrics": baseline_metrics,
        } if baseline_metrics else None,
        "fair": {
            "auc": round(final_auc, 3),
            "metrics": final_metrics,
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

    # Convert any non-serialisable values
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
