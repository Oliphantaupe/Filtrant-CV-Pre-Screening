"""
Derives ML features from a parsed CVSchema.
All features are numeric — no text, no NaN.
"""
from src.models.cv_schema import CVSchema


def extract_features(cv: CVSchema) -> dict:
    """Return a flat dict of ML-ready features."""
    total_months = sum(
        e.duration_months for e in cv.experience if e.duration_months
    )
    total_years = round(total_months / 12, 2)

    num_positions = len(cv.experience)

    avg_tenure = round(total_months / num_positions, 1) if num_positions else 0.0

    education_score = max(
        (e.level_score for e in cv.education), default=1
    )

    total_skills = (
        len(cv.skills.technical)
        + len(cv.skills.methods)
        + len(cv.skills.management)
    )

    has_certifications = 1 if cv.certifications else 0

    language_count = len(cv.languages)

    # 0–5: personal, summary, education, experience, skills, languages
    sections = [
        bool(cv.personal.full_name or cv.personal.email),
        bool(cv.summary),
        bool(cv.education),
        bool(cv.experience),
        bool(cv.skills.technical or cv.skills.methods),
        bool(cv.languages),
    ]
    section_completeness = sum(sections)

    return {
        "total_years_experience": total_years,
        "num_positions": num_positions,
        "avg_tenure_months": avg_tenure,
        "education_level_score": education_score,
        "total_skills_count": total_skills,
        "has_certifications": has_certifications,
        "language_count": language_count,
        "section_completeness_score": section_completeness,
    }


FEATURE_COLUMNS = [
    "total_years_experience",
    "num_positions",
    "avg_tenure_months",
    "education_level_score",
    "total_skills_count",
    "has_certifications",
    "language_count",
    "section_completeness_score",
]
