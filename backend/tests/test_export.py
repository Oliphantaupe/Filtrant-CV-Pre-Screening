"""
API endpoint tests for:
  GET  /api/v1/candidates
  GET  /api/v1/candidates/{id}
  POST /api/v1/candidates/{id}/override
  GET  /api/v1/health
"""
import json
import pytest
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from src.main import app


# ── DB mock helpers ───────────────────────────────────────────────────────────

def _cursor_mock(rows=None, count=0, fetchone_return=None):
    cur = MagicMock()
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)
    cur.fetchall.return_value = rows or []
    cur.fetchone.return_value = fetchone_return or (count,)
    cur.description = []
    return cur


def _conn_mock(cursor):
    conn = MagicMock()
    conn.cursor.return_value = cursor
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)

    @contextmanager
    def _get_conn():
        yield conn

    return _get_conn


def _now_iso():
    return datetime.now(timezone.utc)


def _candidate_row():
    """Fake DB row matching the list_candidates SELECT column order."""
    return (
        "uuid-1234",                  # id
        _now_iso(),                   # processed_at
        "cv.pdf",                     # source_filename
        "pdf",                        # source_format
        "complete",                   # parse_quality
        "Invite",                     # recommendation
        0.87,                         # confidence
        "Reject",                     # recommendation_base
        0.42,                         # confidence_base
        None,                         # hr_decision
        None,                         # override_reason
        None,                         # overridden_at
        "Alice Tester",               # name
        "alice@test.com",             # email
        "Data Engineer",              # target_role
    )


def _detail_row():
    """Fake DB row matching the get_candidate SELECT column order."""
    cv_data = {
        "personal": {"full_name": "Alice Tester", "email": "alice@test.com",
                     "phone": None, "address": None},
        "target_role": "Data Engineer",
        "summary": None, "education": [], "experience": [],
        "skills": {"technical": [], "methods": [], "management": []},
        "languages": [], "certifications": [],
        "parse_quality": "complete", "missing_fields": [],
    }
    return (
        "uuid-1234", _now_iso(), "cv.pdf", "pdf", "complete",
        "Invite", 0.87, cv_data, json.dumps([]),
        None, None, None, None,
        "Reject", 0.42, None,
    )


# ── GET /candidates ───────────────────────────────────────────────────────────

def test_list_candidates_returns_200():
    row = _candidate_row()
    cols = ["id", "processed_at", "source_filename", "source_format",
            "parse_quality", "recommendation", "confidence",
            "recommendation_base", "confidence_base",
            "hr_decision", "override_reason", "overridden_at",
            "name", "email", "target_role"]
    cur = _cursor_mock(rows=[row], fetchone_return=(1,))
    cur.description = [(c,) for c in cols]

    with patch("src.routers.export.get_conn", _conn_mock(cur)):
        with TestClient(app) as client:
            resp = client.get("/api/v1/candidates")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1


def test_list_candidates_item_has_expected_fields():
    row = _candidate_row()
    cols = ["id", "processed_at", "source_filename", "source_format",
            "parse_quality", "recommendation", "confidence",
            "recommendation_base", "confidence_base",
            "hr_decision", "override_reason", "overridden_at",
            "name", "email", "target_role"]
    cur = _cursor_mock(rows=[row], fetchone_return=(1,))
    cur.description = [(c,) for c in cols]

    with patch("src.routers.export.get_conn", _conn_mock(cur)):
        with TestClient(app) as client:
            resp = client.get("/api/v1/candidates")

    item = resp.json()["items"][0]
    assert item["id"] == "uuid-1234"
    assert item["recommendation"] == "Invite"
    assert item["recommendation_base"] == "Reject"
    assert item["name"] == "Alice Tester"


def test_list_candidates_empty_db():
    cur = _cursor_mock(rows=[], fetchone_return=(0,))
    cur.description = []

    with patch("src.routers.export.get_conn", _conn_mock(cur)):
        with TestClient(app) as client:
            resp = client.get("/api/v1/candidates")

    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert resp.json()["items"] == []


