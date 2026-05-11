"""
Script d'entraînement du modèle ML de screening CV — Filtrant (v2)
===================================================================
Améliorations vs v1 :
  - Suppression des features constantes (variance = 0) automatiquement
  - Ajout de features dérivées (interactions, ratios)
  - SMOTE pour le suréchantillonnage de la classe minoritaire
  - Plus de modèles : SVM, XGBoost, HistGradientBoosting
  - Recherche d'hyperparamètres via RandomizedSearchCV
  - Sélection du meilleur modèle par F1 moyen en cross-validation
  - Détection des labels potentiellement bruités

Usage (dans Docker) :
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
from sklearn.metrics import classification_report, confusion_matrix, f1_score, roc_auc_score
from sklearn.model_selection import (
    ParameterGrid,
    RandomizedSearchCV,
    RepeatedStratifiedKFold,
    StratifiedKFold,
    cross_val_predict,
    cross_val_score,
    train_test_split,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

# SMOTE pour le suréchantillonnage
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

# ─── Chemins ──────────────────────────────────────────────────────────────────
HERE = Path(__file__).parent
DATA_PATH = HERE / "candidates_export.csv"
MODEL_PATH = HERE / "model.joblib"

# ─── Features — dans le MÊME ordre que features.py ───────────────────────────
#
# Chaque feature est un chiffre extrait du CV parsé.
# Le modèle ne lit pas le texte — il ne voit que ces chiffres.
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

# ── Features dérivées (calculées à partir des features de base) ──────────────
DERIVED_FEATURE_NAMES = [
    "experience_education_ratio",  # total_years / education_level_score
    "certs_per_year",              # num_certifications / max(total_years, 0.5)
    "experience_x_seniority",     # total_years * has_senior_title
    "experience_x_education",     # total_years * education_level_score
]


def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute des features dérivées au DataFrame (in-place + return)."""
    df["experience_education_ratio"] = df["total_years_experience"] / df["education_level_score"].clip(lower=1)
    df["certs_per_year"] = df["num_certifications"] / df["total_years_experience"].clip(lower=0.5)
    df["experience_x_seniority"] = df["total_years_experience"] * df["has_senior_title"]
    df["experience_x_education"] = df["total_years_experience"] * df["education_level_score"]
    return df


def remove_constant_features(df: pd.DataFrame, feature_cols: list[str]) -> list[str]:
    """Supprime les features à variance nulle et retourne la liste filtrée."""
    constant = [col for col in feature_cols if df[col].nunique() <= 1]
    if constant:
        print(f"\n  [!] Features constantes supprimées (variance=0) : {constant}")
    return [col for col in feature_cols if col not in constant]


def detect_noisy_labels(df: pd.DataFrame) -> None:
    """Détecte les labels potentiellement incohérents."""
    print("\n--- Détection de labels potentiellement bruités ---")

    # Profils forts labellisés Reject
    strong_reject = df[
        (df["recommendation"] == "Reject")
        & (df["total_years_experience"] >= 5)
        & (df["education_level_score"] >= 4)
        & (df["has_senior_title"] == 1)
    ]

    # Profils faibles labellisés Invite
    weak_invite = df[
        (df["recommendation"] == "Invite")
        & (df["total_years_experience"] == 0)
        & (df["has_certifications"] == 0)
        & (df["has_senior_title"] == 0)
    ]

    n_strong_reject = len(strong_reject)
    n_weak_invite = len(weak_invite)

    if n_strong_reject > 0:
        print(f"  [!] {n_strong_reject} profils forts (5+ ans, Master+, Senior) labellisés Reject")
    if n_weak_invite > 0:
        print(f"  [!] {n_weak_invite} profils faibles (0 exp, 0 certif, pas Senior) labellisés Invite")
    if n_strong_reject == 0 and n_weak_invite == 0:
        print("  [OK] Aucune incohérence flagrante détectée.")

    total_noisy = n_strong_reject + n_weak_invite
    if total_noisy > 0:
        print(f"  -> {total_noisy} labels potentiellement bruités sur {len(df)} ({total_noisy/len(df)*100:.0f}%)")
        print("  -> Conseil : vérifier ces labels manuellement pour améliorer la qualité du modèle.")


