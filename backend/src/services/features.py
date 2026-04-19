"""
Derives ML features from a parsed CVSchema.
All features are numeric — no text, no NaN.
"""
from datetime import datetime
from src.models.cv_schema import CVSchema

SENIORITY_KEYWORDS = {"senior", "lead", "manager", "head", "director", "principal", "chief", "vp", "president"}


def extract_features(cv: CVSchema) -> dict:
    """Return a flat dict of ML-ready features."""

    # ── Original features ────────────────────────────────────────────────────
    total_months = sum(e.duration_months for e in cv.experience if e.duration_months)
    total_years = round(total_months / 12, 2)

    num_positions = len(cv.experience)
    avg_tenure = round(total_months / num_positions, 1) if num_positions else 0.0

    education_score = max((e.level_score for e in cv.education), default=1)

    total_skills = (
        len(cv.skills.technical)
        + len(cv.skills.methods)
        + len(cv.skills.management)
    )

    has_certifications = 1 if cv.certifications else 0

    language_count = len(cv.languages)

    sections = [
        bool(cv.personal.full_name or cv.personal.email),
        bool(cv.summary),
        bool(cv.education),
        bool(cv.experience),
        bool(cv.skills.technical or cv.skills.methods),
        bool(cv.languages),
    ]
    section_completeness = sum(sections)

    # ── New features ─────────────────────────────────────────────────────────

    # Max language level score (C2=6 much better than A1=1)
    max_language_score = max((l.level_score for l in cv.languages), default=0)

    # Seniority in any job title
    has_senior_title = int(any(
        kw in (e.title or "").lower()
        for e in cv.experience
        for kw in SENIORITY_KEYWORDS
    ))

    # Career gap: total months between jobs (sorted by start date)
    career_gap_months = _compute_career_gap(cv)

    # Latest job duration (most recent = index 0 as parsed)
    latest_job_duration = cv.experience[0].duration_months if cv.experience and cv.experience[0].duration_months else 0

    # Has a written summary (signals care taken with CV)
    has_summary = 1 if cv.summary and len(cv.summary.strip()) > 20 else 0

    # Number of certifications (not just binary)
    num_certifications = len(cv.certifications)

    # Parse quality as ordinal score
    parse_quality_score = {"complete": 2, "partial": 1, "poor": 0}.get(cv.parse_quality, 1)

    # ── Derived features (ratios & interactions) ────────────────────────────
    experience_education_ratio = round(total_years / max(education_score, 1), 2)
    certs_per_year = round(num_certifications / max(total_years, 0.5), 2)
    experience_x_seniority = round(total_years * has_senior_title, 2)
    experience_x_education = round(total_years * education_score, 2)

    return {
        # Original
        "total_years_experience": total_years,
        "num_positions": num_positions,
        "avg_tenure_months": avg_tenure,
        "education_level_score": education_score,
        "total_skills_count": total_skills,
        "has_certifications": has_certifications,
        "language_count": language_count,
        "section_completeness_score": section_completeness,
        # New
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
    }


def _compute_career_gap(cv: CVSchema) -> int:
    """Total months of career gaps between jobs. Returns 0 if not computable."""
    dated = []
    for e in cv.experience:
        if not e.start:
            continue
        try:
            start = datetime.strptime(e.start, "%Y-%m")
            if e.end and e.end != "present":
                end = datetime.strptime(e.end, "%Y-%m")
            else:
                end = datetime.now().replace(day=1)
            dated.append((start, end))
        except ValueError:
            continue

    if len(dated) < 2:
        return 0

    dated.sort(key=lambda x: x[0])
    gap_months = 0
    for i in range(1, len(dated)):
        prev_end = dated[i - 1][1]
        curr_start = dated[i][0]
        diff = (curr_start.year - prev_end.year) * 12 + (curr_start.month - prev_end.month)
        if diff > 0:
            gap_months += diff

    return gap_months


FEATURE_COLUMNS = [
    # Original
    "total_years_experience",
    "num_positions",
    "avg_tenure_months",
    "education_level_score",
    "total_skills_count",
    "has_certifications",
    "language_count",
    "section_completeness_score",
    # New
    "max_language_score",
    "has_senior_title",
    "career_gap_months",
    "latest_job_duration",
    "has_summary",
    "num_certifications",
    "parse_quality_score",
    # Derived
    "experience_education_ratio",
    "certs_per_year",
    "experience_x_seniority",
    "experience_x_education",
]
