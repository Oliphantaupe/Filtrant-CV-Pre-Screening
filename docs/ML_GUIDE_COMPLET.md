# Complete Guide — ML Algorithms in the Filtrant Project

## Introduction

This document explains **every algorithm and technique** used in the Filtrant project for automated CV screening. The goal: anyone with no ML background should be able to understand how and why each piece of the puzzle works.

---


## PART 1: The Global Pipeline

### How does a CV become a decision?

Imagine a recruiter receives a CV as a PDF. Here is what the system does, step by step:

```
1. The CV arrives (PDF or DOCX)
         |
2. extractor.py extracts the raw TEXT from the file
         |
3. llm_parser.py sends the text to Anthropic Claude (Haiku 4.5), which structures it as JSON
         |
4. features.py transforms the JSON into 16 NUMBERS
         |
5. predictor.py feeds these 16 numbers to the ML model
         |
6. The model responds: "Invite" or "Reject" + a confidence score
```

**The ML model never reads the CV.** It only sees 16 numbers. It is Claude (the LLM) that handles the text comprehension work.

### Why 16 numbers?

Because a classical ML algorithm does not understand words. It can only work with numbers. So we transform each CV into a "profile sheet" of 16 measurements:

**Concrete example:**

```
Marie Dupont, 7 years of experience, Master's in Computer Science, 3 positions held,
speaks 2 languages, has 4 certifications, title "Senior Developer"

-> This information becomes:
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

The model looks at these 16 numbers and decides: **Invite** (90% confidence).

---

## PART 2: Classification Algorithms

The goal of these algorithms: learn from past examples (CVs with their Invite/Reject decision) to predict the decision on new CVs.

### 1. Logistic Regression

**What is it in one sentence?**
A calculation that computes a weighted sum of all features and says "Invite" if the total is high enough.

**How does it work (with an example)?**

Imagine the model has learned these weights:

```
experience :     +2.0  (lots of experience = good sign)
education :      +1.5  (high degree = good sign)
career_gap :     -0.5  (career gaps = bad sign)
skills :         +0.1  (low impact)
```

For Marie (7 years exp, Master, 5 months gap, 14 skills):

```
Score = (7 * 2.0) + (4 * 1.5) + (5 * -0.5) + (14 * 0.1)
      = 14.0 + 6.0 - 2.5 + 1.4
      = 18.9
```

18.9 is clearly positive -> **Invite**.

For a weak profile (0 exp, high school, 0 certifications):

```
Score = (0 * 2.0) + (1 * 1.5) + (0 * -0.5) + (2 * 0.1)
      = 0 + 1.5 + 0 + 0.2
      = 1.7
```

1.7 is low -> **Reject**.

**Why do we use it?**
- Simple and fast
- You can see exactly WHAT influenced the decision (the weights)
- Works well with little data (our case: 200 rows)
- It is the model that won in our comparison

**The important parameter: `C`**

`C` controls the "strictness" of the model:
- Large `C` (e.g. 10): the model tries to fit the training data perfectly -> risk of overfitting
- Small `C` (e.g. 0.01): the model stays simple and generalises better -> this is what we chose

Our model chose `C=0.01`, which means: "stay simple, don't over-learn these 200 examples".

---

### 2. Random Forest

**What is it in one sentence?**
300 "decision trees" that vote together — the majority wins.

**How does it work (with an example)?**

A decision tree is like a game of questions:

```
Tree 1:
  Is experience > 3 years?
    YES -> Is education >= Master?
              YES -> INVITE
              NO  -> REJECT
    NO  -> REJECT

Tree 2:
  Are certifications > 2?
    YES -> Is senior_title = 1?
              YES -> INVITE
              NO  -> Is experience > 5?
                        YES -> INVITE
                        NO  -> REJECT
    NO  -> REJECT

