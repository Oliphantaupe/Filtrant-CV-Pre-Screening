# Guide Complet -- Les Algorithmes ML du Projet Filtrant

## Introduction

Ce document explique **chaque algorithme et technique** utilise dans le projet Filtrant pour le screening automatique de CVs. L'objectif : que quelqu'un qui ne connait rien au ML puisse comprendre comment et pourquoi chaque piece du puzzle fonctionne.

---


## PARTIE 1 : Le Pipeline Global

### Comment un CV devient une decision ?

Imagine qu'un recruteur recoit un CV en PDF. Voici ce que le systeme fait, etape par etape :

```
1. Le CV arrive (PDF ou DOCX)
         |
2. extractor.py extrait le TEXTE brut du fichier
         |
3. llm_parser.py envoie le texte a Gemini (IA) qui le structure en JSON
         |
4. features.py transforme le JSON en 16 CHIFFRES
         |
5. predictor.py donne ces 16 chiffres au modele ML
         |
6. Le modele repond : "Invite" ou "Reject" + un score de confiance
```

**Le modele ML ne lit jamais le CV.** Il ne voit que 16 nombres. C'est Gemini (le LLM) qui fait le travail de comprehension du texte.

### Pourquoi 16 chiffres ?

Parce qu'un algorithme ML classique ne comprend pas les mots. Il ne sait travailler qu'avec des nombres. Donc on transforme chaque CV en une "fiche" de 16 mesures :

**Exemple concret :**

```
Marie Dupont, 7 ans d'experience, Master en informatique, 3 postes occupes,
parle 2 langues, a 4 certifications, titre "Senior Developer"

-> Ces infos deviennent :
   total_years_experience = 7.0
   num_positions = 3
   avg_tenure_months = 28.0
   education_level_score = 4 (Master)
   total_skills_count = 14
   has_certifications = 1
   language_count = 2
   max_language_score = 5 (C1)
   has_senior_title = 1
   career_gap_months = 5
   latest_job_duration = 36
   num_certifications = 4
   experience_education_ratio = 1.75 (7/4)
   certs_per_year = 0.57 (4/7)
   experience_x_seniority = 7.0 (7*1)
   experience_x_education = 28.0 (7*4)
```

Le modele regarde ces 16 nombres et decide : **Invite** (90% de confiance).

---

## PARTIE 2 : Les Algorithmes de Classification

Le but de ces algorithmes : apprendre a partir d'exemples passes (des CVs avec leur decision Invite/Reject) pour predire la decision sur de nouveaux CVs.

### 1. Regression Logistique

**C'est quoi en une phrase ?**
Un calcul qui fait la somme ponderee de toutes les features et dit "Invite" si le total est assez eleve.

**Comment ca marche (avec un exemple) ?**

Imagine que le modele a appris ces poids :

```
experience :     +2.0  (beaucoup d'experience = bon signe)
education :      +1.5  (diplome eleve = bon signe)
career_gap :     -0.5  (trous de carriere = mauvais signe)
skills :         +0.1  (peu d'impact)
```

Pour Marie (7 ans exp, Master, 5 mois de gap, 14 skills) :

```
Score = (7 * 2.0) + (4 * 1.5) + (5 * -0.5) + (14 * 0.1)
      = 14.0 + 6.0 - 2.5 + 1.4
      = 18.9
```

18.9 est largement positif -> **Invite**.

Pour un profil faible (0 exp, lycee, 0 certif) :

```
Score = (0 * 2.0) + (1 * 1.5) + (0 * -0.5) + (2 * 0.1)
      = 0 + 1.5 + 0 + 0.2
      = 1.7
```

1.7 est faible -> **Reject**.

**Pourquoi on l'utilise ?**
- Simple et rapide
- On peut voir exactement QUOI a influence la decision (les poids)
- Fonctionne bien quand on a peu de donnees (notre cas : 200 lignes)
- C'est le modele qui a gagne dans notre comparaison

**Le parametre important : `C`**

