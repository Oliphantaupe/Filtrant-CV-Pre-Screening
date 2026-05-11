"""
proxy_detection.py
==================
Phase 2 — Detects proxy bias in the ML feature set.

Two methods:
  1. Mutual Information: quantifies how much each ML feature leaks
     demographic information (non-linear, captures complex dependencies).
  2. Adversarial Probe: trains a classifier to predict each protected
     attribute from ML features alone — high AUC = exploitable proxy.

Usage:
    docker compose exec backend python /app/ml/fairness_audit/proxy_detection.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import mutual_info_classif
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import LabelEncoder

HERE = Path(__file__).parent.parent
DATA_PATH = HERE / "training_dataset.csv"
REPORT_PATH = Path(__file__).parent.parent.parent.parent / "docs" / "fairness_audit_report.md"

FEATURE_COLUMNS = [
    "total_years_experience", "num_positions", "avg_tenure_months",
    "education_level_score", "total_skills_count", "has_certifications",
    "language_count", "section_completeness_score", "max_language_score",
    "has_senior_title", "career_gap_months", "latest_job_duration",
    "has_summary", "num_certifications", "parse_quality_score",
    "experience_education_ratio", "certs_per_year",
    "experience_x_seniority", "experience_x_education",
]

SENSITIVE_ATTRIBUTES = {
    "gender": "binary",
    "age_cohort": "multiclass",
    "is_multilingual": "binary",
}

MI_THRESHOLD = 0.05
AUC_THRESHOLD = 0.65


def run_mutual_information(X: np.ndarray, df: pd.DataFrame) -> dict:
    """Compute MI between each ML feature and each sensitive attribute."""
    results = {}
    for attr, kind in SENSITIVE_ATTRIBUTES.items():
        if kind == "binary":
            le = LabelEncoder()
            y_attr = le.fit_transform(df[attr].astype(str))
        else:
            le = LabelEncoder()
            y_attr = le.fit_transform(df[attr].astype(str))

        mi_scores = mutual_info_classif(X, y_attr, random_state=42)
        results[attr] = dict(zip(FEATURE_COLUMNS, mi_scores))
    return results


def run_adversarial_probe(X: np.ndarray, df: pd.DataFrame) -> dict:
    """Train a Random Forest to predict each sensitive attribute from ML features."""
    results = {}
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    clf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)

    for attr, kind in SENSITIVE_ATTRIBUTES.items():
        le = LabelEncoder()
        y_attr = le.fit_transform(df[attr].astype(str))

        if kind == "binary":
            scoring = "roc_auc"
            scores = cross_val_score(clf, X, y_attr, cv=cv, scoring=scoring)
            auc = scores.mean()
        else:
            # Multiclass: use OVR AUC
            scoring = "roc_auc_ovr_weighted"
            scores = cross_val_score(clf, X, y_attr, cv=cv, scoring=scoring)
            auc = scores.mean()

        results[attr] = {"auc": round(auc, 3), "std": round(scores.std(), 3)}
    return results


def print_and_build_report(mi_results: dict, adv_results: dict, df: pd.DataFrame) -> str:
    lines = []

    lines.append("# Fairness Audit — Proxy Bias Detection Report")
    lines.append(f"\nDataset: {len(df)} candidates | "
                 f"Invite: {(df['passed_next_stage']==1).sum()} | "
                 f"Reject: {(df['passed_next_stage']==0).sum()}")

    lines.append("\n---\n")
    lines.append("## 1. Mutual Information Analysis\n")
    lines.append("MI > 0.05 indicates a feature carries significant demographic signal.\n")

    for attr in SENSITIVE_ATTRIBUTES:
        lines.append(f"### {attr}")
        scores = mi_results[attr]
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        flagged = [(f, s) for f, s in sorted_scores if s > MI_THRESHOLD]
        safe = [(f, s) for f, s in sorted_scores if s <= MI_THRESHOLD]

        if flagged:
            lines.append(f"\n**Flagged (MI > {MI_THRESHOLD}):**")
            for feat, score in flagged:
                lines.append(f"- `{feat}`: MI = {score:.4f} ⚠️")
        lines.append(f"\n**Below threshold:**")
        for feat, score in safe[:5]:
            lines.append(f"- `{feat}`: MI = {score:.4f}")
        lines.append("")

    lines.append("---\n")
    lines.append("## 2. Adversarial Probe\n")
    lines.append(
        f"A Random Forest is trained on ML features only to predict each protected attribute. "
        f"AUC > {AUC_THRESHOLD} = exploitable proxy bias.\n"
    )

    for attr, result in adv_results.items():
        auc = result["auc"]
        flag = "⚠️  PROXY BIAS CONFIRMED" if auc > AUC_THRESHOLD else "✅ OK"
        lines.append(f"- **{attr}**: AUC = {auc:.3f} ± {result['std']:.3f}  {flag}")

    lines.append("\n---\n")
    lines.append("## 3. Interpretation\n")

    any_flagged = any(r["auc"] > AUC_THRESHOLD for r in adv_results.values())
    if any_flagged:
        lines.append(
            "At least one sensitive attribute is predictable from the ML feature set. "
            "This means the model can reconstruct demographic information even without "
            "explicit protected attributes — **mitigation is required** (see train_fair.py).\n"
        )
        lines.append("**Key proxy features to monitor:**")
        for attr in SENSITIVE_ATTRIBUTES:
            top = sorted(mi_results[attr].items(), key=lambda x: x[1], reverse=True)[:3]
            lines.append(f"- {attr}: " + ", ".join(f"`{f}` ({s:.3f})" for f, s in top))
    else:
        lines.append(
            "No sensitive attribute is strongly predictable from the ML features alone. "
            "Proxy bias risk is low, but re-weighting mitigation is still applied as a precaution.\n"
        )

    return "\n".join(lines)


def main():
    print("\n" + "=" * 60)
    print("  FILTRANT — Proxy Bias Detection")
    print("=" * 60)

    df = pd.read_csv(DATA_PATH)
    X = df[FEATURE_COLUMNS].fillna(0).values

    print(f"\nDataset loaded: {len(df)} rows")
    print("\n[1/2] Running Mutual Information analysis...")
    mi_results = run_mutual_information(X, df)

    print("[2/2] Running Adversarial Probe (5-fold CV)...")
    adv_results = run_adversarial_probe(X, df)

    # Print summary
    print("\n--- Adversarial Probe Results ---")
    for attr, result in adv_results.items():
        flag = "PROXY BIAS" if result["auc"] > AUC_THRESHOLD else "OK"
        print(f"  {attr:<20} AUC = {result['auc']:.3f} ± {result['std']:.3f}  [{flag}]")

    print("\n--- Top MI scores per attribute ---")
    for attr in SENSITIVE_ATTRIBUTES:
        top = sorted(mi_results[attr].items(), key=lambda x: x[1], reverse=True)[:3]
        print(f"  {attr}: " + "  |  ".join(f"{f}={s:.3f}" for f, s in top))

    # Write report
    report = print_and_build_report(mi_results, adv_results, df)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"\n[OK] Report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