def test_list_candidates_pagination_params():
    cur = _cursor_mock(rows=[], fetchone_return=(0,))
    cur.description = []

    with patch("src.routers.export.get_conn", _conn_mock(cur)):
        with TestClient(app) as client:
            resp = client.get("/api/v1/candidates?page=2&page_size=10")

    assert resp.status_code == 200
    assert resp.json()["page"] == 2
    assert resp.json()["page_size"] == 10


# ── GET /candidates/{id} ──────────────────────────────────────────────────────

def test_get_candidate_returns_200():
    cols = ["id", "processed_at", "source_filename", "source_format",
            "parse_quality", "recommendation", "confidence", "cv_data",
            "missing_fields", "explanation", "hr_decision",
            "override_reason", "overridden_at",
            "recommendation_base", "confidence_base", "explanation_base"]
    cur = _cursor_mock(fetchone_return=_detail_row())
    cur.description = [(c,) for c in cols]
    cur.fetchone.return_value = _detail_row()

    with patch("src.routers.export.get_conn", _conn_mock(cur)):
        with TestClient(app) as client:
            resp = client.get("/api/v1/candidates/uuid-1234")

    assert resp.status_code == 200
    assert resp.json()["id"] == "uuid-1234"
    assert resp.json()["recommendation"] == "Invite"


def test_get_candidate_not_found_returns_404():
    cur = _cursor_mock(fetchone_return=None)
    cur.fetchone.return_value = None

    with patch("src.routers.export.get_conn", _conn_mock(cur)):
        with TestClient(app) as client:
            resp = client.get("/api/v1/candidates/does-not-exist")

    assert resp.status_code == 404


# ── POST /candidates/{id}/override ───────────────────────────────────────────

def test_override_invite_returns_200():
    cur = _cursor_mock(fetchone_return=("uuid-1234",))

    with patch("src.routers.export.get_conn", _conn_mock(cur)):
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/candidates/uuid-1234/override",
                json={"hr_decision": "Invite",
                      "override_reason": "Strong referral"},
            )

    assert resp.status_code == 200
    assert resp.json()["hr_decision"] == "Invite"


def test_override_reject_returns_200():
    cur = _cursor_mock(fetchone_return=("uuid-1234",))

    with patch("src.routers.export.get_conn", _conn_mock(cur)):
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/candidates/uuid-1234/override",
                json={"hr_decision": "Reject",
                      "override_reason": "Missing required certification"},
            )

    assert resp.status_code == 200
    assert resp.json()["hr_decision"] == "Reject"


def test_override_invalid_decision_returns_400():
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/candidates/uuid-1234/override",
            json={"hr_decision": "Maybe", "override_reason": "Unsure"},
        )
    assert resp.status_code == 400


def test_override_empty_reason_returns_400():
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/candidates/uuid-1234/override",
            json={"hr_decision": "Invite", "override_reason": "   "},
        )
    assert resp.status_code == 400


def test_override_nonexistent_candidate_returns_404():
    cur = _cursor_mock(fetchone_return=None)
    cur.fetchone.return_value = None

    with patch("src.routers.export.get_conn", _conn_mock(cur)):
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/candidates/ghost-id/override",
                json={"hr_decision": "Invite", "override_reason": "Test"},
            )

    assert resp.status_code == 404


# ── GET /health ───────────────────────────────────────────────────────────────

def test_health_check_returns_200():
    cur = _cursor_mock(fetchone_return=(1,))
    with (
        patch("src.db.init_db"),           # skip DB connection on startup
        patch("src.db.close_db"),          # skip DB teardown on shutdown
        patch("src.db.get_conn", _conn_mock(cur)),
    ):
        with TestClient(app) as client:
            resp = client.get("/api/v1/health")
    assert resp.status_code == 200
