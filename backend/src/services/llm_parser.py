"""
Sends extracted CV text to Anthropic Claude and returns a validated CVSchema.
"""
import json
import logging

import anthropic

from src.config import settings
from src.models.cv_schema import CVSchema

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """You are a CV parser. Extract structured information from the CV text provided and return ONLY a valid JSON object matching this exact schema. Do not add any explanation or markdown — return raw JSON only.

Schema:
{
  "personal": { "full_name": str|null, "email": str|null, "phone": str|null, "address": str|null },
  "target_role": str|null,
  "summary": str|null,
  "education": [{ "degree": str|null, "field": str|null, "institution": str|null, "year": int|null, "level_score": int (1=high school,2=associate,3=bachelor,4=master,5=phd) }],
  "experience": [{ "title": str|null, "company": str|null, "start": "YYYY-MM"|null, "end": "YYYY-MM"|"present"|null, "duration_months": int|null }],
  "skills": { "technical": [str], "methods": [str], "management": [str] },
  "languages": [{ "language": str, "level": str|null, "level_score": int (1=A1..6=C2) }],
  "certifications": [{ "name": str, "year": int|null }],
  "parse_quality": "complete"|"partial"|"poor",
  "missing_fields": [str]
}

Rules:
- Compute duration_months whenever start is known: if end is "present" or not stated, compute months from start to today (2026-05). If start itself is unknown, set duration_months to null.
- List experience entries in reverse chronological order (most recent first).
- target_role: copy the exact job title from the CV if present; if absent, use the most recent job title; never rephrase or infer a broader role.
- Skills categorization: technical = tools, software, programming languages, platforms; methods = frameworks, methodologies, processes (e.g. Agile, BPMN); management = people or project leadership skills. Do not duplicate a skill across categories.
- Set parse_quality to "complete" if all main sections are present, "partial" if some are missing, "poor" if very little data.
- List any missing important fields in missing_fields.
- Return only the JSON object."""


async def parse_cv(raw_text: str) -> CVSchema:
    """
    Call Claude to parse raw CV text into a validated CVSchema.
    Uses prompt caching on the system prompt to reduce cost on batch uploads.
    """
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key, max_retries=4)

    message = await client.messages.create(
        model=MODEL,
        max_tokens=2048,
        temperature=0,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {"role": "user", "content": f"Parse this CV:\n\n{raw_text[:12000]}"}
        ],
    )

    raw_json = message.content[0].text.strip()

    if raw_json.startswith("```"):
        lines = raw_json.splitlines()
        raw_json = "\n".join(lines[1:-1]).strip()

    data = json.loads(raw_json)
    logger.debug("CV parsed successfully (parse_quality=%s)", data.get("parse_quality"))
    return CVSchema(**data)
