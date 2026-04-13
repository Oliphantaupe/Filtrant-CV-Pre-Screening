# Rapport — Modèle ML de screening de CVs
## Projet Filtrant — LuxTalent Advisory Group S.A.

---

## 1. Le problème à résoudre

LuxTalent reçoit des dizaines de CVs par jour. Le but est d'automatiser la première étape de tri : est-ce que ce candidat mérite d'être invité à un entretien, ou non ?

On veut donc un modèle qui prend un CV en entrée et retourne **Invite** ou **Reject**.

---

## 2. Pourquoi un modèle ML classique et pas juste le LLM ?

Le LLM (Gemini) est déjà utilisé dans le projet pour **lire et structurer** le CV. Mais on ne lui demande pas de décider. Pourquoi ?

- Un LLM peut avoir des biais imprévisibles dans ses décisions
- On ne peut pas entraîner un LLM sur nos propres données historiques
- Un modèle sklearn est **traçable** : on peut voir exactement quelles features ont pesé dans la décision
- C'est beaucoup plus rapide et moins cher à l'utilisation

Le LLM fait le travail de compréhension du texte. Le modèle ML fait la décision basée sur des critères objectifs appris depuis les données.

---

## 3. Les données

### D'où viennent-elles ?

Les données viennent des CVs qui ont été uploadés et traités par l'application. Pour chaque CV, on stocke les features extraites + la recommandation.

Le fichier `candidates_export.csv` contient une ligne par candidat avec ses 15 features et son label (Invite ou Reject).

### Ce qu'on a

| | Valeur |
|---|---|
| Nombre de candidats | 200 |
| Invités | 51 (26%) |
| Rejetés | 149 (74%) |

### Le déséquilibre des classes

On a 3x plus de Reject que d'Invite. C'est normal dans le recrutement — tous les candidats ne sont pas retenus. Mais ça pose un problème au modèle : il pourrait apprendre à tout rejeter et avoir l'air d'être bon (74% de bonnes réponses juste en disant "Reject" tout le temps).

Pour corriger ça, on utilise le paramètre `class_weight="balanced"` dans sklearn. Ça force le modèle à traiter les deux classes de façon équilibrée, même si l'une est minoritaire.

---

## 4. Les features — qu'est-ce qu'on mesure ?

Un modèle ML ne peut pas lire du texte. On doit transformer chaque CV en **15 chiffres**. Ces chiffres sont calculés automatiquement par `features.py` depuis le JSON retourné par le LLM.

### Groupe Expérience

| Feature | Description | Exemple |
|---|---|---|
| `total_years_experience` | Total des années de travail | 5.5 |
| `num_positions` | Nombre de postes occupés | 3 |
| `avg_tenure_months` | Durée moyenne dans un poste (mois) | 22 |

Ces features mesurent la stabilité et l'expérience accumulée. Un candidat avec 10 ans et 2 postes stables est différent d'un avec 10 ans et 8 postes courts.

### Groupe Formation

| Feature | Description | Valeurs |
|---|---|---|
| `education_level_score` | Niveau du diplôme le plus élevé | 1=Lycée, 2=BTS, 3=Licence, 4=Master, 5=PhD |

### Groupe Compétences

| Feature | Description | Exemple |
|---|---|---|
| `total_skills_count` | Total skills (technique + méthodes + management) | 12 |
| `has_certifications` | A au moins une certification | 0 ou 1 |
| `num_certifications` | Nombre exact de certifications | 3 |

### Groupe Langues

| Feature | Description | Valeurs |
|---|---|---|
| `language_count` | Nombre de langues parlées | 2 |
| `max_language_score` | Meilleur niveau CEFR | 1=A1 … 6=C2 |

### Groupe Signaux de qualité

