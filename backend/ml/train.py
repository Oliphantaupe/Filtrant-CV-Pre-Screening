"""
Script d'entraînement du modèle ML de screening CV — Filtrant
=============================================================
Ce script charge candidates_export.csv, compare 3 modèles,
sélectionne le meilleur, et sauvegarde model.joblib.

Usage (dans Docker) :
    docker compose exec backend python /app/ml/train.py
"""

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import warnings
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

# ─── Chemins ──────────────────────────────────────────────────────────────────
HERE = Path(__file__).parent
DATA_PATH = HERE / "candidates_export.csv"
MODEL_PATH = HERE / "model.joblib"

# ─── Features — dans le MÊME ordre que features.py ───────────────────────────
#
# Chaque feature est un chiffre extrait du CV parsé.
# Le modèle ne lit pas le texte — il ne voit que ces 15 chiffres.
#
FEATURE_COLUMNS = [
    # ── Expérience ────────────────────────────────────────────────────────────
    "total_years_experience",     # Années d'expérience totale (ex: 5.5)
    "num_positions",              # Nombre de postes différents (ex: 3)
    "avg_tenure_months",          # Durée moyenne par poste en mois (ex: 22.0)
    # ── Formation ─────────────────────────────────────────────────────────────
    "education_level_score",      # Niveau diplôme : 1=lycée 2=BTS 3=Licence 4=Master 5=PhD
    # ── Compétences ───────────────────────────────────────────────────────────
    "total_skills_count",         # Nb total skills (tech + méthodes + management)
    "has_certifications",         # A au moins une certification (0 ou 1)
    # ── Langues ───────────────────────────────────────────────────────────────
    "language_count",             # Nombre de langues parlées
    # ── Complétude du CV ──────────────────────────────────────────────────────
    "section_completeness_score", # Sections remplies parmi 6 (nom, résumé, formation, expé, skills, langues)
    "max_language_score",         # Meilleur niveau CEFR : 1=A1 2=A2 3=B1 4=B2 5=C1 6=C2
    # ── Signaux de séniorité ──────────────────────────────────────────────────
    "has_senior_title",           # Titre contient Senior/Lead/Manager/Director... (0 ou 1)
    "career_gap_months",          # Total des trous de carrière en mois
    "latest_job_duration",        # Durée du dernier poste en mois
    # ── Qualité du CV ─────────────────────────────────────────────────────────
    "has_summary",                # CV contient un résumé professionnel (0 ou 1)
    "num_certifications",         # Nombre de certifications (pas juste 0/1)
    "parse_quality_score",        # Qualité du parsing : 0=mauvais 1=partiel 2=complet
]


