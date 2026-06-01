"""
API endpoint tests for POST /api/v1/upload.
DB, LLM parser, predictor, and file extractor are all mocked.
"""
import io
import json
import pytest
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from src.main import app

from src.models.cv_schema import CVSchema, PersonalInfo, Experience, Skills, Language


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_cv() -> CVSchema:
    return CVSchema(
        personal=PersonalInfo(full_name="Test User", email="test@example.com"),
        target_role="Engineer",
        experience=[Experience(title="Engineer", company="X",
                               start="2020-01", end="present", duration_months=24)],
        parse_quality="complete",
    )


def _mock_db_conn(existing_hash=None):
    """Return a mock context manager for get_conn() that simulates DB operations."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchone.return_value = existing_hash  # None = not a duplicate
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)

    @contextmanager
    def _get_conn():
        yield mock_conn

    return _get_conn


def _upload_file(client: TestClient, content: bytes = b"CV content",
                 filename: str = "cv.txt") -> dict:
    return client.post(
        "/api/v1/upload",
        files={"file": (filename, io.BytesIO(content), "text/plain")},
    )


# ── Successful upload ────────────────────────────────────────────────────────

def test_upload_success_returns_201():
    cv = _make_cv()
    with (
        patch("src.routers.upload.extract_text", return_value=("CV text", "txt")),
        patch("src.routers.upload.compute_hash", return_value="a" * 64),
        patch("src.routers.upload.parse_cv", new=AsyncMock(return_value=cv)),
        patch("src.routers.upload.predict", return_value=("Invite", 0.85, None)),
        patch("src.routers.upload.get_conn", _mock_db_conn()),
    ):
        with TestClient(app) as client:
            resp = _upload_file(client)

    assert resp.status_code == 201


def test_upload_success_response_fields():
    cv = _make_cv()
    with (
        patch("src.routers.upload.extract_text", return_value=("CV text", "txt")),
        patch("src.routers.upload.compute_hash", return_value="b" * 64),
        patch("src.routers.upload.parse_cv", new=AsyncMock(return_value=cv)),
        patch("src.routers.upload.predict", side_effect=[
            ("Invite", 0.85, {"positive": [], "negative": []}),  # fair
            ("Reject", 0.60, None),                               # base
        ]),
        patch("src.routers.upload.get_conn", _mock_db_conn()),
    ):
        with TestClient(app) as client:
            resp = _upload_file(client)

    body = resp.json()
    assert "id" in body
    assert body["recommendation"] == "Invite"
    assert body["confidence"] == pytest.approx(0.85)
    assert body["recommendation_base"] == "Reject"
    assert body["parse_quality"] == "complete"


def test_upload_calls_both_models():
    """predict() must be called twice — once for fair, once for base."""
    cv = _make_cv()
    mock_predict = MagicMock(return_value=("Invite", 0.8, None))

    with (
        patch("src.routers.upload.extract_text", return_value=("CV text", "txt")),
        patch("src.routers.upload.compute_hash", return_value="c" * 64),
        patch("src.routers.upload.parse_cv", new=AsyncMock(return_value=cv)),
        patch("src.routers.upload.predict", mock_predict),
        patch("src.routers.upload.get_conn", _mock_db_conn()),
    ):
        with TestClient(app) as client:
            _upload_file(client)

    assert mock_predict.call_count == 2
    calls = [c.kwargs.get("model") or c.args[1] for c in mock_predict.call_args_list]
    assert "fair" in calls
    assert "base" in calls


# ── Duplicate detection ──────────────────────────────────────────────────────

def test_upload_duplicate_returns_409():
    existing_row = ("existing-uuid",)  # fetchone returns a row → duplicate
    with (
        patch("src.routers.upload.extract_text", return_value=("CV text", "txt")),
        patch("src.routers.upload.compute_hash", return_value="d" * 64),
        patch("src.routers.upload.get_conn", _mock_db_conn(existing_hash=existing_row)),
    ):
        with TestClient(app) as client:
            resp = _upload_file(client)

    assert resp.status_code == 409
    assert "already been processed" in resp.json()["detail"]


# ── Validation errors ────────────────────────────────────────────────────────

def test_upload_empty_file_returns_400():
    with (
        patch("src.routers.upload.extract_text", return_value=("CV text", "txt")),
        patch("src.routers.upload.compute_hash", return_value="e" * 64),
        patch("src.routers.upload.get_conn", _mock_db_conn()),
    ):
        with TestClient(app) as client:
            resp = _upload_file(client, content=b"")

    assert resp.status_code == 400


def test_upload_file_too_large_returns_413():
    big_content = b"x" * (6 * 1024 * 1024)  # 6 MB > 5 MB limit
    with TestClient(app) as client:
        resp = _upload_file(client, content=big_content)
    assert resp.status_code == 413


def test_upload_unsupported_format_returns_400():
    with (
        patch("src.routers.upload.extract_text",
              side_effect=ValueError("Unsupported format")),
        patch("src.routers.upload.compute_hash", return_value="f" * 64),
        patch("src.routers.upload.get_conn", _mock_db_conn()),
    ):
        with TestClient(app) as client:
            resp = _upload_file(client, content=b"data", filename="cv.xyz")

    assert resp.status_code == 400


def test_upload_empty_text_after_extraction_returns_422():
    with (
        patch("src.routers.upload.extract_text", return_value=("   ", "txt")),
        patch("src.routers.upload.compute_hash", return_value="g" * 64),
        patch("src.routers.upload.get_conn", _mock_db_conn()),
    ):
        with TestClient(app) as client:
            resp = _upload_file(client)

    assert resp.status_code == 422


# ── LLM failure ──────────────────────────────────────────────────────────────

def test_upload_llm_failure_returns_502():
    with (
        patch("src.routers.upload.extract_text", return_value=("CV text", "txt")),
        patch("src.routers.upload.compute_hash", return_value="h" * 64),
        patch("src.routers.upload.parse_cv",
              new=AsyncMock(side_effect=Exception("LLM error"))),
        patch("src.routers.upload.get_conn", _mock_db_conn()),
    ):
        with TestClient(app) as client:
            resp = _upload_file(client)

    assert resp.status_code == 502