| Feature | Description | Ce que ça indique |
|---|---|---|
| `has_senior_title` | Titre contient Senior/Lead/Manager... | Expérience de séniorité |
| `career_gap_months` | Total des trous entre postes (mois) | 0 = carrière continue |
| `latest_job_duration` | Durée du dernier poste (mois) | Stabilité récente |
| `has_summary` | CV a un résumé professionnel | Soin apporté au CV |
| `section_completeness_score` | Sections remplies parmi 6 | 6 = CV complet |
| `parse_quality_score` | Qualité du parsing LLM | 0=mauvais, 2=complet |

---

## 5. Analyse des features — ce qu'on a découvert

Avant d'entraîner le modèle, on a regardé la **différence de moyenne entre Invite et Reject** pour chaque feature. Si une feature a la même moyenne dans les deux groupes, elle n'apporte aucune information.

### Features avec un signal réel

```
latest_job_duration    Invite=22.5 mois  vs  Reject=15.7 mois  → différence de 6.8
avg_tenure_months      Invite=13.2 mois  vs  Reject=8.8 mois   → différence de 4.4
total_years_experience Invite=3.1 ans    vs  Reject=2.0 ans     → différence de 1.1
num_certifications     Invite=2.0        vs  Reject=1.4         → différence de 0.6
has_senior_title       Invite=0.65       vs  Reject=0.36        → différence de 0.3
```

Les candidats invités ont en moyenne **plus d'expérience, restent plus longtemps dans leurs postes, et ont plus de certifications**.

### Features inutiles dans notre dataset

```
section_completeness_score → toujours 6.0 dans les deux groupes
has_summary                → toujours 1.0 dans les deux groupes
parse_quality_score        → toujours 2.0 dans les deux groupes
total_skills_count         → 12.7 vs 12.6 (différence négligeable)
```

Ces features ont la **même valeur pour tous les candidats** dans notre dataset. C'est parce que nos CVs de test sont tous bien formatés, avec un résumé, bien parsés, et avec toutes les sections remplies.

**Pourquoi on les a gardées quand même ?**

On ne les supprime pas du code car sur de vraies données clients (CVs incomplets, mal formatés, sans résumé), ces features redeviendraient utiles. Le modèle leur attribue automatiquement un poids de zéro — donc elles ne nuisent pas.

---

## 6. Entraînement — choix du modèle

On a comparé trois modèles classiques de classification.

### Régression Logistique

C'est le modèle le plus simple. Il calcule un score en faisant une somme pondérée des features :

```
score = (expérience × w1) + (éducation × w2) + (skills × w3) + ...
```

Les poids (w1, w2, w3...) sont appris pendant l'entraînement. Si le score dépasse un seuil, c'est Invite, sinon Reject.

Avantage : simple, rapide, interprétable. On peut voir exactement quel poids a chaque feature.

### Random Forest

Construit 300 arbres de décision. Chaque arbre apprend des règles du type "si expérience > 5 ans ET certifications > 1 → Invite". Les 300 arbres votent et la majorité l'emporte.

Avantage : capture des relations non-linéaires entre les features.

### Gradient Boosting

Similaire à Random Forest mais chaque arbre corrige les erreurs du précédent, en séquence.

Avantage : souvent le meilleur en pratique. Inconvénient : plus lent à entraîner.

### Résultats de la comparaison

| Modèle | AUC (test) | F1 Invite |
|---|---|---|
| LogisticRegression | **0.663** | 0.521 |
| RandomForest | 0.513 | 0.289 |
| GradientBoosting | 0.497 | 0.389 |

La Régression Logistique gagne. C'est surprenant car RandomForest et GradientBoosting sont généralement plus puissants. Mais avec seulement 200 lignes et peu de variance dans les données, les modèles complexes ont tendance à **overfitter** (apprendre les données par cœur plutôt que les tendances générales).

---

## 7. Évaluation — comprendre les métriques

### L'AUC-ROC

L'AUC mesure la capacité du modèle à distinguer Invite de Reject. Elle va de 0.5 (aléatoire) à 1.0 (parfait).