...300 trees in total...
```

Each tree is different (it looks at different features and thresholds). For a new CV:
- 180 trees say "Invite"
- 120 trees say "Reject"
- Majority -> **Invite** (60% confidence)

**Why do we use it?**
- Captures complex relationships (e.g. "experience > 5 AND Master" together)
- No need to normalise the data
- Provides a feature importance measure

**Why didn't it win here?**
With only 200 examples, the 300 trees tend to "memorise" the data instead of learning the real patterns. This is **overfitting**.

---

### 3. Gradient Boosting

**What is it in one sentence?**
Trees built one after the other, where each new tree corrects the errors of the previous one.

**How does it work (with an example)?**

```
Step 1: Tree 1 makes its predictions -> gets 30 candidates wrong
Step 2: Tree 2 focuses ON those 30 errors -> corrects 20 of them
Step 3: Tree 3 focuses on the 10 remaining errors -> corrects 7
...200 trees in total...
```

It is like a student revising: they don't reread the entire course, they focus on what they got wrong in the last test.

**The important parameter: `learning_rate`**

This is the "learning speed":
- `learning_rate=0.2`: each tree makes a large correction -> risk of overfitting
- `learning_rate=0.05`: each tree makes a small correction -> slower but more stable

**Why do we use it?**
- Often the best model in practice
- Widely used in industry and ML competitions

**Why didn't it win here?**
Same problem as Random Forest: too complex for 200 rows of noisy data.

---

### 4. SVM (Support Vector Machine)

**What is it in one sentence?**
Finds the best "boundary" to separate Invite from Reject in the feature space.

**How does it work (with an example)?**

Imagine a 2D chart with experience on the X axis and education on the Y axis. Invite candidates are green dots, Reject are red dots.

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

SVM draws a **line** (in 2D) or a **hyperplane** (in 16D) that best separates the two groups. It chooses the line that is **as far as possible** from both groups — this is the "maximum margin".

With the **RBF kernel**, SVM can draw curved boundaries, not just straight lines. This allows it to capture non-linear patterns.

**Why do we use it?**
- Excellent on small datasets (our case)
- Robust to overfitting thanks to the maximum margin
- RBF kernel = flexible boundaries

**The important parameters: `C` and `gamma`**
- `C`: tolerance to errors. Small C = accepts some errors for better generalisation
- `gamma`: radius of influence of each point. Small gamma = smooth boundary, large gamma = complex boundary

---

### 5. HistGradientBoosting

**What is it in one sentence?**
An improved Gradient Boosting: faster and handles class imbalance better.

**How does it work?**
Same principle as Gradient Boosting (trees correcting previous errors), but with optimisations:
- **Histograms**: instead of testing every possible threshold for each feature, it groups values into "bins" (intervals). E.g. instead of testing "experience > 3.1? > 3.2? > 3.3?...", it tests "experience > 3? > 5? > 7?". This is much faster.
- **class_weight="balanced"**: natively supports the Invite/Reject imbalance (unlike standard GB)

**Why do we use it?**
- Faster than standard Gradient Boosting
- Natively handles class imbalance

---

### 6. XGBoost (eXtreme Gradient Boosting)

**What is it in one sentence?**
The "Formula 1" version of Gradient Boosting — it is the algorithm that wins the most ML competitions.

**How does it work?**
Same core principle as Gradient Boosting (sequential trees), but with improvements:

1. **Regularisation**: prevents the model from becoming too complex (avoids overfitting)
2. **Parallelism**: uses all CPU cores to run faster
3. **Native imbalance handling**: the `scale_pos_weight` parameter tells the model "one Invite example is worth 3 Reject examples" (since we have 3× more Rejects)

**The important parameter: `scale_pos_weight`**

```
scale_pos_weight = num_reject / num_invite = 149 / 51 = 2.92
```

This means: "when you get an Invite wrong, treat it as 3 times worse than getting a Reject wrong".

**Why do we use it?**
- Reference algorithm in competitive ML
- Native imbalance handling
- Highly configurable

---

## PART 3: Improvement Techniques

### SMOTE (Synthetic Minority Over-sampling Technique)

**The problem:**
We have 51 Invite and 149 Reject. The model has 3× more "Reject" examples to learn from. It therefore tends to reject everything (the "easy solution").

**The SMOTE solution:**
Create **fake Invite examples** by mixing real ones.

**Concrete example:**

```
Real Invite A: experience=5, education=4, skills=12
Real Invite B: experience=7, education=4, skills=15

