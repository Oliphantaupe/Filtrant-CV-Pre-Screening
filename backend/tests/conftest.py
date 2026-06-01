"""
Shared fixtures for all test modules.
Env vars must be set before any src.* import because Settings() runs at import time.
"""
import os
import pytest
from unittest.mock import patch, AsyncMock

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/testdb")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key")

from src.models.cv_schema import (
    CVSchema, PersonalInfo, Education, Experience,
    Skills, Language, Certification,
)


@pytest.fixture(autouse=True)
def mock_app_lifecycle():
    """Prevent init_db/close_db/watcher from running during tests.

    All tests that spin up TestClient(app) call the lifespan, which would
    otherwise try to connect to a real Postgres instance and start a
    file-watcher task. Patching these here keeps tests hermetic.
    """
    with (
        patch("src.main.init_db"),
        patch("src.main.close_db"),
        patch("src.main.watch_incoming", new=AsyncMock(return_value=None)),
    ):
        yield


@pytest.fixture
def minimal_cv() -> CVSchema:
    """CVSchema with the bare minimum — all optional fields empty."""
    return CVSchema(
        personal=PersonalInfo(full_name="Jean Dupont", email="jean@example.com"),
        parse_quality="complete",
    )


@pytest.fixture
def full_cv() -> CVSchema:
    """CVSchema with rich data covering all feature extraction paths."""
    return CVSchema(
        personal=PersonalInfo(
            full_name="Sophie Martin",
            email="sophie@example.com",
            phone="+352 621 000 000",
            address="Luxembourg-Ville, Luxembourg",
        ),
        target_role="Senior Data Engineer",
        summary="10 years of experience in data engineering and ML.",
        education=[
            Education(degree="Master", field="Computer Science",
                      institution="EPFL", year=2014, level_score=4),
            Education(degree="Bachelor", field="Mathematics",
                      institution="UCL", year=2012, level_score=3),
        ],
        experience=[
            Experience(title="Senior Data Engineer", company="Luxbank",
                       start="2020-01", end="present", duration_months=52),
            Experience(title="Data Engineer", company="Clearstream",
                       start="2016-03", end="2019-12", duration_months=45),
            Experience(title="Junior Analyst", company="PwC",
                       start="2014-09", end="2016-02", duration_months=17),
        ],
        skills=Skills(
            technical=["Python", "Spark", "SQL", "Kafka", "dbt"],
            methods=["Agile", "TDD"],
            management=["Team lead"],
        ),
        languages=[
            Language(language="French", level="C2", level_score=6),
            Language(language="English", level="C1", level_score=5),
            Language(language="German", level="B2", level_score=4),
        ],
        certifications=[
            Certification(name="AWS Solutions Architect", year=2021),
            Certification(name="Databricks Associate", year=2022),
        ],
        parse_quality="complete",
        missing_fields=[],
    )


@pytest.fixture
def senior_cv(full_cv) -> CVSchema:
    """full_cv with an explicitly senior title — tests has_senior_title."""
    full_cv.experience[0].title = "Lead Data Engineer"
    return full_cv


@pytest.fixture
def cv_with_gap() -> CVSchema:
    """CVSchema with a visible career gap between two positions."""
    return CVSchema(
        personal=PersonalInfo(full_name="Marc Becker"),
        experience=[
            Experience(title="Engineer", company="A", start="2018-01",
                       end="2019-06", duration_months=18),
            # 13-month gap
            Experience(title="Engineer", company="B", start="2020-07",
                       end="present", duration_months=24),
        ],
        parse_quality="partial",
    )
