"""
bootstrap_ci.py — WP2 Phase 2: BCa Bootstrap Confidence Intervals
==================================================================
Standalone module + CLI for computing bootstrap confidence intervals
on Equal Opportunity Difference (EOD) across demographic groups.

With subgroups of 30–80 samples, raw EOD values have high variance.
Bootstrap CIs establish whether a disparity is statistically meaningful:

  Decision rule (WP2 §2.3):
    - 95% CI strictly above 0.05  → mitigation required
    - 95% CI includes 0           → not statistically significant
    - 95% CI above 0 but ≤ 0.05  → borderline — monitor

Reusable API:
    from fairness_audit.bootstrap_ci import bca_eod_ci
    mean, lo, hi, verdict = bca_eod_ci(y_true, y_pred, sensitive_features)

CLI:
    docker compose exec backend python /app/ml/fairness_audit/bootstrap_ci.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

import numpy as np

# Allow running from repo root inside Docker
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Windows consoles default to cp1252 and crash on Unicode output; force UTF-8 so
# these audit scripts run natively (no Docker required).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).parent
DATA_PATH       = HERE.parent / "training_dataset.csv"
BASELINE_PATH   = HERE.parent / "model.joblib"
FAIR_MODEL_PATH = HERE.parent / "model_fair.joblib"

N_BOOTSTRAP = 10_000
ALPHA = 0.05          # 95% CI
THRESHOLD = 0.05      # WP2 §2.3 mitigation trigger


def _eod_statistic(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    sensitive: np.ndarray,
) -> float:
    """Equal Opportunity Difference = max(TPR) - min(TPR) across groups."""
    groups = np.unique(sensitive)
    tprs = []
    for g in groups:
        mask = sensitive == g
        y_t, y_p = y_true[mask], y_pred[mask]
        positives = y_t == 1
        if positives.sum() == 0:
            continue
        tprs.append(y_p[positives].mean())
    if len(tprs) < 2:
        return 0.0
    return float(max(tprs) - min(tprs))


def bca_eod_ci(
    y_true: Sequence,
    y_pred: Sequence,
    sensitive: Sequence,
    n_bootstrap: int = N_BOOTSTRAP,
    seed: int = 42,
) -> tuple[float, float, float, str]:
    """
    Percentile bootstrap CI for Equal Opportunity Difference.

    Returns (mean_eod, ci_low, ci_high, verdict).
    Verdict is one of: 'MITIGATE', 'BORDERLINE', 'OK', 'INSUFFICIENT_DATA'.
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    sensitive = np.asarray(sensitive)

    n = len(y_true)
    if n < 20:
        return float("nan"), float("nan"), float("nan"), "INSUFFICIENT_DATA"

    rng = np.random.default_rng(seed)
    boot_stats = np.empty(n_bootstrap)
    idx = np.arange(n)

    for i in range(n_bootstrap):
        s = rng.choice(idx, size=n, replace=True)
        boot_stats[i] = _eod_statistic(y_true[s], y_pred[s], sensitive[s])

    observed = _eod_statistic(y_true, y_pred, sensitive)
    lo = float(np.percentile(boot_stats, (ALPHA / 2) * 100))
    hi = float(np.percentile(boot_stats, (1 - ALPHA / 2) * 100))
    mean = float(np.mean(boot_stats))

    if lo > THRESHOLD:
        verdict = "MITIGATE"
    elif hi < THRESHOLD or hi < 0.02:
        verdict = "OK"
    else:
        verdict = "BORDERLINE"

    return observed, lo, hi, verdict


def _load_model_pipeline(path: Path):
    import joblib
    artifact = joblib.load(path)
    if isinstance(artifact, dict) and "pipeline" in artifact:
        return artifact["pipeline"], artifact.get("model_name", path.stem)
    return artifact, path.stem


def main() -> None:
    import pandas as pd
    from sklearn.model_selection import train_test_split

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

    print("\n" + "=" * 65)
    print("  FILTRANT — Bootstrap CI on Equal Opportunity Difference")
    print(f"  n_bootstrap={N_BOOTSTRAP:,}  alpha={ALPHA}  threshold={THRESHOLD}")
    print("=" * 65)

    if not DATA_PATH.exists():
        print(f"ERROR: {DATA_PATH} not found.")
        sys.exit(1)

    df = pd.read_csv(DATA_PATH)
    X = df[FEATURE_COLUMNS].fillna(0).values
    y = df["passed_next_stage"].values

    _, X_test, _, y_test, _, idx_test = train_test_split(
        X, y, df.index, test_size=0.2, stratify=y, random_state=42
    )
    df_test = df.loc[idx_test].copy()
    y_test_arr = np.array(y_test)

    SENSITIVE_CONFIGS = [
        ("gender",       df_test["gender"].values),
        ("age_cohort",   df_test["age_cohort"].values),
        ("multilingual", df_test["is_multilingual"].map({0: "mono", 1: "multi"}).values),
    ]

    models = []
    for label, path in [("Baseline", BASELINE_PATH), ("Fair", FAIR_MODEL_PATH)]:
        if path.exists():
            import joblib as _jl
            artifact = _jl.load(path)
            feat_cols = (artifact.get("feature_columns") if isinstance(artifact, dict) else None) or FEATURE_COLUMNS
            pipe, name = _load_model_pipeline(path)
            X_m = df[feat_cols].fillna(0).values
            _, X_test_m, _, _, _, _ = train_test_split(
                X_m, y, df.index, test_size=0.2, stratify=y, random_state=42
            )
            y_pred = pipe.predict(X_test_m)
            models.append((label, name, np.array(y_pred)))
        else:
            print(f"  ⚠️  {label} model not found at {path} — skipping")

    if not models:
        print("No models found. Run train.py and/or train_fair.py first.")
        sys.exit(1)

    verdict_symbols = {"MITIGATE": "⚠️ ", "BORDERLINE": "⚡", "OK": "✅", "INSUFFICIENT_DATA": "❓"}

    for model_label, model_name, y_pred in models:
        print(f"\n── {model_label} ({model_name}) ──────────────────────────────────")
        print(f"  {'Attribute':<18} {'EOD':>7} {'CI_low':>8} {'CI_high':>8}  Verdict")
        print(f"  {'─'*18} {'─'*7} {'─'*8} {'─'*8}  {'─'*20}")
        for attr, sensitive in SENSITIVE_CONFIGS:
            obs, lo, hi, verdict = bca_eod_ci(y_test_arr, y_pred, sensitive)
            sym = verdict_symbols.get(verdict, "?")
            print(f"  {attr:<18} {obs:>7.3f} {lo:>8.3f} {hi:>8.3f}  {sym} {verdict}")

    print(f"\n  Decision threshold: EOD CI_low > {THRESHOLD} → mitigation required")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