SMOTE creates a fake Invite C (between A and B):
  experience = 5 + 0.6*(7-5) = 6.2
  education  = 4 + 0.6*(4-4) = 4
  skills     = 12 + 0.6*(15-12) = 13.8
```

"C" is an imaginary point situated between A and B. It is a *plausible* Invite.

```
Before SMOTE:  51 Invite, 149 Reject
After SMOTE:  149 Invite, 149 Reject
```

Now the model has just as many examples from both classes to learn from.

**Warning:** SMOTE does not create real data. The fake examples are interpolations. If the original data is noisy, SMOTE amplifies the noise.

---

### StandardScaler (Normalisation)

**The problem:**
Features have very different scales:

```
has_certifications  : 0 or 1         (scale 0–1)
career_gap_months   : 0 to 40        (scale 0–40)
latest_job_duration : 0 to 58        (scale 0–58)
```

Without normalisation, the model would give far more importance to `latest_job_duration` (because its values are larger) even if `has_certifications` is more informative.

**The StandardScaler solution:**
Transform each feature so that it has a **mean of 0** and a **standard deviation of 1**.

```
Before: has_certifications = [1, 0, 1, 1, 0, ...]  -> mean=0.8, std=0.4
After:  has_certifications = [0.5, -2.0, 0.5, 0.5, -2.0, ...]

Before: career_gap_months = [14, 0, 16, 12, 0, ...]  -> mean=8.5, std=9.2
After:  career_gap_months = [0.6, -0.9, 0.8, 0.4, -0.9, ...]
```

Now both features are on the same scale and the model can compare them fairly.

---

### RandomizedSearchCV (Hyperparameter Search)

**The problem:**
Each model has "settings" (hyperparameters) that need to be chosen. For example:
- Logistic Regression: which `C`? (0.01, 0.1, 1, 10?)
- Random Forest: how many trees? (100, 200, 300?)
- Gradient Boosting: what learning rate? (0.01, 0.05, 0.1?)

Choosing by hand is like trying to guess the best recipe without tasting it.

**The RandomizedSearchCV solution:**
Automatically test many combinations and keep the best one.

```
Trial 1: C=0.01, penalty=l2  -> F1 = 0.548  <- BEST
Trial 2: C=0.1,  penalty=l2  -> F1 = 0.510
Trial 3: C=1.0,  penalty=l2  -> F1 = 0.505
Trial 4: C=5.0,  penalty=l2  -> F1 = 0.490
...
```

The "CV" in the name stands for **Cross-Validation**: for each combination, the data is split into 5 chunks, training on 4 and testing on the 5th, 5 times in a row. This gives a reliable score.

---

### Cross-Validation

**The problem:**
If you split the data into 1 train + 1 test set, the score depends heavily on WHICH candidate ends up in which group. With 40 candidates in the test set, one misplaced candidate shifts the score by 2.5%.

**The solution (5-fold cross-validation):**

```
Fold 1: [AAAA][BBBB][CCCC][DDDD] -> test [EEEE] -> F1 = 0.52
Fold 2: [AAAA][BBBB][CCCC][EEEE] -> test [DDDD] -> F1 = 0.60
Fold 3: [AAAA][BBBB][DDDD][EEEE] -> test [CCCC] -> F1 = 0.55
Fold 4: [AAAA][CCCC][DDDD][EEEE] -> test [BBBB] -> F1 = 0.48
Fold 5: [BBBB][CCCC][DDDD][EEEE] -> test [AAAA] -> F1 = 0.58

