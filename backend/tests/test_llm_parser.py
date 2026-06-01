"""
Unit tests for src.services.llm_parser.
- clean_cv_text_for_llm: pure function, no mocking needed.
- parse_cv: Anthropic client is mocked.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.llm_parser import clean_cv_text_for_llm


# ── clean_cv_text_for_llm ────────────────────────────────────────────────────

def test_clean_removes_page_numbers():
    text = "Page 1 of 3\nExperience\nEngineer at ACME"
    cleaned = clean_cv_text_for_llm(text)
    assert "Page 1 of 3" not in cleaned
    assert "Engineer" in cleaned


def test_clean_removes_curriculum_vitae_header():
    text = "Curriculum Vitae\n\nExperience\nDeveloper at X\nSkills\nPython"
    cleaned = clean_cv_text_for_llm(text)
    assert "Curriculum Vitae" not in cleaned


def test_clean_removes_horizontal_rules():
    text = "Experience\n---\nDeveloper at X\n===\nEducation\nMSc Computer Science"
    cleaned = clean_cv_text_for_llm(text)
    assert "---" not in cleaned
    assert "===" not in cleaned
    assert "Developer" in cleaned


def test_clean_collapses_excess_blank_lines():
    text = "Experience\n\n\n\nDeveloper at X"
    cleaned = clean_cv_text_for_llm(text)
    assert "\n\n\n" not in cleaned


def test_clean_collapses_excess_spaces():
    text = "Experience\nDeveloper  at   ACME"
    cleaned = clean_cv_text_for_llm(text)
    assert "  " not in cleaned


def test_clean_returns_original_when_no_sections_detected():
    """Fallback: if no section headers found, return the original text stripped."""
    text = "John Doe\njohn@example.com\n+352 621 000 000"
    cleaned = clean_cv_text_for_llm(text)
    assert cleaned == text.strip()


def test_clean_preserves_content_with_sections():
    text = "Experience:\nSenior Engineer at Luxbank 2020-present\nSkills:\nPython SQL"
    cleaned = clean_cv_text_for_llm(text)
    assert "Senior Engineer" in cleaned
    assert "Python" in cleaned


def test_clean_handles_empty_string():
    assert clean_cv_text_for_llm("") == ""


def test_clean_handles_form_feed():
    text = "Experience\nDeveloper\x0cPage 2\nEducation\nMSc"
    cleaned = clean_cv_text_for_llm(text)
    assert "\x0c" not in cleaned


# ── parse_cv ─────────────────────────────────────────────────────────────────

def _make_cv_json_response(**overrides) -> str:
    base = {
        "personal": {
            "full_name": "Alice Tester",
            "email": "alice@test.com",
            "phone": None,
            "address": None,
        },
        "target_role": "Data Engineer",
        "summary": "Experienced engineer.",
        "education": [{"degree": "Master", "field": "CS",
                        "institution": "EPFL", "year": 2018, "level_score": 4}],
        "experience": [{"title": "Engineer", "company": "ACME",
                         "start": "2019-01", "end": "present",
                         "duration_months": 36}],
        "skills": {"technical": ["Python"], "methods": [], "management": []},
        "languages": [{"language": "English", "level": "C1", "level_score": 5}],
        "certifications": [],
        "parse_quality": "complete",
        "missing_fields": [],
    }
    base.update(overrides)
    return json.dumps(base)


def _mock_anthropic_response(content: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=content)]
    return msg


@pytest.mark.asyncio
async def test_parse_cv_returns_cv_schema():
    from src.services.llm_parser import parse_cv

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(
        return_value=_mock_anthropic_response(_make_cv_json_response())
    )

    with patch("src.services.llm_parser.anthropic.AsyncAnthropic",
               return_value=mock_client):
        result = await parse_cv("Some CV text here")

    assert result.personal.full_name == "Alice Tester"
    assert result.personal.email == "alice@test.com"
    assert result.parse_quality == "complete"
    assert len(result.experience) == 1
    assert result.experience[0].title == "Engineer"


@pytest.mark.asyncio
async def test_parse_cv_strips_markdown_fences():
    from src.services.llm_parser import parse_cv

    content_with_fences = f"```json\n{_make_cv_json_response()}\n```"
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(
        return_value=_mock_anthropic_response(content_with_fences)
    )

    with patch("src.services.llm_parser.anthropic.AsyncAnthropic",
               return_value=mock_client):
        result = await parse_cv("Some CV text")

    assert result.personal.full_name == "Alice Tester"


@pytest.mark.asyncio
async def test_parse_cv_raises_on_invalid_json():
    from src.services.llm_parser import parse_cv

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(
        return_value=_mock_anthropic_response("not valid json at all")
    )

    with patch("src.services.llm_parser.anthropic.AsyncAnthropic",
               return_value=mock_client):
        with pytest.raises(Exception):
            await parse_cv("Some CV text")


@pytest.mark.asyncio
async def test_parse_cv_truncates_long_input():
    """Verify that very long input is sent truncated (≤12000 chars)."""
    from src.services.llm_parser import parse_cv

    long_text = "x" * 50_000

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(
        return_value=_mock_anthropic_response(_make_cv_json_response())
    )

    with patch("src.services.llm_parser.anthropic.AsyncAnthropic",
               return_value=mock_client):
        await parse_cv(long_text)

    call_args = mock_client.messages.create.call_args
    user_message = call_args.kwargs["messages"][0]["content"]
    assert len(user_message) <= 12100  # 12000 chars + "Parse this CV:\n\n" prefix