`C` controle la "rigueur" du modele :
- `C` grand (ex: 10) : le modele essaie de coller parfaitement aux donnees d'entrainement -> risque d'overfitting
- `C` petit (ex: 0.01) : le modele reste simple et generalise mieux -> c'est ce qu'on a choisi

Notre modele a choisi `C=0.01`, ce qui veut dire : "reste simple, ne sur-apprends pas ces 200 exemples".

---

### 2. Random Forest (Foret Aleatoire)

**C'est quoi en une phrase ?**
300 "arbres de decision" qui votent ensemble -- la majorite l'emporte.

**Comment ca marche (avec un exemple) ?**

Un arbre de decision, c'est comme un jeu de questions :

```
Arbre 1 :
  Est-ce que experience > 3 ans ?
    OUI -> Est-ce que education >= Master ?
              OUI -> INVITE
              NON -> REJECT
    NON -> REJECT

Arbre 2 :
  Est-ce que certifications > 2 ?
    OUI -> Est-ce que senior_title = 1 ?
              OUI -> INVITE
              NON -> Est-ce que experience > 5 ?
                        OUI -> INVITE
                        NON -> REJECT
    NON -> REJECT

...300 arbres au total...
```

Chaque arbre est different (il regarde des features et des seuils differents). Pour un nouveau CV :
- 180 arbres disent "Invite"
- 120 arbres disent "Reject"
- Majorite -> **Invite** (60% de confiance)

**Pourquoi on l'utilise ?**
- Capture des relations complexes (ex: "experience > 5 ET Master" ensemble)
- Pas besoin de normaliser les donnees
- Donne une mesure d'importance des features

**Pourquoi il n'a pas gagne ici ?**
Avec seulement 200 exemples, les 300 arbres ont tendance a "memoriser" les donnees au lieu d'apprendre les vrais patterns. C'est l'**overfitting**.

---

### 3. Gradient Boosting

**C'est quoi en une phrase ?**
Des arbres construits l'un apres l'autre, ou chaque nouvel arbre corrige les erreurs du precedent.

**Comment ca marche (avec un exemple) ?**

```
Etape 1 : Arbre 1 fait ses predictions -> se trompe sur 30 candidats
Etape 2 : Arbre 2 se concentre SUR ces 30 erreurs -> corrige 20 d'entre elles
Etape 3 : Arbre 3 se concentre sur les 10 erreurs restantes -> en corrige 7
...200 arbres au total...
```

C'est comme un etudiant qui revise : il ne relit pas tout le cours, il se concentre sur ce qu'il a rate au dernier test.

**Le parametre important : `learning_rate`**

C'est la "vitesse d'apprentissage" :
- `learning_rate=0.2` : chaque arbre apporte une grosse correction -> risque d'overfitting
- `learning_rate=0.05` : chaque arbre apporte une petite correction -> plus lent mais plus stable

**Pourquoi on l'utilise ?**
- Souvent le meilleur modele en pratique
- Tres utilise en industrie et en competitions ML

**Pourquoi il n'a pas gagne ici ?**
Meme probleme que Random Forest : trop complexe pour 200 lignes de donnees bruitees.

---

### 4. SVM (Support Vector Machine) -- Machine a Vecteurs de Support

**C'est quoi en une phrase ?**
Cherche la meilleure "frontiere" pour separer les Invite des Reject dans l'espace des features.

**Comment ca marche (avec un exemple) ?**

Imagine un graphique 2D avec experience en X et education en Y. Les Invite sont des points verts, les Reject des points rouges.

```
education
    5 |         V   V
    4 |      V    V
    3 |   R  R  V
    2 |  R  R
    1 | R R
      +-------------> experience
      0  2  4  6  8
```

SVM trace une **ligne** (en 2D) ou un **hyperplan** (en 16D) qui separe au mieux les deux groupes. Il choisit la ligne qui est **le plus loin possible** des deux groupes -- c'est la "marge maximale".

Avec le **kernel RBF**, SVM peut tracer des frontieres courbes, pas seulement des lignes droites. Ca lui permet de capturer des patterns non-lineaires.