def main():
    print("\n" + "=" * 60)
    print("  FILTRANT — Entraînement du modèle ML de screening CV")
    print("=" * 60)

    # ─── 1. Charger les données ───────────────────────────────────────────────
    if not DATA_PATH.exists():
        print(f"\nERREUR : fichier introuvable → {DATA_PATH}")
        print("Lance d'abord : curl http://localhost:8000/api/v1/candidates/export.csv -o /app/ml/candidates_export.csv")
        sys.exit(1)

    df = pd.read_csv(DATA_PATH)
    df = df[df["recommendation"].isin(["Invite", "Reject"])].copy()
    df[FEATURE_COLUMNS] = df[FEATURE_COLUMNS].fillna(0)

    n_total  = len(df)
    n_invite = (df["recommendation"] == "Invite").sum()
    n_reject = (df["recommendation"] == "Reject").sum()

    print(f"\nDonnées chargées : {n_total} candidats")
    print(f"  Invite : {n_invite} ({n_invite / n_total * 100:.0f}%)")
    print(f"  Reject : {n_reject} ({n_reject / n_total * 100:.0f}%)")

    if n_total < 50:
        print("\nATTENTION : moins de 50 lignes — résultats peu fiables.")

    # ─── 2. Analyse des features ──────────────────────────────────────────────
    print("\n--- Pouvoir discriminant de chaque feature ---")
    print("    (différence de moyenne Invite vs Reject)")
    print()

    means   = df.groupby("recommendation")[FEATURE_COLUMNS].mean()
    invite_m = means.loc["Invite"]
    reject_m = means.loc["Reject"]
    diff = (invite_m - reject_m).abs().sort_values(ascending=False)

    for feat, d in diff.items():
        inv_val = invite_m[feat]
        rej_val = reject_m[feat]
        bar     = "█" * min(int(d * 2), 25)
        tag     = " ← fort signal" if d > 3 else (" ← signal moyen" if d > 0.3 else " · signal faible")
        print(f"  {feat:<35} Invite={inv_val:5.1f}  Reject={rej_val:5.1f}  {bar}{tag}")

    # ─── 3. Préparer X et y ───────────────────────────────────────────────────
    X = df[FEATURE_COLUMNS].values
    y = (df["recommendation"] == "Invite").astype(int).values
    # y = 1 → Invite,  y = 0 → Reject

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    print(f"\nSplit : {len(X_train)} train / {len(X_test)} test")

    # ─── 4. Définir et comparer les modèles ───────────────────────────────────
    #
    # Chaque pipeline = StandardScaler (normalise les chiffres) + classifieur
    # StandardScaler est nécessaire pour LogisticRegression
    # (les features ont des échelles très différentes : 0/1 vs 0-120 mois)
    #
    candidates = {
        "LogisticRegression": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(
                max_iter=1000,
                class_weight="balanced",  # compense le déséquilibre Invite/Reject
                C=1.0,
                random_state=42,
            )),
        ]),
        "RandomForest": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", RandomForestClassifier(
                n_estimators=300,
                class_weight="balanced",
                max_depth=6,
                random_state=42,
            )),
        ]),
        "GradientBoosting": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", GradientBoostingClassifier(
                n_estimators=200,
                learning_rate=0.05,
                max_depth=4,
                random_state=42,
            )),
        ]),
    }

    print("\n--- Comparaison des modèles ---")
    print(f"  {'Modèle':<25}  AUC (test)  F1 Invite (cv5)")
    print(f"  {'-'*25}  ----------  ---------------")

    cv_strat = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    best_name, best_auc, best_pipeline = None, 0.0, None

    for name, pipe in candidates.items():
        pipe.fit(X_train, y_train)
        y_proba = pipe.predict_proba(X_test)[:, 1]
        auc     = roc_auc_score(y_test, y_proba)
        f1_cv   = cross_val_score(pipe, X_train, y_train, cv=cv_strat, scoring="f1").mean()

        marker = "  ← MEILLEUR" if auc > best_auc else ""
        print(f"  {name:<25}  {auc:.3f}       {f1_cv:.3f}{marker}")

        if auc > best_auc:
            best_auc, best_name, best_pipeline = auc, name, pipe

    # ─── 5. Évaluation détaillée du meilleur ──────────────────────────────────
    print(f"\n--- Rapport détaillé : {best_name} ---")
    y_pred = best_pipeline.predict(X_test)

    print(classification_report(y_test, y_pred, target_names=["Reject", "Invite"]))

    cm = confusion_matrix(y_test, y_pred)
    print("Matrice de confusion :")
    print(f"  Correctement rejetés  : {cm[0, 0]}   |  Faussement invités : {cm[0, 1]}")
    print(f"  Faussement rejetés    : {cm[1, 0]}   |  Correctement invités : {cm[1, 1]}")

    # ─── 6. Feature importance ────────────────────────────────────────────────
    clf = best_pipeline.named_steps["clf"]

    if hasattr(clf, "feature_importances_"):
        importances = clf.feature_importances_
    elif hasattr(clf, "coef_"):
        importances = np.abs(clf.coef_[0])
    else:
        importances = np.ones(len(FEATURE_COLUMNS))

    fi = sorted(zip(FEATURE_COLUMNS, importances), key=lambda x: x[1], reverse=True)
    print("\n--- Feature importance (ce que le modèle utilise vraiment) ---")
    max_imp = fi[0][1] if fi else 1
    for feat, imp in fi:
        bar = "█" * int((imp / max_imp) * 25)
        print(f"  {feat:<35} {bar} {imp:.4f}")

    # ─── 7. Réentraîner sur 100% des données puis sauvegarder ─────────────────
    best_pipeline.fit(X, y)
    joblib.dump(best_pipeline, MODEL_PATH)

    print(f"\n{'=' * 60}")
    print(f"  ✓ model.joblib sauvegardé dans {MODEL_PATH}")
    print(f"  Modèle      : {best_name}")
    print(f"  AUC (test)  : {best_auc:.3f}")
    print(f"  Entraîné sur {len(X)} candidats")
    print(f"{'=' * 60}")

    # Test de sanité — profil fort vs profil faible
    profil_fort   = np.array([[10.0, 4, 30.0, 4, 15, 1, 3, 6, 5, 1, 0, 36, 1, 3, 2]])
    profil_faible = np.array([[0.5,  1,  6.0, 1,  2, 0, 1, 3, 3, 0, 6,  6, 0, 0, 0]])

    pred_fort   = best_pipeline.predict(profil_fort)[0]
    conf_fort   = best_pipeline.predict_proba(profil_fort)[0].max()
    pred_faible = best_pipeline.predict(profil_faible)[0]
    conf_faible = best_pipeline.predict_proba(profil_faible)[0].max()

    print("\nTest de cohérence :")
    print(f"  Profil fort   (10 ans, Master, 15 skills) → {'Invite' if pred_fort == 1 else 'Reject'}  {conf_fort:.0%}")
    print(f"  Profil faible (0.5 an, lycée, 2 skills)   → {'Invite' if pred_faible == 1 else 'Reject'} {conf_faible:.0%}")
    print()


if __name__ == "__main__":
    main()
