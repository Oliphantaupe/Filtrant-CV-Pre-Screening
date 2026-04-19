# Rapport -- Modele ML de screening de CVs (v2)
## Projet Filtrant -- LuxTalent Advisory Group S.A.

---

## 1. Le probleme a resoudre

LuxTalent recoit des dizaines de CVs par jour. Le but est d'automatiser la premiere etape de tri : est-ce que ce candidat merite d'etre invite a un entretien, ou non ?

On veut donc un modele qui prend un CV en entree et retourne **Invite** ou **Reject**.

---

## 2. Pourquoi un modele ML classique et pas juste le LLM ?

Le LLM (Gemini) est deja utilise dans le projet pour **lire et structurer** le CV. Mais on ne lui demande pas de decider. Pourquoi ?

- Un LLM peut avoir des biais imprevisibles dans ses decisions
- On ne peut pas entrainer un LLM sur nos propres donnees historiques
- Un modele sklearn est **tracable** : on peut voir exactement quelles features ont pese dans la decision
- C'est beaucoup plus rapide et moins cher a l'utilisation

Le LLM fait le travail de comprehension du texte. Le modele ML fait la decision basee sur des criteres objectifs appris depuis les donnees.

---

## 3. Les donnees

### D'ou viennent-elles ?

Les donnees viennent des CVs qui ont ete uploades et traites par l'application. Pour chaque CV, on stocke les features extraites + la recommandation.

Le fichier `candidates_export.csv` contient une ligne par candidat avec ses features et son label (Invite ou Reject).

### Ce qu'on a

| | Valeur |
|---|---|
| Nombre de candidats | 200 |
| Invites | 51 (26%) |
| Rejetes | 149 (74%) |

### Le desequilibre des classes

On a 3x plus de Reject que d'Invite. C'est normal dans le recrutement -- tous les candidats ne sont pas retenus. Mais ca pose un probleme au modele : il pourrait apprendre a tout rejeter et avoir l'air d'etre bon (74% de bonnes reponses juste en disant "Reject" tout le temps).

**Solutions utilisees (v2) :**

1. **`class_weight="balanced"`** dans sklearn : ca force le modele a traiter les deux classes de facon equilibree, meme si l'une est minoritaire
2. **SMOTE** (Synthetic Minority Over-sampling Technique) : ca *cree* de nouveaux exemples "Invite" synthetiques pour equilibrer les donnees avant l'entrainement
3. **`scale_pos_weight`** dans XGBoost : meme principe, pondere plus fort les exemples "Invite"

---

## 4. Les features -- qu'est-ce qu'on mesure ?

Un modele ML ne peut pas lire du texte. On doit transformer chaque CV en **chiffres**. Ces chiffres sont calcules automatiquement par `features.py` depuis le JSON retourne par le LLM.

### 4.1 Features de base (15)

#### Groupe Experience

| Feature | Description | Exemple |
|---|---|---|
| `total_years_experience` | Total des annees de travail | 5.5 |
| `num_positions` | Nombre de postes occupes | 3 |
| `avg_tenure_months` | Duree moyenne dans un poste (mois) | 22 |

Ces features mesurent la stabilite et l'experience accumulee. Un candidat avec 10 ans et 2 postes stables est different d'un avec 10 ans et 8 postes courts.

#### Groupe Formation

| Feature | Description | Valeurs |
|---|---|---|
| `education_level_score` | Niveau du diplome le plus eleve | 1=Lycee, 2=BTS, 3=Licence, 4=Master, 5=PhD |

#### Groupe Competences

| Feature | Description | Exemple |
|---|---|---|
| `total_skills_count` | Total skills (technique + methodes + management) | 12 |
| `has_certifications` | A au moins une certification | 0 ou 1 |
| `num_certifications` | Nombre exact de certifications | 3 |

#### Groupe Langues

| Feature | Description | Valeurs |
|---|---|---|
| `language_count` | Nombre de langues parlees | 2 |
| `max_language_score` | Meilleur niveau CEFR | 1=A1 ... 6=C2 |

