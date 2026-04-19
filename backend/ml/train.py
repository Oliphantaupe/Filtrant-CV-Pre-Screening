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

    cv_strat = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
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
        print(f"  Meilleurs paramètres : {search.best_params_}")
        print(f"  F1 (cv5) optimisé   : {search.best_score_:.3f}")

        # Recalculer AUC avec le modèle optimisé
        y_proba = best_pipeline.predict_proba(X_test)[:, 1]
        best_auc = roc_auc_score(y_test, y_proba)
        best_f1_cv = search.best_score_
    else:
        print(f"  Pas de grille pour {best_name}, on garde les paramètres par défaut.")

    # ─── 9. Évaluation détaillée du meilleur ──────────────────────────────────
    print(f"\n--- Rapport détaillé : {best_name} ---")
    y_pred = best_pipeline.predict(X_test)

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

    # ─── 11. Réentraîner sur 100% des données puis sauvegarder ────────────────
    best_pipeline.fit(X, y)

    # Sauvegarder le modèle + les features effectives utilisées
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
    print(f"  [OK] model.joblib sauvegardé dans {MODEL_PATH}")
    print(f"  Modèle         : {best_name}")
    print(f"  AUC (test)     : {best_auc:.3f}")
    print(f"  F1 Invite (cv) : {best_f1_cv:.3f}")
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

    pred_fort   = best_pipeline.predict(profil_fort)[0]
    conf_fort   = best_pipeline.predict_proba(profil_fort)[0].max()
    pred_faible = best_pipeline.predict(profil_faible)[0]
    conf_faible = best_pipeline.predict_proba(profil_faible)[0].max()

    print("\nTest de cohérence :")
    print(f"  Profil fort   (10 ans, Master, 15 skills) -> {'Invite' if pred_fort == 1 else 'Reject'}  {conf_fort:.0%}")
    print(f"  Profil faible (0.5 an, lycée, 2 skills)   -> {'Invite' if pred_faible == 1 else 'Reject'} {conf_faible:.0%}")
    print()


if __name__ == "__main__":
    main()