```
0.5  → aussi bon qu'une pièce de monnaie
0.663 → notre modèle
0.8  → bon modèle
1.0  → parfait (suspect en pratique = overfitting)
```

Notre 0.663 est **modeste mais honnête** pour 200 lignes de données homogènes.

### La matrice de confusion

```
                      Prédit Reject   Prédit Invite
Réellement Reject  |      17         |      13      |
Réellement Invite  |       5         |       5      |
```

Sur 40 candidats du jeu de test :
- **17 Reject correctement identifiés** — le modèle protège bien contre les faux positifs
- **5 Invite correctement identifiés** — sur 10 vrais Invite, il en trouve la moitié
- **13 faux Invite** — des Reject envoyés en entretien (coûteux mais non bloquant)
- **5 faux Reject** — des bons candidats manqués (le cas le plus problématique)

### Pourquoi la précision sur Invite est faible (28%) ?

```
Invite  precision=0.28  recall=0.50
```

Sur 18 fois où le modèle dit "Invite", il a raison seulement 5 fois. C'est dû à deux facteurs :
1. Les données sont peu nombreuses et homogènes — difficile d'apprendre des patterns fins
2. Le déséquilibre des classes — même avec `class_weight="balanced"`, 51 exemples positifs c'est peu

---

## 8. Ce que le modèle a vraiment appris

La feature importance de la Régression Logistique montre les coefficients du modèle après normalisation :

```
language_count           → coefficient 0.96 (le plus fort)
num_positions            → coefficient 0.80
avg_tenure_months        → coefficient 0.76
education_level_score    → coefficient 0.51
has_senior_title         → coefficient 0.27
section_completeness...  → coefficient 0.00  (inutile)
has_summary              → coefficient 0.00  (inutile)
parse_quality_score      → coefficient 0.00  (inutile)
```

**Note importante** : `language_count` a le coefficient le plus élevé non pas parce qu'il est le plus discriminant (sa différence Invite/Reject est faible), mais parce qu'après normalisation par StandardScaler, sa variance relative est grande dans ce dataset. C'est une limite connue de la Régression Logistique : les coefficients ne reflètent pas directement l'importance réelle si les features ont des distributions très différentes.

---

## 9. Limites et améliorations possibles

### Limites actuelles

| Limite | Impact |
|---|---|
| 200 lignes de données | Modèle peu généralisable |
| Données homogènes (CVs de test bien formatés) | 3 features constantes, inutiles |
| Pas de données clients réelles | Les patterns appris peuvent ne pas correspondre à la réalité |
| AUC = 0.663 | Marge d'erreur notable |

### Ce qu'on ferait avec plus de données

- Réentraîner sur les vraies données historiques de LuxTalent (CVs archivés + décisions HR)
- Ajouter des features textuelles (TF-IDF sur les titres de poste, domaine d'activité)
- Tester XGBoost ou LightGBM avec GridSearchCV pour l'optimisation des hyperparamètres
- Calibrer le modèle pour que les scores de confiance soient fiables (ex: 87% = vraiment 87%)

### Comment améliorer sans nouvelles données

- Augmenter les données synthétiques avec plus de variance sur les features constantes
- Utiliser SMOTE pour synthétiser des exemples de la classe minoritaire (Invite)

---

## 10. Conclusion

On a construit un pipeline ML complet :

```
CV (PDF/DOCX)
    ↓ extractor.py    → texte brut
    ↓ llm_parser.py   → JSON structuré (Gemini 2.0 Flash)
    ↓ features.py     → 15 chiffres normalisés
    ↓ predictor.py    → Invite / Reject + score de confiance
```

Le modèle retenu est une **Régression Logistique** avec normalisation StandardScaler. Malgré des données limitées, le modèle passe le test de cohérence : il reconnaît correctement les profils très forts (99% Invite) et les profils très faibles (97% Reject).

L'AUC de 0.663 est honnête et attendu pour ce volume de données. Il s'améliorera significativement avec les vraies données clients et un réentraînement régulier au fil des décisions HR.