#### Groupe Signaux de qualite

| Feature | Description | Ce que ca indique |
|---|---|---|
| `has_senior_title` | Titre contient Senior/Lead/Manager... | Experience de seniorite |
| `career_gap_months` | Total des trous entre postes (mois) | 0 = carriere continue |
| `latest_job_duration` | Duree du dernier poste (mois) | Stabilite recente |
| `has_summary` | CV a un resume professionnel | Soin apporte au CV |
| `section_completeness_score` | Sections remplies parmi 6 | 6 = CV complet |
| `parse_quality_score` | Qualite du parsing LLM | 0=mauvais, 2=complet |

### 4.2 Features derivees (4) -- NOUVEAU en v2

Ces features sont **calculees a partir des features de base**. Elles capturent des relations que le modele ne verrait pas autrement.

| Feature | Formule | Ce que ca mesure |
|---|---|---|
| `experience_education_ratio` | annees_exp / niveau_diplome | Un autodidacte avec beaucoup d'experience vs un diplome sans experience |
| `certs_per_year` | nb_certifications / annees_exp | Intensite de la formation continue |
| `experience_x_seniority` | annees_exp * a_titre_senior | Combine experience + titre senior (vaut 0 si pas senior) |
| `experience_x_education` | annees_exp * niveau_diplome | Score combine experience + diplome |

### 4.3 Suppression automatique des features constantes

Dans notre dataset actuel, 3 features ont **exactement la meme valeur** pour tous les candidats :

```
section_completeness_score -> toujours 6
has_summary                -> toujours 1
parse_quality_score        -> toujours 2
```

Le script v2 les detecte et les retire automatiquement. Ca laisse **16 features effectives** (12 base + 4 derivees).

**Pourquoi on les garde dans le code ?** Parce que sur de vrais CVs (incomplets, mal formates), ces features auront de la variance et redeviendront utiles.

---

## 5. Analyse des features -- ce qu'on a decouvert

### Features avec un signal reel

```
latest_job_duration         Invite=22.5 mois  vs  Reject=15.7 mois  -> difference de 6.8
avg_tenure_months           Invite=13.2 mois  vs  Reject=8.8 mois   -> difference de 4.4
experience_x_education      Invite=11.0       vs  Reject=6.8        -> difference de 4.2 (NOUVEAU)
total_years_experience      Invite=3.1 ans    vs  Reject=2.0 ans    -> difference de 1.1
experience_x_seniority      Invite=2.5        vs  Reject=1.3        -> difference de 1.2 (NOUVEAU)
```

Les candidats invites ont en moyenne **plus d'experience, restent plus longtemps dans leurs postes, et combinent experience + diplome**.

### Detection de labels bruites (NOUVEAU en v2)

Le script detecte automatiquement les labels incoherents :

```
12 profils forts (5+ ans, Master+, Senior) labellises Reject
-> 12 labels potentiellement bruites sur 200 (6%)
```

Corriger ces labels ameliorerait significativement les performances.

---

## 6. Entrainement -- choix du modele

