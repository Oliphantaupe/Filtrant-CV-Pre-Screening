"""
infer_proxies.py — WP2 Phase 0: Proxy Attribute Inference Documentation
========================================================================
Documents how demographic proxy attributes are derived in Filtrant.

Unlike the WP2 plan which proposed using `gender-guesser` on candidate names,
the actual implementation uses *explicit structured fields* already present in
the CV text files:
  - Gender: read directly from a "Gender:" header field in the CV
  - Age cohort: derived from "Date of Birth" field → birth_year → age → bucket
  - Multilingual flag: counted from the "Languages" section (≥ 2 → multilingual)

These attributes are computed by parse_training_cvs.py and stored in
training_dataset.csv. This script validates their coverage and prints a
full coverage report for audit purposes.

These attributes are NEVER fed to the prediction model — they exist only for
fairness metric calculation (proxy audit and bias mitigation weight computation).

Usage:
    docker compose exec backend python /app/ml/fairness_audit/infer_proxies.py
"""

from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
DATA_PATH = HERE.parent / "training_dataset.csv"
OUTPUT_PATH = HERE / "proxy_coverage_report.csv"

PROXY_COLUMNS = {
    "gender": {
        "description": "Derived from 'Gender:' header field in CV text",
        "method": "Direct extraction from structured CV header (not name-based inference)",
        "values": ["male", "female", "other"],
        "unknown_value": "other",
        "limitation": "'other' groups non-binary and missing/unreadable fields together — "
                      "treat as unknown for gender-specific metrics",
    },
    "age_cohort": {
        "description": "Derived from 'Date of Birth' field → birth_year → age = 2026 - birth_year",
        "method": "age ≤ 28 → '22-28' | ≤ 32 → '29-32' | ≤ 36 → '33-36' | else → '37-44'",
        "values": ["22-28", "29-32", "33-36", "37-44"],
        "unknown_value": None,
        "limitation": "Missing DOB defaults to birth_year=1990 (age≈36, lands in '33-36') — "
                      "may overcount that cohort",
    },
    "is_multilingual": {
        "description": "Derived from count of languages listed in 'Languages' section",
        "method": "language_count ≥ 2 → 1 (multilingual) | else → 0 (monolingual)",
        "values": [0, 1],
        "unknown_value": 0,
        "limitation": "Coarse proxy for immigration background — monolingual does not mean "
                      "native-born; multilingual does not confirm foreign origin",
    },
}


def print_section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def main() -> None:
    print("\n" + "=" * 60)
    print("  FILTRANT — Proxy Attribute Coverage Report (WP2 Phase 0)")
    print("=" * 60)

    if not DATA_PATH.exists():
        print(f"ERROR: {DATA_PATH} not found. Run parse_training_cvs.py first.")
        return

    df = pd.read_csv(DATA_PATH)
    n_total = len(df)
    print(f"\nDataset: {n_total} candidates loaded from {DATA_PATH.name}")

    for col, meta in PROXY_COLUMNS.items():
        print_section(col.upper())
        print(f"  Derivation : {meta['description']}")
        print(f"  Method     : {meta['method']}")
        print(f"  Limitation : {meta['limitation']}")

        if col not in df.columns:
            print(f"  ⚠️  COLUMN MISSING from dataset")
            continue

        counts = df[col].value_counts(dropna=False)
        print(f"\n  Distribution ({n_total} total):")
        for val, cnt in counts.items():
            pct = cnt / n_total * 100
            bar = "█" * int(pct / 2)
            label = f"  {str(val):<15} {cnt:>4}  ({pct:5.1f}%)  {bar}"
            unknown_flag = " ← treated as unknown" if val == meta["unknown_value"] else ""
            print(label + unknown_flag)

        missing = df[col].isna().sum()
        if missing:
            print(f"\n  ⚠️  {missing} rows have NaN — will be coerced to unknown value")

        usable = df[col] != meta["unknown_value"] if meta["unknown_value"] is not None else df[col].notna()
        print(f"\n  Usable rows (excl. unknown): {usable.sum()} / {n_total} "
              f"({usable.sum()/n_total*100:.1f}%)")

    # ── Export summary CSV ────────────────────────────────────────────────────
    print_section("EXPORT")
    proxy_df = df[["filename", "passed_next_stage", *PROXY_COLUMNS.keys()]].copy()
    proxy_df.to_csv(OUTPUT_PATH, index=False)
    print(f"  Proxy attribute summary saved → {OUTPUT_PATH}")

    # ── Cross-tabulation: label by group ──────────────────────────────────────
    print_section("LABEL DISTRIBUTION BY GROUP")
    for col in PROXY_COLUMNS:
        if col not in df.columns:
            continue
        ct = pd.crosstab(df[col], df["passed_next_stage"],
                         margins=True, margins_name="Total")
        ct.columns = ["Reject", "Invite", "Total"]
        ct["Invite%"] = (ct["Invite"] / ct["Total"] * 100).round(1)
        print(f"\n  {col}:")
        print(ct.to_string())

    print(f"\n{'=' * 60}")
    print("  Done. Use proxy_detection.py to measure bias in ML features.")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
