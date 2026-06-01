"""
Unit tests for src.services.extractor.
- compute_hash: pure function, no mocking.
- extract_text: mocks pdfplumber and python-docx for binary formats.
"""
import io
import pytest
from unittest.mock import MagicMock, patch

from src.services.extractor import compute_hash, extract_text


# ── compute_hash ─────────────────────────────────────────────────────────────

def test_compute_hash_returns_64_char_hex():
    h = compute_hash(b"hello world")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_compute_hash_deterministic():
    data = b"test content"
    assert compute_hash(data) == compute_hash(data)


def test_compute_hash_different_inputs_differ():
    assert compute_hash(b"aaa") != compute_hash(b"bbb")


def test_compute_hash_empty_bytes():
    h = compute_hash(b"")
    assert len(h) == 64  # SHA-256 of empty bytes is still valid


def test_compute_hash_known_value():
    # SHA-256("hello") known constant
    import hashlib
    expected = hashlib.sha256(b"hello").hexdigest()
    assert compute_hash(b"hello") == expected


# ── extract_text — TXT ───────────────────────────────────────────────────────

def test_extract_text_txt_returns_content():
    content = b"John Doe\nSoftware Engineer\nPython, SQL"
    text, fmt = extract_text(content, "resume.txt")
    assert "John Doe" in text
    assert fmt == "txt"


def test_extract_text_txt_uppercase_extension():
    content = b"John Doe"
    text, fmt = extract_text(content, "resume.TXT")
    assert "John Doe" in text
    assert fmt == "txt"


# ── extract_text — PDF ───────────────────────────────────────────────────────

def test_extract_text_pdf_uses_pdfplumber():
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Alice Engineer\nPython SQL"
    mock_pdf = MagicMock()
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    mock_pdf.pages = [mock_page]

    with patch("src.services.extractor.pdfplumber.open", return_value=mock_pdf):
        text, fmt = extract_text(b"%PDF fake", "cv.pdf")

    assert "Alice Engineer" in text
    assert fmt == "pdf"


def test_extract_text_pdf_multiple_pages():
    pages = []
    for i in range(3):
        page = MagicMock()
        page.extract_text.return_value = f"Page {i} content"
        pages.append(page)

    mock_pdf = MagicMock()
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    mock_pdf.pages = pages

    with patch("src.services.extractor.pdfplumber.open", return_value=mock_pdf):
        text, fmt = extract_text(b"%PDF fake", "cv.pdf")

    for i in range(3):
        assert f"Page {i} content" in text


def test_extract_text_pdf_skips_none_pages():
    p1, p2 = MagicMock(), MagicMock()
    p1.extract_text.return_value = "Page 1"
    p2.extract_text.return_value = None  # some pages return None

    mock_pdf = MagicMock()
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    mock_pdf.pages = [p1, p2]

    with patch("src.services.extractor.pdfplumber.open", return_value=mock_pdf):
        text, _ = extract_text(b"%PDF fake", "cv.pdf")

    assert "Page 1" in text


# ── extract_text — DOCX ──────────────────────────────────────────────────────

def test_extract_text_docx_uses_python_docx():
    mock_para = MagicMock()
    mock_para.text = "Bob Manager\nTeam Lead"
    mock_doc = MagicMock()
    mock_doc.paragraphs = [mock_para]

    with patch("src.services.extractor.Document", return_value=mock_doc):
        text, fmt = extract_text(b"PK fake docx", "cv.docx")

    assert "Bob Manager" in text
    assert fmt == "docx"


# ── extract_text — unsupported format ────────────────────────────────────────

def test_extract_text_unknown_format_raises():
    with pytest.raises(ValueError, match="[Uu]nsupported"):
        extract_text(b"some data", "cv.xyz")


def test_extract_text_no_extension_raises():
    with pytest.raises((ValueError, Exception)):
        extract_text(b"some data", "cv_no_ext")
