"""
Sends extracted CV text to Anthropic API (Claude Haiku 4.5) and returns a validated CVSchema.
Client is lazy-initialised so a bad key doesn't crash the app at startup.
"""
import asyncio
import json
import logging
import httpx

from src.config import settings
from src.models.cv_schema import CVSchema

logger = logging.getLogger(__name__)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
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
- Compute duration_months from start/end if possible.
- Set parse_quality to "complete" if all main sections are present, "partial" if some are missing, "poor" if very little data.
- List any missing important fields in missing_fields.
- Return only the JSON object."""


async def parse_cv(raw_text: str, max_retries: int = 2) -> CVSchema:
    """
    Call Anthropic API (Claude Haiku 4.5) to parse raw CV text into a validated CVSchema.
    Retries up to max_retries times on rate-limit (429) or server errors (5xx).
    """
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "max_tokens": 4096,
        "system": SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": f"Parse this CV:\n\n{raw_text[:12000]}"},
        ],
        "temperature": 0,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        for attempt in range(max_retries + 1):
            try:
                response = await client.post(ANTHROPIC_URL, headers=headers, json=payload)
            except httpx.TimeoutException:
                if attempt < max_retries:
                    wait = 2 ** attempt
                    logger.warning("Anthropic timeout, retrying in %ss (attempt %d)", wait, attempt + 1)
                    await asyncio.sleep(wait)
                    continue
                raise

            if response.status_code == 429 or response.status_code >= 500:
                if attempt < max_retries:
                    wait = 2 ** attempt
                    logger.warning("Anthropic %s, retrying in %ss (attempt %d)", response.status_code, wait, attempt + 1)
                    await asyncio.sleep(wait)
                    continue
                response.raise_for_status()

            response.raise_for_status()

            raw_json = response.json()["content"][0]["text"].strip()

            # Strip markdown code fences if present (e.g. ```json ... ```)
            if raw_json.startswith("```"):
                lines = raw_json.splitlines()
                raw_json = "\n".join(lines[1:-1]).strip()

            try:
                data = json.loads(raw_json)
            except json.JSONDecodeError as e:
                logger.error("Claude returned invalid JSON on attempt %d: %s", attempt + 1, e)
                if attempt < max_retries:
                    continue
                raise

            logger.debug("CV parsed successfully (parse_quality=%s)", data.get("parse_quality"))
            return CVSchema(**data)

    raise RuntimeError("CV parsing failed after all retries")