def auto_clean_labels(X, y, cv, confidence_threshold: float = 0.85) -> tuple[np.ndarray, np.ndarray, int]:
    """
    Identifie les samples où un modèle baseline (LogReg balanced) prédit l'inverse
    du label avec haute confiance (>= confidence_threshold) en cross_val_predict.

    Retourne (X_clean, y_clean, n_removed). Ces samples sont probablement mal labellisés.
    """
    baseline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced",
                                    C=1.0, random_state=42)),
    ])
    proba_oof = cross_val_predict(baseline, X, y, cv=cv, method="predict_proba")[:, 1]

    # Sample bruité = labellisé Invite mais proba_invite très basse, ou inverse
    suspect_invite_to_reject = (y == 1) & (proba_oof < (1 - confidence_threshold))
    suspect_reject_to_invite = (y == 0) & (proba_oof > confidence_threshold)
    suspect_mask = suspect_invite_to_reject | suspect_reject_to_invite

    n_removed = int(suspect_mask.sum())
    n_inv_to_rej = int(suspect_invite_to_reject.sum())
    n_rej_to_inv = int(suspect_reject_to_invite.sum())

    print(f"  Confiance seuil : {confidence_threshold}")
    print(f"  Invite -> probablement Reject : {n_inv_to_rej}")
    print(f"  Reject -> probablement Invite : {n_rej_to_inv}")
    print(f"  Total retirés du train : {n_removed} / {len(y)} ({n_removed/len(y)*100:.1f}%)")

    keep_mask = ~suspect_mask
    return X[keep_mask], y[keep_mask], n_removed


def tune_threshold(pipeline, X, y, cv) -> tuple[float, float]:
    """
    Cherche le seuil de décision qui maximise le F1 sur la classe Invite (1)
    via cross_val_predict (probas out-of-fold).

    Retourne (best_threshold, best_f1).
    """
    proba_oof = cross_val_predict(pipeline, X, y, cv=cv, method="predict_proba")[:, 1]
    thresholds = np.linspace(0.05, 0.95, 91)
    f1_scores = [f1_score(y, (proba_oof >= t).astype(int), pos_label=1, zero_division=0)
                 for t in thresholds]
    best_idx = int(np.argmax(f1_scores))
    return float(thresholds[best_idx]), float(f1_scores[best_idx])


