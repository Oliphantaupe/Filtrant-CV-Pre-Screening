"""
parse_training_cvs.py
=====================
Parses all CV text files in training_cvs/, extracts ML features and
demographic attributes, joins with student_labels.csv, and writes
training_dataset.csv — the single data source for all WP2 scripts.

Usage:
    python backend/ml/parse_training_cvs.py
    # or inside Docker:
    docker compose exec backend python /app/ml/parse_training_cvs.py
"""

import csv
import re
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
CVS_DIR = HERE / "training_cvs"
LABELS_PATH = HERE / "student_labels.csv"
OUTPUT_PATH = HERE / "training_dataset.csv"

CURRENT_YEAR = 2026
CURRENT_DATE = datetime(2026, 5, 1)

# ── Lookup tables ─────────────────────────────────────────────────────────────

DEGREE_SCORES = {
    "phd": 5, "doctorate": 5, "doctor of": 5,
    "master": 4, "m.s": 4, "m.sc": 4, "msc": 4, "mba": 4, "m.eng": 4,
    "bachelor": 3, "b.s": 3, "b.sc": 3, "bsc": 3, "b.a": 3, "b.eng": 3,
    "associate": 2,
    "high school": 1, "secondary": 1, "diploma": 1,
}

CEFR_SCORES = {"a1": 1, "a2": 2, "b1": 3, "b2": 4, "c1": 5, "c2": 6}

SENIORITY_KEYWORDS = {
    "senior", "lead", "manager", "head", "director",
    "principal", "chief", "vp", "president",
}

SENIORITY_LEVELS = {
    'intern': 0, 'trainee': 0, 'apprentice': 0, 'student': 0,
    'junior': 1, 'jr': 1, 'entry': 1, 'graduate': 1, 'associate': 1,
    'senior': 3, 'sr': 3, 'lead': 3, 'specialist': 3, 'expert': 3,
    'principal': 4, 'staff': 4,
    'manager': 4, 'supervisor': 4, 'head': 4,
    'director': 5, 'vp': 5, 'vice president': 5, 'partner': 5,
    'chief': 5, 'cto': 5, 'cfo': 5, 'ceo': 5, 'president': 5, 'founder': 5,
}


def _get_seniority(title: str) -> int:
    if not title:
        return 2
    t = title.lower()
    for kw in sorted(SENIORITY_LEVELS, key=len, reverse=True):
        if kw in t:
            return SENIORITY_LEVELS[kw]
    return 2


# ── Section parser ────────────────────────────────────────────────────────────

