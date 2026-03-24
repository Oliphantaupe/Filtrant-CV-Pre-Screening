"""
Text extraction from PDF, DOCX, and image files.
Returns raw text to be passed to the Claude parser.
"""
import hashlib
import io
from pathlib import Path

import pdfplumber
from docx import Document


SUPPORTED_FORMATS = {".pdf", ".docx", ".doc", ".txt"}


def extract_text(file_bytes: bytes, filename: str) -> tuple[str, str]:
    """Extract raw text from a CV file. Returns (text, format_detected)."""
    suffix = Path(filename).suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf(file_bytes), "pdf"
    elif suffix in (".docx", ".doc"):
        return _extract_docx(file_bytes), "docx"
    elif suffix == ".txt":
        return file_bytes.decode("utf-8", errors="replace"), "txt"
    else:
        raise ValueError(f"Unsupported file format: {suffix}")


def compute_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def _extract_pdf(file_bytes: bytes) -> str:
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    return "\n".join(text_parts)


def _extract_docx(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