**Pourquoi on l'utilise ?**
- Excellent sur les petits datasets (notre cas)
- Robuste a l'overfitting grace a la marge maximale
- Kernel RBF = frontieres flexibles

**Le parametre important : `C` et `gamma`**
- `C` : tolerance aux erreurs. C petit = accepte quelques erreurs pour une meilleure generalisation
- `gamma` : rayon d'influence de chaque point. Petit gamma = frontiere lisse, grand gamma = frontiere complexe

---

### 5. HistGradientBoosting

**C'est quoi en une phrase ?**
Gradient Boosting ameliore : plus rapide et gere mieux le desequilibre des classes.

**Comment ca marche ?**
Meme principe que Gradient Boosting (arbres qui corrigent les erreurs precedentes), mais avec des optimisations :
- **Histogrammes** : au lieu de tester tous les seuils possibles pour chaque feature, il regroupe les valeurs en "bins" (intervalles). Ex: au lieu de tester "experience > 3.1? > 3.2? > 3.3?...", il teste "experience > 3? > 5? > 7?". C'est beaucoup plus rapide.
- **class_weight="balanced"** : supporte nativement le desequilibre Invite/Reject (contrairement au GB classique)

**Pourquoi on l'utilise ?**
- Plus rapide que Gradient Boosting classique
- Gere nativement le desequilibre des classes

---

### 6. XGBoost (eXtreme Gradient Boosting)

**C'est quoi en une phrase ?**
La version "course automobile" du Gradient Boosting -- c'est l'algorithme qui gagne le plus de competitions de ML.

**Comment ca marche ?**
Meme principe de base que Gradient Boosting (arbres sequentiels), mais avec des ameliorations :

