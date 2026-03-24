"""
Sends extracted CV text to the Claude API and returns a validated CVSchema.
Client is lazy-initialised so a bad key doesn't crash the app at startup.
"""
import asyncio
import json
import logging
import anthropic

from src.config import settings
from src.models.cv_schema import CVSchema

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None

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


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


async def parse_cv(raw_text: str, max_retries: int = 2) -> CVSchema:
    """
    Call Claude API to parse raw CV text into a validated CVSchema.
    Retries up to max_retries times on rate-limit (429) or overload (529) errors.
    """
    client = _get_client()

    for attempt in range(max_retries + 1):
        try:
            message = await asyncio.to_thread(
                client.messages.create,
                model="claude-haiku-4-5-20251001",
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": f"Parse this CV:\n\n{raw_text[:12000]}",
                    }
                ],
            )
        except anthropic.RateLimitError:
            if attempt < max_retries:
                wait = 2 ** attempt
                logger.warning("Claude rate-limited, retrying in %ss (attempt %d)", wait, attempt + 1)
                await asyncio.sleep(wait)
                continue
            raise
        except anthropic.APIStatusError as e:
            if attempt < max_retries and e.status_code in (529,):
                wait = 2 ** attempt
                logger.warning("Claude overloaded (%s), retrying in %ss", e.status_code, wait)
                await asyncio.sleep(wait)
                continue
            raise

        raw_json = message.content[0].text.strip()

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

    raise RuntimeError("Claude parsing failed after all retries")