def parse_cv(text: str) -> dict:
    """Parse a CV text file into a flat dict of features + demographics."""
    lines = text.splitlines()

    # ── Header fields (key: value lines at the top) ───────────────────────────
    header = {}
    for line in lines:
        if ": " in line and not line.startswith(" ") and not line.startswith("*"):
            key, _, val = line.partition(": ")
            key = key.strip().lower().replace(" ", "_")
            header[key] = val.strip()

    # ── Split into named sections ─────────────────────────────────────────────
    sections: dict[str, list[str]] = {}
    current_section = None
    section_headers = {
        "professional summary", "education", "experience",
        "skills", "languages", "certifications",
    }

    for line in lines:
        stripped = line.strip()
        lower = stripped.lower().rstrip(":")
        if lower in section_headers:
            current_section = lower
            sections[current_section] = []
        elif current_section is not None and stripped:
            sections[current_section].append(stripped)

    # ── Demographics ──────────────────────────────────────────────────────────
    gender_raw = header.get("gender", "").lower()
    if "female" in gender_raw:
        gender = "female"
    elif "male" in gender_raw:
        gender = "male"
    else:
        gender = "other"

    dob_str = header.get("date_of_birth", "")
    try:
        birth_year = int(dob_str.split("-")[0])
    except (ValueError, IndexError):
        birth_year = 1990

    age = CURRENT_YEAR - birth_year

    if age <= 28:
        age_cohort = "22-28"
    elif age <= 32:
        age_cohort = "29-32"
    elif age <= 36:
        age_cohort = "33-36"
    else:
        age_cohort = "37-44"

    address = header.get("address", "")
    country = address.split(",")[-1].strip() if address else "Unknown"

    # ── Education ─────────────────────────────────────────────────────────────
    edu_lines = sections.get("education", [])
    education_score = 1
    for line in edu_lines:
        lower = line.lower()
        for kw, score in DEGREE_SCORES.items():
            if kw in lower:
                education_score = max(education_score, score)

    # ── Experience ────────────────────────────────────────────────────────────
    exp_lines = sections.get("experience", [])
    experiences = _parse_experiences(exp_lines)

    num_positions = len(experiences)
    durations = [e["duration_months"] for e in experiences if e["duration_months"] > 0]
    total_months = sum(durations)
    total_years = round(total_months / 12, 2)
    avg_tenure = round(total_months / num_positions, 1) if num_positions else 0.0
    latest_job_duration = experiences[0]["duration_months"] if experiences else 0
    career_gap_months = _compute_gap(experiences)

    has_senior_title = int(any(
        kw in e["title"].lower()
        for e in experiences
        for kw in SENIORITY_KEYWORDS
        if e["title"]
    ))

    # Career trajectory: count of upward seniority transitions (earliest → latest)
    experiences_asc = sorted(experiences, key=lambda e: e["start"])
    levels_asc = [_get_seniority(e["title"]) for e in experiences_asc]
    career_trajectory_score = sum(1 for a, b in zip(levels_asc, levels_asc[1:]) if b > a)
    latest_title_seniority = _get_seniority(experiences[0]["title"]) if experiences else 2

    # ── Skills ────────────────────────────────────────────────────────────────
    skill_lines = sections.get("skills", [])
    total_skills = 0
    for line in skill_lines:
        if ":" in line:
            _, _, vals = line.partition(":")
            total_skills += len([s.strip() for s in vals.split(",") if s.strip()])

    # ── Languages ─────────────────────────────────────────────────────────────
    lang_lines = sections.get("languages", [])
    lang_scores = []
    for line in lang_lines:
        parts = line.split("—")
        if len(parts) >= 2:
            level = parts[-1].strip().lower()
            if level in CEFR_SCORES:
                lang_scores.append(CEFR_SCORES[level])

    language_count = len(lang_scores)
    max_language_score = max(lang_scores, default=0)
    is_multilingual = int(language_count >= 2)

    # ── Certifications ────────────────────────────────────────────────────────
    cert_lines = sections.get("certifications", [])
    certs = [c for c in cert_lines if c.lower() != "none listed" and c.strip()]
    num_certifications = len(certs)
    has_certifications = int(num_certifications > 0)

    # ── Summary ───────────────────────────────────────────────────────────────
    summary_lines = sections.get("professional summary", [])
    summary_text = " ".join(summary_lines)
    has_summary = int(len(summary_text.strip()) > 20)

    # ── Section completeness ──────────────────────────────────────────────────
    section_completeness_score = sum([
        bool(header.get("name")),
        bool(summary_text.strip()),
        bool(edu_lines),
        bool(experiences),
        bool(total_skills > 0),
        bool(language_count > 0),
    ])

    # ── Parse quality ─────────────────────────────────────────────────────────
    if section_completeness_score >= 5:
        parse_quality_score = 2
    elif section_completeness_score >= 3:
        parse_quality_score = 1
    else:
        parse_quality_score = 0

    # ── Derived features ──────────────────────────────────────────────────────
    experience_education_ratio = round(total_years / max(education_score, 1), 2)
    certs_per_year = round(num_certifications / max(total_years, 0.5), 2)
    experience_x_seniority = round(total_years * has_senior_title, 2)
    experience_x_education = round(total_years * education_score, 2)

    return {
        # Demographics (audit only)
        "gender": gender,
        "birth_year": birth_year,
        "age": age,
        "age_cohort": age_cohort,
        "country": country,
        "is_multilingual": is_multilingual,
        # ML features
        "total_years_experience": total_years,
        "num_positions": num_positions,
        "avg_tenure_months": avg_tenure,
        "education_level_score": education_score,
        "total_skills_count": total_skills,
        "has_certifications": has_certifications,
        "language_count": language_count,
        "section_completeness_score": section_completeness_score,
        "max_language_score": max_language_score,
        "has_senior_title": has_senior_title,
        "career_gap_months": career_gap_months,
        "latest_job_duration": latest_job_duration,
        "has_summary": has_summary,
        "num_certifications": num_certifications,
        "parse_quality_score": parse_quality_score,
        # Derived
        "experience_education_ratio": experience_education_ratio,
        "certs_per_year": certs_per_year,
        "experience_x_seniority": experience_x_seniority,
        "experience_x_education": experience_x_education,
        # Career trajectory
        "career_trajectory_score": career_trajectory_score,
        "latest_title_seniority": latest_title_seniority,
    }


