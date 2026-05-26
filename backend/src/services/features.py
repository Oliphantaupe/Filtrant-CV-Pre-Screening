"""
Derives ML features from a parsed CVSchema.
All features are numeric — no text, no NaN.
"""
import logging
from datetime import datetime
from src.models.cv_schema import CVSchema

logger = logging.getLogger(__name__)

LUXEMBOURG_COORDS = (49.6116, 6.1319)

# -1 = unknown (geopy unavailable or geocoding failed)
_GEOPY_AVAILABLE = False
try:
    from geopy.geocoders import Nominatim
    from geopy.distance import geodesic
    _geolocator = Nominatim(user_agent="filtrant_cv_screener", timeout=5)
    _GEOPY_AVAILABLE = True
except ImportError:
    pass


def _compute_distance_km(address: str | None) -> float:
    """Return km distance from address to Luxembourg-Ville. Returns -1 if unknown."""
    if not address or not _GEOPY_AVAILABLE:
        return -1.0
    try:
        location = _geolocator.geocode(address)
        if location:
            return round(geodesic((location.latitude, location.longitude), LUXEMBOURG_COORDS).kilometers, 1)
    except Exception as e:
        logger.debug("Geocoding failed for '%s': %s", address, e)
    return -1.0

SENIORITY_KEYWORDS = {"senior", "lead", "manager", "head", "director", "principal", "chief", "vp", "president"}

SENIORITY_LEVELS = {
    'intern': 0, 'trainee': 0, 'apprentice': 0, 'student': 0,
    'junior': 1, 'jr': 1, 'entry': 1, 'graduate': 1, 'associate': 1,
    'senior': 3, 'sr': 3, 'lead': 3, 'specialist': 3, 'expert': 3,
    'principal': 4, 'staff': 4,
    'manager': 4, 'supervisor': 4, 'head': 4,
    'director': 5, 'vp': 5, 'vice president': 5, 'partner': 5,
    'chief': 5, 'cto': 5, 'cfo': 5, 'ceo': 5, 'president': 5, 'founder': 5,
}


def _get_seniority(title: str | None) -> int:
    if not title:
        return 2
    t = title.lower()
    for kw in sorted(SENIORITY_LEVELS, key=len, reverse=True):
        if kw in t:
            return SENIORITY_LEVELS[kw]
    return 2


def _compute_trajectory(cv: CVSchema) -> int:
    exps = sorted(cv.experience, key=lambda e: e.start or '', reverse=False)
    if len(exps) < 2:
        return 0
    levels = [_get_seniority(e.title) for e in exps]
    return sum(1 for a, b in zip(levels, levels[1:]) if b > a)


def _duration_months(e) -> int:
    """
    Return duration in months for an Experience entry.
    Uses the LLM-provided value when available; otherwise computes from
    start/end strings so 'present' roles are never counted as 0.
    """
    if e.duration_months is not None and e.duration_months > 0:
        return e.duration_months
    if not e.start:
        return 0
    try:
        start_dt = datetime.strptime(e.start, "%Y-%m")
        if e.end and e.end.lower() not in ("present", ""):
            end_dt = datetime.strptime(e.end, "%Y-%m")
        else:
            end_dt = datetime.now().replace(day=1)
        return max(0, (end_dt.year - start_dt.year) * 12 + (end_dt.month - start_dt.month))
    except ValueError:
        return 0


def extract_features(cv: CVSchema) -> dict:
    """Return a flat dict of ML-ready features."""

    # ── Original features ────────────────────────────────────────────────────
    total_months = sum(_duration_months(e) for e in cv.experience)
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
    latest_job_duration = _duration_months(cv.experience[0]) if cv.experience else 0

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

    # ── Career trajectory features ───────────────────────────────────────────
    career_trajectory_score = _compute_trajectory(cv)
    latest_title_seniority = _get_seniority(cv.experience[0].title if cv.experience else None)

    # ── Geolocation feature ───────────────────────────────────────────────────
    # Distance to Luxembourg-Ville in km (-1 = unknown address or geopy unavailable).
    # Candidates closer to Luxembourg tend to be more likely to be invited.
    distance_km = _compute_distance_km(cv.personal.address)

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
        # Career trajectory
        "career_trajectory_score": career_trajectory_score,
        "latest_title_seniority": latest_title_seniority,
        # Geolocation
        "distance_km": distance_km,
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
    # Career trajectory
    "career_trajectory_score",
    "latest_title_seniority",
    # Geolocation
    "distance_km",
]