Average score = (0.52 + 0.60 + 0.55 + 0.48 + 0.58) / 5 = 0.548
```

Each candidate is in the test set exactly once. The average score is much more reliable than a single split.

---

### Derived Features (Feature Engineering)

**The problem:**
The model sees `total_years_experience=7` and `education_level_score=4` separately. But it does not "understand" that **7 years + Master's** is a much stronger profile than **7 years + high school**.

**The solution:**
Create features that **combine** existing features:

| Derived feature | Formula | Example Marie (7 yrs, Master) | Example Paul (7 yrs, high school) |
|---|---|---|---|
| `experience_x_education` | exp × edu | 7 × 4 = **28** | 7 × 1 = **7** |
| `experience_x_seniority` | exp × senior | 7 × 1 = **7** | 7 × 0 = **0** |
| `experience_education_ratio` | exp / edu | 7 / 4 = **1.75** | 7 / 1 = **7.0** |
| `certs_per_year` | certs / exp | 4 / 7 = **0.57** | 0 / 7 = **0.0** |

Now the model directly sees that Marie (28) and Paul (7) have very different profiles, even though they have the same experience.

---

## PART 4: How the Model Is Selected

### The complete process

```
1. Load the 200 candidates with their labels (Invite/Reject)
2. Compute the 4 derived features
3. Remove the 3 constant features (variance = 0)
4. Split into 80% train (160) / 20% test (40)
5. For each model (6 in total):
   a. Create the pipeline: SMOTE -> StandardScaler -> Model
   b. Train on the train set
   c. Measure AUC on the test set
   d. Measure F1 with 5-fold cross-validation on the train set
6. Keep the model with the BEST F1 in cross-validation
7. Optimise its hyperparameters with RandomizedSearchCV
8. Retrain the optimised model on 100% of the data
9. Save the model to model.joblib
```

### Why F1 and not accuracy?

**Accuracy** = % of correct answers overall.
With our imbalanced dataset (74% Reject), a model that ALWAYS says "Reject" has an accuracy of 74%. But it misses 100% of good candidates. That is useless.

**F1** = balance between precision and recall.
- **Precision**: "When the model says Invite, is it right?" (35% in our case)
- **Recall**: "Among the real Invites, how many does the model find?" (60% in our case)
- **F1** = harmonic mean of the two = 0.44

F1 penalises a model that produces too many false positives OR misses too many true positives.

---

## PART 5: Visual Summary

```
                    DATA
                  200 candidates
                  51 Invite (26%)
                  149 Reject (74%)
                       |
              +--------+--------+
              |                 |
          PROBLEMS          SOLUTIONS
              |                 |
   1:3 imbalance        SMOTE + class_weight
   3 dead features      Auto-removal
   No combinations      4 derived features
   Random params        RandomizedSearchCV
   12 noisy labels      Detection + alert
              |
              v
        6 MODELS TESTED
   LogReg | RF | GB | SVM | HistGB | XGBoost
              |
              v
        WINNER: LogisticRegression
          C=0.01, with SMOTE
          F1 = 0.548
          Invite Recall = 60%
              |
              v
         model.joblib
   (used by predictor.py)
```

---

## Glossary

| Term | Simple definition |
|---|---|
| **Feature** | A number that describes the CV (e.g. years of experience) |
| **Label** | The expected answer (Invite or Reject) |
| **Training** | The step where the model learns from examples |
| **Overfitting** | The model memorises examples instead of learning the real patterns |
| **AUC** | Score from 0.5 (random) to 1.0 (perfect) measuring model quality |
| **F1** | Score that balances precision and recall |
| **Precision** | "When the model says Invite, is it right?" |
| **Recall** | "Among the real Invites, how many does the model find?" |
| **Cross-validation** | Testing the model multiple times on different data chunks |
| **Hyperparameter** | A model setting chosen before training |
| **Pipeline** | Chain of steps: SMOTE -> Normalisation -> Model |
| **SMOTE** | Technique that creates synthetic examples to balance the classes |
| **StandardScaler** | Normalises features so they all share the same scale |