# ── Experience helpers ────────────────────────────────────────────────────────

def _parse_experiences(lines: list[str]) -> list[dict]:
    """
    Experience lines look like:
      Senior Software Engineer — Atlas Systems — Cologne, Germany — 2016-01 to Present
    Returns list of dicts with title, start, end, duration_months.
    """
    entries = []
    date_pattern = re.compile(r"(\d{4}-\d{2})\s+to\s+(\d{4}-\d{2}|[Pp]resent)", re.IGNORECASE)

    for line in lines:
        if line.startswith("*") or not "—" in line:
            continue
        m = date_pattern.search(line)
        if not m:
            continue

        start_str, end_str = m.group(1), m.group(2)
        try:
            start_dt = datetime.strptime(start_str, "%Y-%m")
        except ValueError:
            continue

        if end_str.lower() == "present":
            end_dt = CURRENT_DATE
        else:
            try:
                end_dt = datetime.strptime(end_str, "%Y-%m")
            except ValueError:
                end_dt = CURRENT_DATE

        duration = max(0, (end_dt.year - start_dt.year) * 12 + (end_dt.month - start_dt.month))

        parts = line.split("—")
        title = parts[0].strip() if parts else ""

        entries.append({
            "title": title,
            "start": start_dt,
            "end": end_dt,
            "duration_months": duration,
        })

    # Sort by start date descending (most recent first)
    entries.sort(key=lambda e: e["start"], reverse=True)
    return entries


def _compute_gap(experiences: list[dict]) -> int:
    """Total months of gaps between jobs (chronological order)."""
    if len(experiences) < 2:
        return 0

    dated = sorted(experiences, key=lambda e: e["start"])
    gap = 0
    for i in range(1, len(dated)):
        prev_end = dated[i - 1]["end"]
        curr_start = dated[i]["start"]
        diff = (curr_start.year - prev_end.year) * 12 + (curr_start.month - prev_end.month)
        if diff > 0:
            gap += diff
    return gap


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 60)
    print("  FILTRANT — Training Dataset Builder")
    print("=" * 60)

    # Load labels
    labels: dict[str, int] = {}
    with open(LABELS_PATH, newline="") as f:
        for row in csv.DictReader(f):
            labels[row["filename"]] = int(row["passed_next_stage"])

    print(f"\nLabels loaded: {len(labels)} entries")
    print(f"  Invite (1): {sum(v for v in labels.values())}")
    print(f"  Reject (0): {sum(1 for v in labels.values() if v == 0)}")

    cv_files = sorted(CVS_DIR.glob("*.txt"))
    print(f"\nCV files found: {len(cv_files)}")

    rows = []
    errors = []

    for cv_path in cv_files:
        filename = cv_path.name
        label = labels.get(filename)
        if label is None:
            errors.append(f"  [SKIP] {filename} — no label found")
            continue

        text = cv_path.read_text(encoding="utf-8")
        try:
            features = parse_cv(text)
        except Exception as e:
            errors.append(f"  [ERROR] {filename} — {e}")
            continue

        row = {"filename": filename, "passed_next_stage": label}
        row.update(features)
        rows.append(row)

    if errors:
        print(f"\nWarnings ({len(errors)}):")
        for e in errors:
            print(e)

    if not rows:
        print("\nERROR: no rows produced.")
        return

    # Write CSV
    fieldnames = list(rows[0].keys())
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDataset written: {OUTPUT_PATH}")
    print(f"  Rows    : {len(rows)}")
    print(f"  Columns : {len(fieldnames)}")

    # Quick sanity check
    import statistics
    years_exp = [r["total_years_experience"] for r in rows]
    genders = [r["gender"] for r in rows]
    ages = [r["age"] for r in rows]

    print(f"\nSanity check:")
    print(f"  avg years_experience : {statistics.mean(years_exp):.1f}")
    print(f"  avg age              : {statistics.mean(ages):.1f}")
    print(f"  gender — male        : {genders.count('male')}  female: {genders.count('female')}  other: {genders.count('other')}")
    for cohort in ["22-28", "29-32", "33-36", "37-44"]:
        n = sum(1 for r in rows if r["age_cohort"] == cohort)
        print(f"  age cohort {cohort}: {n}")
    print()


if __name__ == "__main__":
    main()
