"""
Unit tests for src.services.features.extract_features().
All pure functions — no mocking required.
"""
import pytest
from src.services.features import extract_features, FEATURE_COLUMNS
from src.models.cv_schema import CVSchema, PersonalInfo, Experience, Education, Skills, Language, Certification


# ── Completeness ────────────────────────────────────────────────────────────

def test_all_22_features_present(full_cv):
    feats = extract_features(full_cv)
    assert set(feats.keys()) == set(FEATURE_COLUMNS)
    assert len(feats) == 22


def test_all_features_are_numeric(full_cv):
    feats = extract_features(full_cv)
    for key, val in feats.items():
        assert isinstance(val, (int, float)), f"{key} is not numeric: {val!r}"


def test_no_nan_values(full_cv):
    import math
    feats = extract_features(full_cv)
    for key, val in feats.items():
        assert not math.isnan(val), f"{key} is NaN"


# ── Experience features ─────────────────────────────────────────────────────

def test_total_years_experience(full_cv):
    feats = extract_features(full_cv)
    # 52 + 45 + 17 = 114 months → 9.5 years
    assert feats["total_years_experience"] == pytest.approx(9.5, abs=0.1)


def test_num_positions(full_cv):
    feats = extract_features(full_cv)
    assert feats["num_positions"] == 3


def test_avg_tenure_months(full_cv):
    feats = extract_features(full_cv)
    assert feats["avg_tenure_months"] == pytest.approx((52 + 45 + 17) / 3, abs=0.5)


def test_no_experience_gives_zero_years(minimal_cv):
    feats = extract_features(minimal_cv)
    assert feats["total_years_experience"] == 0
    assert feats["num_positions"] == 0
    assert feats["avg_tenure_months"] == 0


def test_latest_job_duration(full_cv):
    feats = extract_features(full_cv)
    # first experience has duration_months=52
    assert feats["latest_job_duration"] == 52


# ── Education features ──────────────────────────────────────────────────────

def test_education_level_score_uses_max(full_cv):
    # Two educations: level_score 4 and 3 → should take max
    feats = extract_features(full_cv)
    assert feats["education_level_score"] == 4


def test_education_level_score_empty(minimal_cv):
    # No education entries → defaults to minimum level_score=1
    feats = extract_features(minimal_cv)
    assert feats["education_level_score"] == 1


# ── Skills & certifications ─────────────────────────────────────────────────

def test_total_skills_count(full_cv):
    # technical=5, methods=2, management=1 → 8
    feats = extract_features(full_cv)
    assert feats["total_skills_count"] == 8


def test_has_certifications(full_cv):
    feats = extract_features(full_cv)
    assert feats["has_certifications"] == 1


def test_no_certifications(minimal_cv):
    feats = extract_features(minimal_cv)
    assert feats["has_certifications"] == 0
    assert feats["num_certifications"] == 0


def test_certs_per_year(full_cv):
    feats = extract_features(full_cv)
    total_years = feats["total_years_experience"]
    if total_years > 0:
        assert feats["certs_per_year"] == pytest.approx(2 / total_years, abs=0.01)


# ── Language features ───────────────────────────────────────────────────────

def test_language_count(full_cv):
    feats = extract_features(full_cv)
    assert feats["language_count"] == 3


def test_max_language_score(full_cv):
    # French C2 = level_score 6
    feats = extract_features(full_cv)
    assert feats["max_language_score"] == 6


def test_no_languages(minimal_cv):
    feats = extract_features(minimal_cv)
    assert feats["language_count"] == 0
    assert feats["max_language_score"] == 0


# ── Seniority features ──────────────────────────────────────────────────────

def test_has_senior_title_detected(senior_cv):
    feats = extract_features(senior_cv)
    assert feats["has_senior_title"] == 1


def test_has_senior_title_absent(minimal_cv):
    feats = extract_features(minimal_cv)
    assert feats["has_senior_title"] == 0


def test_senior_title_keywords():
    cv = CVSchema(
        personal=PersonalInfo(full_name="Test"),
        experience=[Experience(title="VP Engineering", company="X",
                               start="2020-01", end="present", duration_months=24)],
        parse_quality="partial",
    )
    feats = extract_features(cv)
    assert feats["has_senior_title"] == 1


# ── Summary / completeness ──────────────────────────────────────────────────

def test_has_summary(full_cv):
    feats = extract_features(full_cv)
    assert feats["has_summary"] == 1


def test_no_summary(minimal_cv):
    feats = extract_features(minimal_cv)
    assert feats["has_summary"] == 0


def test_section_completeness_score(full_cv):
    feats = extract_features(full_cv)
    # full_cv has personal, summary, experience, education, skills, certs, languages
    assert feats["section_completeness_score"] >= 6


def test_parse_quality_score_complete(full_cv):
    feats = extract_features(full_cv)
    assert feats["parse_quality_score"] == 2  # "complete" → 2


def test_parse_quality_score_partial():
    cv = CVSchema(personal=PersonalInfo(full_name="Test"), parse_quality="partial")
    feats = extract_features(cv)
    assert feats["parse_quality_score"] == 1


# ── Career gap ──────────────────────────────────────────────────────────────

def test_career_gap_detected(cv_with_gap):
    feats = extract_features(cv_with_gap)
    # Gap between 2019-06 and 2020-07 = 13 months
    assert feats["career_gap_months"] >= 12


def test_no_career_gap_continuous(full_cv):
    feats = extract_features(full_cv)
    # full_cv has overlapping/continuous positions
    assert feats["career_gap_months"] >= 0  # can't be negative


# ── Interaction terms ───────────────────────────────────────────────────────

def test_experience_x_education_positive(full_cv):
    feats = extract_features(full_cv)
    assert feats["experience_x_education"] > 0


def test_experience_x_seniority_positive(full_cv):
    feats = extract_features(full_cv)
    assert feats["experience_x_seniority"] >= 0


# ── Distance feature ────────────────────────────────────────────────────────

def test_distance_km_unknown_returns_minus_one(minimal_cv):
    # minimal_cv has no address → distance = -1
    feats = extract_features(minimal_cv)
    assert feats["distance_km"] == -1.0


def test_distance_km_is_numeric(full_cv):
    feats = extract_features(full_cv)
    assert isinstance(feats["distance_km"], float)