1. **Regularisation** : empeche le modele de devenir trop complexe (evite l'overfitting)
2. **Parallelisme** : utilise tous les coeurs du processeur pour aller plus vite
3. **Gestion native du desequilibre** : le parametre `scale_pos_weight` dit au modele "un exemple Invite vaut 3 exemples Reject" (puisqu'on a 3x plus de Reject)

**Le parametre important : `scale_pos_weight`**

```
scale_pos_weight = nb_reject / nb_invite = 149 / 51 = 2.92
```

Ca veut dire : "quand tu te trompes sur un Invite, considere que c'est 3 fois plus grave que de te tromper sur un Reject".

**Pourquoi on l'utilise ?**
- Reference en ML competitif
- Gestion native du desequilibre
- Tres configurable

---

## PARTIE 3 : Les Techniques d'amelioration

### SMOTE (Synthetic Minority Over-sampling Technique)

**Le probleme :**
On a 51 Invite et 149 Reject. Le modele a 3x plus d'exemples "Reject" pour apprendre. Il a donc tendance a tout rejeter (c'est la "solution facile").

**La solution SMOTE :**
Creer de **faux exemples Invite** en melangeant les vrais.

**Exemple concret :**

```
Vrai Invite A : experience=5, education=4, skills=12
Vrai Invite B : experience=7, education=4, skills=15

SMOTE cree un faux Invite C (entre A et B) :
  experience = 5 + 0.6*(7-5) = 6.2
  education  = 4 + 0.6*(4-4) = 4
  skills     = 12 + 0.6*(15-12) = 13.8
```

Le "C" est un point imaginaire qui se situe entre A et B. C'est un Invite *plausible*.

```
Avant SMOTE :  51 Invite, 149 Reject
Apres SMOTE : 149 Invite, 149 Reject
```

Maintenant le modele a autant d'exemples des deux classes pour apprendre.

**Attention :** SMOTE ne cree pas de vraies donnees. Les faux exemples sont des interpolations. Si les donnees d'origine sont bruitees, SMOTE amplifie le bruit.

---

### StandardScaler (Normalisation)

**Le probleme :**
Les features ont des echelles tres differentes :

```
has_certifications : 0 ou 1       (echelle 0-1)
career_gap_months  : 0 a 40       (echelle 0-40)
latest_job_duration : 0 a 58      (echelle 0-58)
```

Sans normalisation, le modele accorderait beaucoup plus d'importance a `latest_job_duration` (parce que ses valeurs sont plus grandes) meme si `has_certifications` est plus informatif.

**La solution StandardScaler :**
Transformer chaque feature pour qu'elle ait une **moyenne de 0** et un **ecart-type de 1**.

```
Avant : has_certifications = [1, 0, 1, 1, 0, ...]  -> moyenne=0.8, ecart-type=0.4
Apres : has_certifications = [0.5, -2.0, 0.5, 0.5, -2.0, ...]

Avant : career_gap_months = [14, 0, 16, 12, 0, ...]  -> moyenne=8.5, ecart-type=9.2
Apres : career_gap_months = [0.6, -0.9, 0.8, 0.4, -0.9, ...]
```

Maintenant les deux features sont sur la meme echelle et le modele peut les comparer equitablement.

---

### RandomizedSearchCV (Recherche d'hyperparametres)

**Le probleme :**
Chaque modele a des "reglages" (hyperparametres) qu'il faut choisir. Par exemple :
- Regression Logistique : quel `C` ? (0.01, 0.1, 1, 10 ?)
- Random Forest : combien d'arbres ? (100, 200, 300 ?)
- Gradient Boosting : quelle vitesse d'apprentissage ? (0.01, 0.05, 0.1 ?)

Choisir a la main, c'est comme essayer de deviner la meilleure recette sans gouter.

**La solution RandomizedSearchCV :**
Tester automatiquement plein de combinaisons et garder la meilleure.

```
Essai 1 : C=0.01, penalty=l2  -> F1 = 0.548 <- MEILLEUR
Essai 2 : C=0.1,  penalty=l2  -> F1 = 0.510
Essai 3 : C=1.0,  penalty=l2  -> F1 = 0.505
Essai 4 : C=5.0,  penalty=l2  -> F1 = 0.490
...
```

Le "CV" dans le nom veut dire **Cross-Validation** : pour chaque combinaison, on coupe les donnees en 5 morceaux, on entraine sur 4 et on teste sur le 5eme, 5 fois de suite. Ca donne un score fiable.

---

### Cross-Validation (Validation Croisee)

**Le probleme :**
Si on coupe les donnees en 1 train + 1 test, le score depend beaucoup de QUEL candidat est dans quel groupe. Avec 40 candidats en test, un seul candidat mal place change le score de 2.5%.

**La solution (5-fold cross-validation) :**

```
Pli 1 : [AAAA][BBBB][CCCC][DDDD] -> test [EEEE] -> F1 = 0.52
Pli 2 : [AAAA][BBBB][CCCC][EEEE] -> test [DDDD] -> F1 = 0.60
Pli 3 : [AAAA][BBBB][DDDD][EEEE] -> test [CCCC] -> F1 = 0.55
Pli 4 : [AAAA][CCCC][DDDD][EEEE] -> test [BBBB] -> F1 = 0.48
Pli 5 : [BBBB][CCCC][DDDD][EEEE] -> test [AAAA] -> F1 = 0.58

Score moyen = (0.52 + 0.60 + 0.55 + 0.48 + 0.58) / 5 = 0.548
```

Chaque candidat est dans le jeu de test exactement 1 fois. Le score moyen est beaucoup plus fiable qu'un seul split.

---

### Features derivees (Feature Engineering)

**Le probleme :**
Le modele voit `total_years_experience=7` et `education_level_score=4` separement. Mais il ne "comprend" pas que **7 ans + Master** c'est un profil beaucoup plus fort que **7 ans + Lycee**.

**La solution :**
Creer des features qui **combinent** les features existantes :

| Feature derivee | Formule | Exemple Marie (7 ans, Master) | Exemple Paul (7 ans, Lycee) |
|---|---|---|---|
| `experience_x_education` | exp * edu | 7 * 4 = **28** | 7 * 1 = **7** |
| `experience_x_seniority` | exp * senior | 7 * 1 = **7** | 7 * 0 = **0** |
| `experience_education_ratio` | exp / edu | 7 / 4 = **1.75** | 7 / 1 = **7.0** |
| `certs_per_year` | certs / exp | 4 / 7 = **0.57** | 0 / 7 = **0.0** |

Maintenant le modele voit directement que Marie (28) et Paul (7) ont des profils tres differents, meme s'ils ont la meme experience.

---

## PARTIE 4 : Comment le modele est selectionne

### Le processus complet

```
1. Charger les 200 candidats avec leurs labels (Invite/Reject)
2. Calculer les 4 features derivees
3. Supprimer les 3 features constantes (variance = 0)
4. Couper en 80% train (160) / 20% test (40)
5. Pour chaque modele (6 au total) :
   a. Creer le pipeline : SMOTE -> StandardScaler -> Modele
   b. Entrainer sur le train set
   c. Mesurer l'AUC sur le test set
   d. Mesurer le F1 en cross-validation 5-fold sur le train set
6. Garder le modele avec le MEILLEUR F1 en cross-validation
7. Optimiser ses hyperparametres avec RandomizedSearchCV
8. Reentrainer le modele optimise sur 100% des donnees
9. Sauvegarder le modele dans model.joblib
```

### Pourquoi F1 et pas accuracy ?

**Accuracy** = % de bonnes reponses totales.
Avec notre dataset desequilibre (74% Reject), un modele qui dit TOUJOURS "Reject" a une accuracy de 74%. Mais il rate 100% des bons candidats. C'est inutile.

**F1** = equilibre entre precision et recall.
- **Precision** : "Quand le modele dit Invite, a-t-il raison ?" (35% dans notre cas)
- **Recall** : "Parmi les vrais Invite, combien le modele en trouve ?" (60% dans notre cas)
- **F1** = moyenne harmonique des deux = 0.44

Le F1 penalise un modele qui fait trop de faux positifs OU qui rate trop de vrais positifs.

---

## PARTIE 5 : Resume visuel

```
                    DONNEES
                  200 candidats
                  51 Invite (26%)
                  149 Reject (74%)
                       |
              +--------+--------+
              |                 |
        PROBLEMES          SOLUTIONS
              |                 |
   Desequilibre 1:3     SMOTE + class_weight
   3 features mortes    Suppression auto
   Pas de combos        4 features derivees
   Params au hasard     RandomizedSearchCV
   12 labels bruites    Detection + alerte
              |
              v
        6 MODELES TESTES
   LogReg | RF | GB | SVM | HistGB | XGBoost
              |
              v
        GAGNANT: LogisticRegression
          C=0.01, avec SMOTE
          F1 = 0.548
          Recall Invite = 60%
              |
              v
         model.joblib
   (utilise par predictor.py)
```

---

## Glossaire

| Terme | Definition simple |
|---|---|
| **Feature** | Un chiffre qui decrit le CV (ex: annees d'experience) |
| **Label** | La reponse attendue (Invite ou Reject) |
| **Training** | L'etape ou le modele apprend a partir des exemples |
| **Overfitting** | Le modele memorise les exemples au lieu d'apprendre les patterns |
| **AUC** | Score de 0.5 (hasard) a 1.0 (parfait) qui mesure la qualite du modele |
| **F1** | Score qui equilibre precision et recall |
| **Precision** | "Quand le modele dit Invite, a-t-il raison ?" |
| **Recall** | "Parmi les vrais Invite, combien le modele en trouve ?" |
| **Cross-validation** | Tester le modele plusieurs fois sur des morceaux differents |
| **Hyperparametre** | Un reglage du modele qu'on choisit avant l'entrainement |
| **Pipeline** | Chaine d'etapes : SMOTE -> Normalisation -> Modele |
| **SMOTE** | Technique qui cree des exemples synthetiques pour equilibrer les classes |
| **StandardScaler** | Normalise les features pour qu'elles aient la meme echelle |
