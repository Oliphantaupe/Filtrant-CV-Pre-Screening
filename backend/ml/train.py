"""
ML training script.
Run this once you have enough labelled CSV data:
  python ml/train.py --data path/to/candidates.csv

The CSV must have columns: [FEATURE_COLUMNS] + recommendation
where recommendation is "Invite" or "Reject".
"""
import argparse
import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report

FEATURE_COLUMNS = [
    "total_years_experience",
    "num_positions",
    "avg_tenure_months",
    "education_level_score",
    "total_skills_count",
    "has_certifications",
    "language_count",
    "section_completeness_score",
]
MODEL_PATH = "ml/model.joblib"


def train(data_path: str):
    df = pd.read_csv(data_path)

    missing = [c for c in FEATURE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in CSV: {missing}")

    X = df[FEATURE_COLUMNS].fillna(0)
    y = (df["recommendation"] == "Invite").astype(int)

    print(f"Dataset: {len(df)} rows | Invite: {y.sum()} | Reject: {(~y.astype(bool)).sum()}")

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(pipeline, X, y, cv=cv, scoring="f1")
    print(f"Cross-val F1: {scores.mean():.3f} ± {scores.std():.3f}")

    pipeline.fit(X, y)
    y_pred = pipeline.predict(X)
    print("\nTrain classification report:")
    print(classification_report(y, y_pred, target_names=["Reject", "Invite"]))

    joblib.dump(pipeline, MODEL_PATH)
    print(f"\nModel saved to {MODEL_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Path to labelled CSV")
    args = parser.parse_args()
    train(args.data)