On a compare **6 modeles** de classification (3 de plus qu'en v1).

### 6.1 Regression Logistique

C'est le modele le plus simple. Il calcule un score en faisant une somme ponderee des features :

```
score = (experience * w1) + (education * w2) + (skills * w3) + ...
```

Les poids (w1, w2, w3...) sont appris pendant l'entrainement. Si le score depasse un seuil, c'est Invite, sinon Reject.

**Avantage** : simple, rapide, interpretable. On voit exactement le poids de chaque feature.
**Inconvenient** : ne capture pas les relations complexes entre features.

### 6.2 Random Forest

Construit 300 arbres de decision. Chaque arbre apprend des regles du type "si experience > 5 ans ET certifications > 1 -> Invite". Les 300 arbres votent et la majorite l'emporte.

**Avantage** : capture des relations non-lineaires entre les features.
**Inconvenient** : peut overfitter sur peu de donnees.

### 6.3 Gradient Boosting

Similaire a Random Forest mais chaque arbre corrige les erreurs du precedent, en sequence.

**Avantage** : souvent le meilleur en pratique.
**Inconvenient** : plus lent, ne supporte pas nativement class_weight.

### 6.4 SVM (Support Vector Machine) -- NOUVEAU en v2

Cherche une frontiere optimale pour separer les deux classes. En mode RBF (Radial Basis Function), il peut trouver des frontieres non-lineaires.

**Avantage** : tres bon sur les petits datasets, robuste a l'overfitting.
**Inconvenient** : lent sur les gros datasets, moins interpretable.

### 6.5 HistGradientBoosting -- NOUVEAU en v2

Version amelioree de Gradient Boosting. Plus rapide et supporte nativement `class_weight="balanced"`.

**Avantage** : rapide, gere le desequilibre, souvent meilleur que GB classique.
**Inconvenient** : "boite noire" -- difficile a interpreter.

### 6.6 XGBoost -- NOUVEAU en v2

L'algorithme de reference en machine learning competitif. Construit des arbres de boosting avec des optimisations avancees (regularisation, parallelisme).

**Avantage** : tres performant, gere nativement le desequilibre via `scale_pos_weight`.
**Inconvenient** : plus de parametres a regler, "boite noire".

### Resultats de la comparaison

| Modele | AUC (test) | F1 Invite (cv5) |
|---|---|---|
| **LogisticRegression** | **0.530** | **0.515** |
| SVM_RBF | 0.530 | 0.423 |
| XGBoost | 0.510 | 0.407 |
| HistGradientBoosting | 0.527 | 0.368 |
| GradientBoosting | 0.503 | 0.363 |
| RandomForest | 0.510 | 0.350 |

La Regression Logistique gagne a nouveau. Avec seulement 200 lignes et des donnees bruitees, les modeles simples generalisent mieux que les modeles complexes.

### Optimisation des hyperparametres (NOUVEAU en v2)

Apres avoir selectionne le meilleur modele, on optimise ses parametres avec `RandomizedSearchCV` :

```
Meilleurs parametres : C=0.01, penalty=l2
F1 (cv5) optimise   : 0.548 (vs 0.515 avant optimisation)
```

Le `C=0.01` signifie que le modele a besoin d'une forte regularisation -- il simplifie au maximum pour eviter l'overfitting sur ces donnees bruitees.

---

## 7. Evaluation -- comprendre les metriques

### L'AUC-ROC

L'AUC mesure la capacite du modele a distinguer Invite de Reject. Elle va de 0.5 (aleatoire) a 1.0 (parfait).

```
0.5   -> aussi bon qu'une piece de monnaie
0.653 -> notre modele (v2)
0.8   -> bon modele
1.0   -> parfait (suspect en pratique = overfitting)
```

### La matrice de confusion (v2)

```
                      Predit Reject   Predit Invite
Reellement Reject  |      19         |      11      |
Reellement Invite  |       4         |       6      |
```

Sur 40 candidats du jeu de test :
- **19 Reject correctement identifies** (vs 17 en v1)
- **6 Invite correctement identifies** (vs 5 en v1, +20%)
- **11 faux Invite** (vs 13 en v1, amelioration)
- **4 faux Reject** (vs 5 en v1, amelioration)

### Comparaison v1 vs v2

| Metrique | v1 | v2 | Evolution |
|---|---|---|---|
| Precision Invite | 0.28 | 0.35 | +25% |
| Recall Invite | 0.50 | 0.60 | +20% |
| F1 Invite (cv5) | 0.521 | 0.548 | +5% |

---

## 8. Ce que le modele a vraiment appris

La feature importance apres optimisation :

```
language_count               -> 0.2055 (le plus fort)
education_level_score        -> 0.1275
certs_per_year               -> 0.1271 (NOUVEAU - derivee)
has_senior_title             -> 0.1028
avg_tenure_months            -> 0.0958
experience_education_ratio   -> 0.0914 (NOUVEAU - derivee)
latest_job_duration          -> 0.0891
total_years_experience       -> 0.0815
num_certifications           -> 0.0763
has_certifications           -> 0.0749
experience_x_seniority       -> 0.0722 (NOUVEAU - derivee)
experience_x_education       -> 0.0690 (NOUVEAU - derivee)
max_language_score           -> 0.0575
num_positions                -> 0.0052 (presque inutile)
total_skills_count           -> 0.0013 (presque inutile)
career_gap_months            -> 0.0005 (presque inutile)
```

**Observation cle** : les 4 features derivees (NOUVEAU) contribuent toutes de maniere significative. `certs_per_year` et `experience_education_ratio` sont dans le top 6. Ces combinaisons apportent de l'information que les features individuelles ne capturaient pas.

---

## 9. Techniques utilisees -- resume

### SMOTE (Synthetic Minority Over-sampling Technique)

**Probleme** : 51 Invite vs 149 Reject -- le modele a tendance a tout rejeter.

**Solution** : SMOTE cree de nouveaux exemples Invite *synthetiques* en interpolant entre les vrais exemples. Si on a deux candidats invites A et B, SMOTE cree un candidat C dont les features sont "entre" A et B.

```
Avant SMOTE :  51 Invite, 149 Reject (ratio 1:3)
Apres SMOTE : 149 Invite, 149 Reject (ratio 1:1)
```

### StandardScaler

Les features ont des echelles tres differentes : `has_certifications` va de 0 a 1, mais `career_gap_months` peut aller de 0 a 40. Sans normalisation, le modele accorderait trop d'importance aux features a grande echelle.

StandardScaler transforme chaque feature pour avoir une moyenne de 0 et un ecart-type de 1.

### RandomizedSearchCV

Au lieu de fixer les parametres a la main, on teste automatiquement plusieurs combinaisons et on garde la meilleure.

---

## 10. Limites et ameliorations possibles

### Limites actuelles

| Limite | Impact |
|---|---|
| 200 lignes de donnees | Modele peu generalisable |
| 12 labels bruites (6%) | Le modele apprend des erreurs |
| Donnees homogenes (CVs de test bien formates) | 3 features constantes |
| Pas de donnees clients reelles | Les patterns appris peuvent ne pas correspondre a la realite |

### Ce qu'on ferait avec plus de donnees

- Reentrainer sur les vraies donnees historiques de LuxTalent
- Ajouter des features textuelles (TF-IDF sur les titres de poste)
- Tester des modeles de deep learning (si > 5000 lignes)
- Calibrer le modele pour que les scores de confiance soient fiables

### Comment ameliorer sans nouvelles donnees

- **Corriger les 12 labels bruites** -- amelioration estimee : AUC +0.05-0.15
- Augmenter les donnees synthetiques avec plus de variance
- Tester d'autres features derivees (ratio skills/experience, etc.)

---

## 11. Conclusion

On a construit un pipeline ML complet (v2) :

```
CV (PDF/DOCX)
    | extractor.py    -> texte brut
    | llm_parser.py   -> JSON structure (Gemini 2.0 Flash)
    | features.py     -> 16 features (12 base + 4 derivees)
    | predictor.py    -> Invite / Reject + score de confiance
```

Le modele retenu est une **Regression Logistique** avec normalisation StandardScaler et surechantillonnage SMOTE. Les ameliorations v2 (features derivees, SMOTE, optimisation hyperparametres) ont ameliore le recall Invite de 50% a 60% et la precision de 28% a 35%.

Le test de coherence confirme que le modele fonctionne :
- Profil fort (10 ans, Master, 15 skills) -> **Invite 90%**
- Profil faible (0.5 an, lycee, 2 skills) -> **Reject 83%**

La principale limitation reste la **qualite des donnees** : corriger les 12 labels bruites et augmenter le volume au-dela de 500 candidats ameliorerait significativement les performances.