def build_pipeline(name: str, clf, use_smote: bool = True) -> Pipeline:
    """Construit un pipeline : [SMOTE optionnel] -> StandardScaler -> Classifieur."""
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
    print("  FILTRANT — Entraînement du modèle ML de screening CV (v2)")
    print("=" * 60)

    if HAS_IMBLEARN:
        print("  [OK] imbalanced-learn disponible — SMOTE activé")
    else:
        print("  [X] imbalanced-learn non disponible — SMOTE désactivé")

    if HAS_XGBOOST:
        print("  [OK] xgboost disponible")
    else:
        print("  [X] xgboost non disponible")

    # ─── 1. Charger les données ───────────────────────────────────────────────
    if not DATA_PATH.exists():
        print(f"\nERREUR : fichier introuvable -> {DATA_PATH}")
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

    # ─── 2. Feature engineering ───────────────────────────────────────────────
    add_derived_features(df)

    all_features = FEATURE_COLUMNS + DERIVED_FEATURE_NAMES
    df[all_features] = df[all_features].fillna(0)

    # Supprimer features constantes
    effective_features = remove_constant_features(df, all_features)

    # ─── 3. Analyse des features ──────────────────────────────────────────────
    print("\n--- Pouvoir discriminant de chaque feature ---")
    print("    (différence de moyenne Invite vs Reject)")
    print()

    means   = df.groupby("recommendation")[effective_features].mean()
    invite_m = means.loc["Invite"]
    reject_m = means.loc["Reject"]
    diff = (invite_m - reject_m).abs().sort_values(ascending=False)

    for feat, d in diff.items():
        inv_val = invite_m[feat]
        rej_val = reject_m[feat]
        bar     = "#" * min(int(d * 2), 25)
        tag     = " <- fort signal" if d > 3 else (" <- signal moyen" if d > 0.3 else " · signal faible")
        print(f"  {feat:<35} Invite={inv_val:5.1f}  Reject={rej_val:5.1f}  {bar}{tag}")

    # ─── 4. Détection de labels bruités ───────────────────────────────────────
    detect_noisy_labels(df)

    # ─── 5. Préparer X et y ───────────────────────────────────────────────────
    X = df[effective_features].values
    y = (df["recommendation"] == "Invite").astype(int).values
    # y = 1 -> Invite,  y = 0 -> Reject

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    print(f"\nSplit : {len(X_train)} train / {len(X_test)} test")

    # ─── 5.5 Auto-clean des labels bruités (sur TRAIN seulement) ──────────────
    print("\n--- Auto-clean des labels bruités (cross_val_predict) ---")
    clean_cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    X_train, y_train, n_cleaned = auto_clean_labels(X_train, y_train, clean_cv)
    print(f"  -> Train après clean : {len(X_train)} samples")

    # ─── 6. Définir les modèles candidats ─────────────────────────────────────
    #
    # Chaque pipeline = [SMOTE] + StandardScaler + classifieur
    # SMOTE génère des exemples synthétiques de la classe minoritaire
    # StandardScaler est nécessaire pour LogReg et SVM
    #
    use_smote = HAS_IMBLEARN and n_invite >= 10  # SMOTE a besoin d'au moins k_neighbors+1 exemples

    candidates = {
        "LogisticRegression": build_pipeline("lr", LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            C=1.0,
            random_state=42,
        ), use_smote=use_smote),
        "LogisticRegression_L1": build_pipeline("lr_l1", LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
            C=0.5,
            penalty="l1",
            solver="liblinear",
            random_state=42,
        ), use_smote=use_smote),
        "LogisticRegression_ElasticNet": build_pipeline("lr_en", LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
            C=0.5,
            penalty="elasticnet",
            l1_ratio=0.5,
            solver="saga",
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

    # HistGradientBoosting supporte nativement class_weight (sklearn >= 1.3)
    try:
        candidates["HistGradientBoosting"] = build_pipeline("hgb", HistGradientBoostingClassifier(
            max_iter=200,
            learning_rate=0.05,
            max_depth=4,
            class_weight="balanced",
            random_state=42,
        ), use_smote=use_smote)
    except TypeError:
        # class_weight pas supporté dans cette version
        candidates["HistGradientBoosting"] = build_pipeline("hgb", HistGradientBoostingClassifier(
            max_iter=200,
            learning_rate=0.05,
            max_depth=4,
            random_state=42,
        ), use_smote=use_smote)

    if HAS_XGBOOST:
        # scale_pos_weight gère nativement le déséquilibre des classes
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

    # ─── 7. Comparer les modèles ──────────────────────────────────────────────
    print("\n--- Comparaison des modèles ---")
    print(f"  {'Modèle':<25}  AUC (test)  F1 Invite (cv5)  F1 Reject (cv5)")
    print(f"  {'-'*25}  ----------  ---------------  ---------------")

    # RepeatedStratifiedKFold : 5 folds × 3 répétitions = 15 mesures (plus stable sur petit dataset)
    cv_strat = RepeatedStratifiedKFold(n_splits=5, n_repeats=3, random_state=42)
    best_name, best_f1_cv, best_auc, best_pipeline = None, 0.0, 0.0, None

    for name, pipe in candidates.items():
        try:
            pipe.fit(X_train, y_train)

            # AUC sur le test set
            y_proba = pipe.predict_proba(X_test)[:, 1]
            auc = roc_auc_score(y_test, y_proba)

            # F1 en cross-validation (métrique de sélection principale)
            f1_invite_cv = cross_val_score(pipe, X_train, y_train, cv=cv_strat, scoring="f1").mean()
            f1_reject_cv = cross_val_score(pipe, X_train, y_train, cv=cv_strat, scoring="f1_macro").mean()

            # Sélection par F1 Invite en CV (plus stable que AUC sur 1 split)
            marker = ""
            if f1_invite_cv > best_f1_cv:
                marker = "  <- MEILLEUR"
                best_f1_cv, best_auc, best_name, best_pipeline = f1_invite_cv, auc, name, pipe

            print(f"  {name:<25}  {auc:.3f}       {f1_invite_cv:.3f}            {f1_reject_cv:.3f}{marker}")

        except Exception as e:
            print(f"  {name:<25}  ERREUR : {e}")

    if best_pipeline is None:
        print("\nERREUR : Aucun modèle n'a fonctionné.")
        sys.exit(1)

    # ─── 8. Recherche d'hyperparamètres pour le meilleur modèle ───────────────
    print(f"\n--- Optimisation des hyperparamètres pour {best_name} ---")

    param_grids = {
        "LogisticRegression": {
            "clf__C": [0.01, 0.1, 0.5, 1.0, 5.0, 10.0],
            "clf__penalty": ["l2"],
        },
        "LogisticRegression_L1": {
            "clf__C": [0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
        },
        "LogisticRegression_ElasticNet": {
            "clf__C": [0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
            "clf__l1_ratio": [0.2, 0.5, 0.8],
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
        # n_iter = nb réel de combinaisons (produit des longueurs), pas nb de clés
        total_combos = len(list(ParameterGrid(param_grids[best_name])))
        search = RandomizedSearchCV(
            best_pipeline,
            param_grids[best_name],
            n_iter=min(30, total_combos),
            cv=cv_strat,
            scoring="f1",
            random_state=42,
            n_jobs=-1,
            refit=True,
        )
        search.fit(X_train, y_train)
        best_pipeline = search.best_estimator_
        print(f"  Meilleurs paramètres : {search.best_params_}")
        print(f"  F1 (cv5) optimisé   : {search.best_score_:.3f}")

        # Recalculer AUC avec le modèle optimisé
        y_proba = best_pipeline.predict_proba(X_test)[:, 1]
        best_auc = roc_auc_score(y_test, y_proba)
        best_f1_cv = search.best_score_
    else:
        print(f"  Pas de grille pour {best_name}, on garde les paramètres par défaut.")

    # ─── 8.5 Tuning du seuil de décision (max F1 Invite, CV out-of-fold) ──────
    print("\n--- Tuning du seuil de décision (classe Invite) ---")
    # cross_val_predict exige une partition -> StratifiedKFold simple (pas Repeated)
    threshold_cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    best_threshold, threshold_f1 = tune_threshold(best_pipeline, X_train, y_train, threshold_cv)
    print(f"  Seuil optimal : {best_threshold:.2f}  (F1 Invite cv = {threshold_f1:.3f})")
    print(f"  Seuil par défaut (0.50) -> F1 Invite cv = {best_f1_cv:.3f}")
    print(f"  Gain F1 vs 0.50 : {threshold_f1 - best_f1_cv:+.3f}")

    # ─── 9. Évaluation détaillée du meilleur ──────────────────────────────────
    print(f"\n--- Rapport détaillé : {best_name} (seuil={best_threshold:.2f}) ---")
    y_proba_test = best_pipeline.predict_proba(X_test)[:, 1]
    y_pred = (y_proba_test >= best_threshold).astype(int)

    print(classification_report(y_test, y_pred, target_names=["Reject", "Invite"]))

    cm = confusion_matrix(y_test, y_pred)
    print("Matrice de confusion :")
    print(f"  Correctement rejetés  : {cm[0, 0]}   |  Faussement invités : {cm[0, 1]}")
    print(f"  Faussement rejetés    : {cm[1, 0]}   |  Correctement invités : {cm[1, 1]}")

    # ─── 10. Feature importance ───────────────────────────────────────────────
    clf = best_pipeline.named_steps["clf"]

    if hasattr(clf, "feature_importances_"):
        importances = clf.feature_importances_
    elif hasattr(clf, "coef_"):
        importances = np.abs(clf.coef_[0])
    else:
        importances = np.ones(len(effective_features))

    fi = sorted(zip(effective_features, importances), key=lambda x: x[1], reverse=True)
    print("\n--- Feature importance (ce que le modèle utilise vraiment) ---")
    max_imp = fi[0][1] if fi else 1
    for feat, imp in fi:
        bar = "#" * int((imp / max_imp) * 25)
        print(f"  {feat:<35} {bar} {imp:.4f}")

    # ─── 11. Réentraîner sur train_clean + test puis sauvegarder ──────────────
    X_final = np.vstack([X_train, X_test])
    y_final = np.concatenate([y_train, y_test])
    best_pipeline.fit(X_final, y_final)

    # Sauvegarder le modèle + les features effectives utilisées
    model_artifact = {
        "pipeline": best_pipeline,
        "effective_features": effective_features,
        "all_feature_columns": FEATURE_COLUMNS,
        "derived_feature_names": DERIVED_FEATURE_NAMES,
        "model_name": best_name,
        "best_auc": best_auc,
        "best_f1_cv": best_f1_cv,
        "decision_threshold": best_threshold,
        "threshold_f1_cv": threshold_f1,
        "n_training_samples": len(X_final),
        "n_labels_cleaned": n_cleaned,
        "cv_strategy": "RepeatedStratifiedKFold(5x3)",
        "smote_used": use_smote and HAS_IMBLEARN,
    }
    joblib.dump(model_artifact, MODEL_PATH)

    print(f"\n{'=' * 60}")
    print(f"  [OK] model.joblib sauvegardé dans {MODEL_PATH}")
    print(f"  Modèle         : {best_name}")
    print(f"  AUC (test)     : {best_auc:.3f}")
    print(f"  F1 Invite (cv) : {best_f1_cv:.3f}  (seuil 0.50)")
    print(f"  F1 Invite (cv) : {threshold_f1:.3f}  (seuil {best_threshold:.2f})")
    print(f"  Seuil décision : {best_threshold:.2f}")
    print(f"  SMOTE          : {'Oui' if use_smote and HAS_IMBLEARN else 'Non'}")
    print(f"  Features       : {len(effective_features)} effectives / {len(all_features)} totales")
    print(f"  Entraîné sur   : {len(X)} candidats")
    print(f"{'=' * 60}")

    # Test de sanité — profil fort vs profil faible
    # On doit construire les vecteurs avec les features effectives
    all_feat_dict_fort = {
        "total_years_experience": 10.0, "num_positions": 4, "avg_tenure_months": 30.0,
        "education_level_score": 4, "total_skills_count": 15, "has_certifications": 1,
        "language_count": 3, "section_completeness_score": 6, "max_language_score": 5,
        "has_senior_title": 1, "career_gap_months": 0, "latest_job_duration": 36,
        "has_summary": 1, "num_certifications": 3, "parse_quality_score": 2,
    }
    all_feat_dict_faible = {
        "total_years_experience": 0.5, "num_positions": 1, "avg_tenure_months": 6.0,
        "education_level_score": 1, "total_skills_count": 2, "has_certifications": 0,
        "language_count": 1, "section_completeness_score": 3, "max_language_score": 3,
        "has_senior_title": 0, "career_gap_months": 6, "latest_job_duration": 6,
        "has_summary": 0, "num_certifications": 0, "parse_quality_score": 0,
    }

    # Ajouter features dérivées
    for d in [all_feat_dict_fort, all_feat_dict_faible]:
        d["experience_education_ratio"] = d["total_years_experience"] / max(d["education_level_score"], 1)
        d["certs_per_year"] = d["num_certifications"] / max(d["total_years_experience"], 0.5)
        d["experience_x_seniority"] = d["total_years_experience"] * d["has_senior_title"]
        d["experience_x_education"] = d["total_years_experience"] * d["education_level_score"]

    profil_fort   = np.array([[all_feat_dict_fort[f] for f in effective_features]])
    profil_faible = np.array([[all_feat_dict_faible[f] for f in effective_features]])

    proba_fort   = best_pipeline.predict_proba(profil_fort)[0]
    proba_faible = best_pipeline.predict_proba(profil_faible)[0]
    pred_fort   = int(proba_fort[1] >= best_threshold)
    pred_faible = int(proba_faible[1] >= best_threshold)
    conf_fort   = float(proba_fort[pred_fort])
    conf_faible = float(proba_faible[pred_faible])

    print("\nTest de cohérence :")
    print(f"  Profil fort   (10 ans, Master, 15 skills) -> {'Invite' if pred_fort == 1 else 'Reject'}  {conf_fort:.0%}")
    print(f"  Profil faible (0.5 an, lycée, 2 skills)   -> {'Invite' if pred_faible == 1 else 'Reject'} {conf_faible:.0%}")
    print()


if __name__ == "__main__":
    main()
