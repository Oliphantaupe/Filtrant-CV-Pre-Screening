# Fairness Audit — Filtrant CV Pre-Screening System

> **LuxTalent Advisory Group S.A.** · Work Package 2 · Fairness Audit & Model Redesign
> Notebook de référence : `backend/ml/fairness_audit/`

---

## Table des matières

1. [Introduction & contexte légal](#introduction--contexte-légal)
2. [Méthodologie générale de l'audit](#méthodologie-générale-de-laudit)
3. [Données & setup](#données--setup)
4. [Attributs sensibles & groupes protégés](#attributs-sensibles--groupes-protégés)
5. [Métriques d'équité — choix et justification](#métriques-déquité--choix-et-justification)
6. [Détection des proxies](#détection-des-proxies)
7. [Analyse par attribut](#analyse-par-attribut)
8. [Stratégie corrective retenue](#stratégie-corrective-retenue)
9. [Comparaison baseline vs Fair Model v2](#comparaison-baseline-vs-fair-model-v2)
10. [Explicabilité des décisions](#explicabilité-des-décisions)
11. [Conclusion & recommandations](#conclusion--recommandations)
12. [Glossaire](#glossaire)

---

## Introduction & contexte légal

Le système Filtrant automatise la présélection de CVs pour LuxTalent Advisory Group. Plusieurs mois après déploiement, l'équipe de conformité RH a observé que certaines catégories de candidats étaient invitées à des taux significativement différents. Le modèle ayant appris sur des décisions historiques, il peut avoir absorbé des biais implicites présents dans ces données.

**La question centrale :** est-ce que le modèle traite tout le monde équitablement ? En particulier, est-ce qu'à *qualification égale*, les candidats sont traités identiquement quel que soit leur genre présumé, leur âge, ou leur profil linguistique ?

### Cadre légal — pourquoi cet audit est une obligation

L'**Annexe III de l'AI Act** classe les outils automatisés de présélection de CVs comme **systèmes à haut risque**. Cela impose à LuxTalent les obligations suivantes :

| Article AI Act | Obligation | Couvert dans cet audit |
|---|---|---|
| **Art. 9** | Système de gestion des risques documenté | Document entier |
| **Art. 10** | Gouvernance des données, détection et correction des biais | §4 à §9 |
| **Art. 13** | Transparence envers les déployeurs | §10 (SHAP global) |
| **Art. 14** | Supervision humaine effective | Override UI + processing_log |
| **Art. 15** | Exactitude et robustesse | §6 (bootstrap CI), §9 (perf avant/après) |

> Autres références : Directive 2000/43/CE (origine ethnique), Directive 2000/78/CE (âge), RGPD Art. 9 (données sensibles), RGPD Art. 22 (décisions automatisées).

---

## Méthodologie générale de l'audit

L'audit suit **5 étapes** explicites, chacune justifiée méthodologiquement.

| Étape | Ce qui est fait | Pourquoi c'est nécessaire |
|---|---|---|
| **1.** Inférence des attributs sensibles | Proxies inférés depuis les features CV | Le dataset ne contient pas les attributs démographiques directs — on reconstruit des proxies défendables légalement |
| **2.** Détection des proxies (MI + adversarial probe) | Mutual Information + Random Forest adversarial | Identifier quelles features ML "leakent" de l'information démographique avant d'agir |
| **3.** Calcul des métriques d'équité par groupe | EOD · DP diff · selection rate · TPR | Aucune métrique seule n'est suffisante — leur combinaison révèle des biais que chacune prise isolément manquerait |
| **4.** Validation statistique | Bootstrap CI 95% (1000 ré-échantillonnages) | Un écart visible peut venir du hasard avec un petit n — on ne conclut que sur des écarts statistiquement robustes |
| **5.** Mitigation + comparaison avant/après | AIF360 sample re-weighting | Corriger en amont (pré-processing) sans créer de leakage, et documenter le coût en performance |

### Deux règles appliquées dans tout l'audit

**1. Out-of-sample uniquement.**
Toutes les métriques d'équité sont calculées sur le test set, jamais sur les données d'entraînement. Évaluer sur le train gonfle artificiellement les TPR et masque les biais.

**2. Honnêteté sur l'incertitude.**
Avec un dataset de 500 candidats synthétiques, certaines métriques par sous-groupe sont bruitées. On les quantifie via des IC bootstrap plutôt que de présenter des chiffres ponctuels comme s'ils étaient stables.

---

## Données & setup

| Élément | Valeur |
|---|---|
| Dataset | 500 candidats synthétiques |
| Taux de sélection réel (`Invite`) | ~41% (204 Invite / 294 Reject) |
| Modèle baseline | LogisticRegression (L2, `class_weight='balanced'`) |
| Modèle Fair v2 | LogisticRegression + AIF360 Reweighing |
| Features | 21 features engineered (voir `services/features.py`) |

### Split train/test

```
Dataset 500 candidats
├── Train  400 candidats  ← entraînement + re-weighting
└── Test   100 candidats  ← base de tout l'audit (out-of-sample)
```

Les métriques d'équité sont calculées sur le test set uniquement. Le seuil de décision est optimisé sur un set de validation séparé (80 candidats) pour éviter le data leakage.

---

## Attributs sensibles & groupes protégés

Le dataset ne contient **pas** les attributs démographiques directs (genre, âge, nationalité). L'AI Act et le RGPD considèrent qu'**une feature qui révèle indirectement un attribut protégé est elle-même sensible** — c'est le principe du *proxy*.

Trois attributs sensibles sont inférés depuis les features CV :

| Attribut inféré | Méthode d'inférence | Groupes | Base légale |
|---|---|---|---|
| `gender` | Prénom → `gender-guesser` (male / female / unknown) | female · male | Directive 2000/78/CE |
| `age_cohort` | Année de la 1ère expérience → cohorte | 22–28 · 29–32 · 33–36 · 37–44 | Directive 2000/78/CE |
| `is_multilingual` | `language_count ≥ 2` | monolingual · multilingual | RGPD Art. 9 — proxy d'origine |

### Pourquoi ces proxies et pas d'autres

**Genre :** les prénoms sont des proxies courants du genre dans les CVs européens. La méthode `gender-guesser` atteint ~85% de précision sur les prénoms latins et anglophones. Les cas ambigus sont exclus de l'analyse (`unknown`).

**Âge :** l'année de début de la première expérience professionnelle est le signal le plus stable disponible. La bucketisation en cohortes (22–28, 29–32, 33–36, 37–44) suit les seuils de la littérature AARP sur la discrimination par âge.

**Multilinguisme :** `language_count ≥ 2` est un proxy grossier mais défendable de la mobilité internationale et, dans le contexte luxembourgeois, de l'origine non-native. C'est la feature disponible la moins intrusive.

> ⚠ Ces proxies **ne sont jamais fournis au modèle de prédiction** — ils servent exclusivement à l'audit et à la pondération des exemples d'entraînement (re-weighting). Le modèle ne "voit" jamais le genre, l'âge, ni le multilinguisme inféré.

---

## Métriques d'équité — choix et justification

Trois métriques complémentaires sont utilisées. Aucune seule n'est suffisante.

### Les trois métriques

**1. Selection rate** — taux de candidats prédits sélectionnés dans un groupe.
```
selection_rate(a) = P(Ŷ=1 | A=a)
```

**2. Demographic Parity Difference (DP diff)**
```
DP diff = max(selection_rate) − min(selection_rate)
Seuil d'alerte : > 0.10
```
Mesure l'écart brut entre groupes. **Limite :** trompeur si les base rates de qualification diffèrent réellement entre groupes.

**3. Equal Opportunity Difference (EOD)** ← *métrique principale*
```
TPR(a) = P(Ŷ=1 | A=a, Y=1)
EOD = max(TPR) − min(TPR)
Seuil d'alerte : > 0.10
```
Vue individuelle : *parmi les candidats **vraiment** qualifiés, le modèle les détecte-t-il aussi bien dans tous les groupes ?* C'est l'**Equal Opportunity** de Hardt et al. (2016), recommandé pour les tâches où les base rates diffèrent légitimement entre groupes.

### Pourquoi l'EOD prime ici

Les base rates de qualification diffèrent entre cohortes d'âge (les candidats seniors ont davantage d'expérience — c'est réel, pas un biais). La DP brute condamnerait le modèle pour avoir simplement reflété cette réalité. L'EOD isole le biais du modèle des qualifications réelles — c'est notre métrique principale, les autres servent de complément descriptif.

```
Arbre de décision :
1. Les base rates diffèrent-ils entre groupes ?
   → Oui → EOD obligatoire, DP complémentaire
   → Non → DP suffirait

2. DP diff élevé + EOD faible
   → différence reflète les qualifications réelles, pas un biais

3. DP diff faible + EOD élevé
   → biais caché : à qualification égale, un groupe est moins bien détecté
```

---

## Détection des proxies

Avant de corriger, on identifie **quelles features ML leakent de l'information démographique**. Deux méthodes complémentaires.

### Méthode 1 — Mutual Information (MI)

La MI mesure la dépendance statistique entre chaque feature ML et chaque attribut sensible inféré. **MI > 0.05 = signal démographique significatif.**

#### Genre

| Feature | MI | Statut |
|---|---|---|
| `num_certifications` | 0.0550 | ⚠️ Flagged |
| `max_language_score` | 0.0325 | OK |
| `experience_x_seniority` | 0.0266 | OK |
| `total_years_experience` | 0.0242 | OK |

→ Une seule feature flaggée. Le genre est le moins problématique des trois attributs.

#### Cohorte d'âge

| Feature | MI | Statut |
|---|---|---|
| `total_years_experience` | 0.4716 | ⚠️ Flagged |
| `experience_education_ratio` | 0.4526 | ⚠️ Flagged |
| `experience_x_education` | 0.4446 | ⚠️ Flagged |
| `experience_x_seniority` | 0.3525 | ⚠️ Flagged |
| `has_senior_title` | 0.3107 | ⚠️ Flagged |
| `certs_per_year` | 0.2265 | ⚠️ Flagged |
| `num_positions` | 0.2009 | ⚠️ Flagged |
| `avg_tenure_months` | 0.1953 | ⚠️ Flagged |
| `career_gap_months` | 0.1689 | ⚠️ Flagged |
| `latest_job_duration` | 0.1093 | ⚠️ Flagged |

→ 10 features flaggées avec MI très élevé. C'est attendu : l'expérience professionnelle est mécaniquement corrélée à l'âge. **Ce n'est pas nécessairement un biais** — un candidat senior a objectivement plus d'expérience. La question est : le modèle pénalise-t-il les jeunes *à qualification égale* ?

#### Multilinguisme

| Feature | MI | Statut |
|---|---|---|
| `language_count` | 0.3758 | ⚠️ Flagged |
| `max_language_score` | 0.0328 | OK |

→ `language_count` est un proxy quasi-parfait de `is_multilingual` (par construction — c'est de cette feature qu'on infère le proxy). À surveiller.

### Méthode 2 — Adversarial Probe

Un Random Forest est entraîné sur les features ML uniquement pour prédire chaque attribut sensible. **AUC > 0.65 = proxy exploitable.**

| Attribut | AUC adversariale | Conclusion |
|---|---|---|
| `gender` | 0.493 ± 0.021 | ✅ OK — non prédictible depuis les features |
| `age_cohort` | 0.802 ± 0.019 | ⚠️ **PROXY BIAS CONFIRMÉ** |
| `is_multilingual` | 1.000 ± 0.000 | ⚠️ **PROXY BIAS CONFIRMÉ** |

**Interprétation :**
- Le genre n'est pas reconstituable depuis les features ML (AUC ≈ 0.5 = aléatoire) — faible risque.
- L'âge est fortement prédictible (AUC = 0.80) — le modèle peut reconstruire la cohorte sans jamais voir l'âge directement. **Mitigation requise.**
- Le multilinguisme est prédictible à 100% (AUC = 1.00) — `language_count` est un proxy parfait. **Mitigation requise.**

> Ces résultats justifient l'application d'une stratégie corrective. Un modèle capable de reconstruire un attribut protégé depuis ses features peut discriminer indirectement même sans l'utiliser explicitement.

---

## Analyse par attribut

Métriques calculées sur le **test set out-of-sample**.

### Genre

| Groupe | Selection rate | TPR |
|---|---|---|
| female | 32% | 67% |
| male | 36% | 64% |

- **EOD (baseline) : 0.03** ✅ — en dessous du seuil de 0.10
- **DP diff (baseline) : 0.04** ✅

→ Le genre présente peu de biais mesurable. Les 3–4 points d'écart sont dans la marge d'erreur du petit échantillon (IC bootstrap large).

### Cohorte d'âge — le cas le plus préoccupant

| Groupe | Selection rate | TPR |
|---|---|---|
| 22–28 | 4% | 0% |
| 29–32 | 19% | 67% |
| 33–36 | 55% | 69% |
| 37–44 | 67% | 100% |

- **EOD (baseline) : 1.00** ❌ — maximum théorique, inacceptable légalement
- **DP diff (baseline) : 0.63** ❌

→ Le modèle ne détecte **aucun candidat Junior qualifié** (TPR = 0%). Même sur un petit échantillon, c'est un signal alarmant. L'écart s'explique mécaniquement : les features d'expérience (MI élevé avec `age_cohort`) pilotent fortement la décision, et les candidats jeunes ont objectivement moins d'expérience.

**Distinction cruciale :** une partie de cet écart est légitime (un poste senior demande de l'expérience) et une partie est un biais (un candidat junior *qualifié* est moins bien détecté qu'un senior *qualifié*). L'EOD mesure uniquement la seconde partie — c'est pourquoi il est notre métrique principale.

### Multilinguisme

| Groupe | Selection rate | TPR |
|---|---|---|
| monolingual | 29% | 100% |
| multilingual | 35% | 61% |

- **EOD (baseline) : 0.39** ❌ — au-dessus du seuil
- **DP diff (baseline) : 0.06** ✅

→ Paradoxe : les monolingues ont un TPR de 100% mais un selection rate plus bas. Cela suggère que les candidats monolingues qui sont qualifiés sont bien détectés, mais qu'il y en a peu au total. Les multilingues sont plus nombreux à candidater mais moins bien détectés à qualification égale. À surveiller sur un dataset plus large.

---

## Stratégie corrective retenue

### AIF360 Sample Re-weighting (pré-processing) — RETENU

**Principe :** au lieu de supprimer des features ou d'appliquer des seuils différents par groupe, on **rééquilibre le poids des exemples d'entraînement** de sorte que chaque groupe démographique contribue équitablement à l'apprentissage du modèle.

```python
# train_fair.py
from aif360.algorithms.preprocessing import Reweighing

RW = Reweighing(
    unprivileged_groups=[{'age_cohort': 0, 'is_multilingual': 0}],
    privileged_groups=[{'age_cohort': 2, 'is_multilingual': 1}]
)
dataset_transf = RW.fit_transform(dataset)
# → les candidats juniors monolingues qualifiés reçoivent un poids plus élevé
```

**Pourquoi cette approche :**

| Alternative | Raison du rejet |
|---|---|
| **Suppression de features** (ex. retirer `total_years_experience`) | Dégraderait massivement les performances — l'expérience est la feature la plus prédictive légitime |
| **Seuils différenciés par groupe** (post-processing) | Demographic norming illégal sous la Directive 2000/78/CE et l'AI Act Art. 10 — appliquer un standard différent selon l'âge est une discrimination directe |
| **Adversarial debiasing** | Plus complexe, moins interprétable, difficile à auditer — contraire au principe de transparence |

Le re-weighting est la stratégie de pré-processing la plus défendable car :
1. Le modèle final ne distingue jamais les candidats selon leur groupe à l'inférence.
2. Il est transparent : on peut expliquer à LuxTalent exactement comment les poids ont été ajustés.
3. Il préserve toutes les features légitimes — l'expérience reste un critère, mais son influence est rééquilibrée.

**Features surveillées comme proxies principaux :**
- `age_cohort` : `total_years_experience` (MI = 0.472), `experience_education_ratio` (MI = 0.453)
- `is_multilingual` : `language_count` (MI = 0.376)

> ⚠ Ces features ne sont **pas supprimées** du modèle — elles sont trop prédictives pour être retirées sans coût majeur. Le re-weighting atténue leur influence biaisée sans les éliminer.

---

## Comparaison baseline vs Fair Model v2

Comparaison sur le **même test set** (rigueur méthodologique).

### Performances brutes

| Métrique | Baseline | Fair Model v2 | Δ |
|---|---|---|---|
| **ROC-AUC** | 0.736 | 0.718 | −0.018 |
| Accuracy | — | — | — |
| F1 | 0.500 | — | — |

Perte de ~2 points de ROC-AUC. C'est le **trade-off équité/performance assumé**. Un système plus équitable est légèrement moins précis — c'est un résultat classique dans la littérature fairness (Hardt et al. 2016).

### Métriques d'équité — avant vs après

| Attribut | Métrique | Baseline | Fair v2 | Δ |
|---|---|---|---|---|
| **Gender** | EOD | 0.03 | ~0.03 | ≈ 0 |
| **Gender** | DP diff | 0.04 | ~0.04 | ≈ 0 |
| **Age cohort** | EOD | 1.00 | 0.67 | **−0.33** ✅ |
| **Age cohort** | DP diff | 0.63 | ~0.55 | −0.08 ✅ |
| **Multilingual** | EOD | 0.39 | ~0.30 | −0.09 ✅ |
| **Multilingual** | DP diff | 0.06 | ~0.06 | ≈ 0 |

> Valeurs Fair v2 estimées sur le test set. Les IC bootstrap sont larges sur ce dataset (n=100 test, ~20 positifs) — les valeurs sont indicatives.

### Effets de bord et limites honnêtes

**1. L'EOD âge reste élevé après correction (0.67).**
Le re-weighting réduit significativement le biais âge (−0.33 points) mais ne l'élimine pas. La corrélation mécanique expérience/âge est structurelle — un candidat de 24 ans aura toujours moins d'expérience qu'un candidat de 40 ans, et cette différence est en partie légitime. Sur un dataset plus grand, le rééquilibrage serait plus efficace.

**2. IC bootstrap larges.**
Avec seulement ~20 candidats positifs dans le test set, les métriques par sous-groupe sont bruitées. Un EOD de 1.00 calculé sur 2 Juniors qualifiés a une marge d'erreur bien plus grande qu'un EOD calculé sur 200. Les conclusions restent valides dans leur direction, mais les valeurs exactes sont à traiter avec prudence.

**3. Dataset synthétique.**
Le dataset d'entraînement (500 candidats) est généré synthétiquement à des fins pédagogiques. Sur de vraies données recrutement, les distributions démographiques et les base rates seraient différents — l'audit devra être refait sur les données réelles en production.

---

## Explicabilité des décisions

L'AI Act (Art. 13, 14) et le RGPD (Art. 22) exigent que les décisions automatisées soient explicables à deux niveaux : globalement (pour LuxTalent) et individuellement (pour chaque candidat).

### Niveau global — importance des features (SHAP)

Le système utilise `shap.LinearExplainer` sur le modèle logistique pour calculer les valeurs SHAP de chaque feature. Ces valeurs indiquent **quel impact réel** chaque feature a sur les décisions du modèle, en tenant compte de la distribution des données.

Features les plus influentes (modèle Fair v2) :
- `experience_x_education` — interaction expérience × niveau d'études
- `total_years_experience` — années d'expérience totales
- `experience_education_ratio` — ratio expérience / formation

### Niveau individuel — "Why this decision"

Pour chaque candidat, le panneau détail de l'interface affiche les **3 contributions positives** et **3 contributions négatives** qui ont le plus pesé dans la décision.

Exemple — candidat refusé :
```
+ Experience × education    +1.129  (bon ratio exp/formation)
+ Years of experience       +1.088  (expérience suffisante)
- Education level           −0.366  (diplôme insuffisant pour le poste)
- Number of certifications  −0.067  (peu de certifications)
```

Le recruteur peut ainsi :
1. Comprendre la décision (Art. 14 AI Act).
2. Contester si une feature clé est manifestement erronée (RGPD Art. 22).
3. Appliquer un override humain si le contexte le justifie — l'action est tracée dans `processing_log`.

### Human Override — Art. 14 AI Act

Chaque décision AI peut être **annulée par un recruteur humain** via l'interface. L'override inclut :
- La nouvelle décision (Invite / Reject)
- La raison obligatoire (champ texte)
- Un timestamp et un log immuable dans `processing_log`

Cette traçabilité garantit que LuxTalent peut démontrer, en cas de contestation, que l'humain garde bien le contrôle final de chaque décision de recrutement.

---

## Conclusion & recommandations

### Résultats clés

| Attribut | EOD baseline | EOD Fair v2 | Résultat |
|---|---|---|---|
| Genre | 0.03 | ~0.03 | ✅ Acceptable |
| Âge | **1.00** | **0.67** | ⚠️ Amélioré, à surveiller |
| Multilinguisme | 0.39 | ~0.30 | ⚠️ Amélioré, à surveiller |
| **ROC-AUC** | 0.736 | 0.718 | −0.018 (trade-off assumé) |

### Réponses au cahier des charges WP2

1. *Le système traite-t-il les candidats comparables de manière égale ?* — **Non pour l'âge** sur le baseline (EOD = 1.00). Partiellement corrigé sur Fair v2 (0.67). Le genre est acceptable.
2. *Y a-t-il des disparités mesurables ?* — Oui sur l'âge (EOD = 1.00) et le multilinguisme (EOD = 0.39). Le genre est en dessous du seuil d'alerte.
3. *Sont-elles justifiées par le poste ?* — Partiellement pour l'âge (l'expérience est un critère légitime). L'écart de TPR entre Juniors et Seniors qualifiés n'est *pas* entièrement justifiable — c'est un vrai biais résiduel.
4. *Le modèle peut-il être amélioré ?* — Oui : EOD Âge réduit de 33 points avec Fair v2, au prix de 1.8 points de ROC-AUC. Un dataset plus grand permettrait une mitigation plus efficace.
5. *Les décisions peuvent-elles être rendues plus transparentes ?* — Oui, via SHAP individuel dans l'interface et human override tracé (Art. 14 AI Act).

### Limites assumées

- **Dataset de 500 candidats synthétiques** → IC bootstrap larges, certaines métriques par sous-groupe peu fiables sur petit n.
- **Attributs sensibles inférés** (pas directs) → précision des proxies imparfaite (~85% pour le genre).
- **Le Fair Model v2 n'est pas un modèle entièrement équitable** — il réduit le biais sur l'âge et le multilinguisme, mais l'EOD âge reste à 0.67. C'est un premier cycle de correction, pas un état final.
- **Corrélation mécanique expérience/âge** : impossible à éliminer complètement sans retirer des features hautement prédictives. Le re-weighting est le meilleur compromis disponible.

### Recommandations pour LuxTalent

1. **Audit annuel** avec un test set d'au moins 500 candidats pour réduire les IC bootstrap et obtenir des métriques plus fiables par sous-groupe.
2. **Collecter des données démographiques anonymisées** (avec consentement) pour mesurer les vrais attributs protégés plutôt que des proxies.
3. **Documenter les décisions contestées** — le processlog `hr_override` y contribue, mais une procédure formelle de contestation doit être établie (RGPD Art. 22).
4. **Former les recruteurs** à la lecture des explications SHAP individuelles et aux biais algorithmiques.
5. **Valider le seuil de décision** avec la direction : le seuil par défaut (0.5) est configurable. Un client orienté inclusion (ne pas rater de talents) demanderait un seuil plus bas ; un client orienté précision (moins d'entretiens inutiles) demanderait un seuil plus haut. Ce n'est pas un choix purement technique.
6. **Second cycle d'audit** dès qu'un dataset réel est disponible — les données synthétiques sont un proxy pédagogique acceptable, pas un substitut à un audit sur données réelles.

---

## Glossaire

| Terme | Définition |
|---|---|
| **AIF360** | AI Fairness 360 — bibliothèque IBM d'algorithmes de mitigation des biais (Reweighing, Adversarial Debiasing, etc.) |
| **Adversarial Probe** | Modèle (ici Random Forest) entraîné à prédire un attribut sensible depuis les features ML. AUC > 0.65 = proxy exploitable. |
| **Bootstrap** | Méthode de ré-échantillonnage (tirage avec remise) pour estimer la marge d'erreur d'une métrique sans hypothèse distributionnelle. |
| **Base rate** | Taux réel de candidats qualifiés (`Y=1`) dans un groupe. À distinguer du selection rate (décision du modèle). |
| **Demographic norming** | Appliquer un standard d'évaluation différent selon un attribut protégé. Illégal sous la Directive 2000/78/CE. |
| **DP diff** | Demographic Parity Difference : écart max−min des selection rates entre groupes. Seuil d'alerte : > 0.10. |
| **EOD** | Equal Opportunity Difference : écart max−min des TPR entre groupes à `Y=1`. Métrique principale de cet audit. |
| **Equal Opportunity** | À qualification égale, tous les groupes ont la même probabilité d'être détectés correctement. |
| **Mutual Information** | Mesure de dépendance statistique entre deux variables. MI > 0.05 = signal démographique significatif. |
| **Out-of-sample** | Évaluation sur des données jamais vues à l'entraînement. Garantit la fiabilité des métriques. |
| **Proxy** | Feature qui révèle indirectement un attribut protégé (ex. `language_count` → multilinguisme → origine). |
| **Re-weighting** | Stratégie pré-processing : ajuster les poids des exemples d'entraînement pour que chaque groupe contribue équitablement à l'apprentissage. |
| **SHAP** | SHapley Additive Explanations — méthode d'explicabilité fondée sur la théorie des jeux coopératifs. |
| **TPR** | True Positive Rate (Rappel) : parmi les `Y=1`, fraction correctement prédite positive. Composante de l'EOD. |
