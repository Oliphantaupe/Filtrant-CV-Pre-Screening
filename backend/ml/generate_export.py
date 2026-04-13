"""
Script autonome — parse les CVs locaux et génère candidates_export.csv avec 15 features.
Appelle OpenRouter directement, sans Docker.

Usage:
    python generate_export.py
"""

import asyncio
import csv
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import httpx

# ── Config ───────────────────────────────────────────────────────────────────
BASE = Path(__file__).parent
CVDIR = BASE.parent.parent / "CVs"
LABELS_PATH = BASE.parent.parent / "student_labels.csv"
OUT_PATH = BASE / "candidates_export.csv"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-2.0-flash-001"
API_KEY = "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"

FEATURE_COLUMNS = [
    "total_years_experience", "num_positions", "avg_tenure_months",
    "education_level_score", "total_skills_count", "has_certifications",
    "language_count", "section_completeness_score",
    "max_language_score", "has_senior_title", "career_gap_months",
    "latest_job_duration", "has_summary", "num_certifications",
    "parse_quality_score",
]

SENIORITY_KEYWORDS = {"senior", "lead", "manager", "head", "director", "principal", "chief", "vp", "president"}

EDU_LEVELS = {
    "high school": 1, "bac": 1, "lycée": 1,
    "associate": 2, "bts": 2, "dut": 2,
    "bachelor": 3, "licence": 3, "undergraduate": 3,
    "master": 4, "mba": 4, "graduate": 4,
    "phd": 5, "doctorate": 5, "doctorat": 5,
}

LANG_LEVELS = {"a1": 1, "a2": 2, "b1": 3, "b2": 4, "c1": 5, "c2": 6,
               "native": 6, "fluent": 5, "professional": 4, "intermediate": 3, "basic": 2}

SYSTEM_PROMPT = """You are a CV parser. Extract structured data from a CV and return ONLY valid JSON.

Return this exact structure:
{
  "full_name": "",
  "email": "",
  "summary": "",
  "education": [{"degree": "", "field": "", "institution": "", "year": null}],
  "experience": [{"title": "", "company": "", "start": "YYYY-MM", "end": "YYYY-MM or present", "duration_months": null}],
  "skills": {"technical": [], "methods": [], "management": []},
  "languages": [{"name": "", "level": ""}],
  "certifications": [],
  "parse_quality": "complete|partial|poor"
}

For duration_months: calculate from start/end dates if possible.
Return ONLY the JSON object, no markdown, no explanation."""


async def call_api(text: str, client: httpx.AsyncClient) -> dict:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse this CV:\n\n{text[:10000]}"},
        ],
        "temperature": 0,
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://filtrant.app",
        "X-Title": "Filtrant CV Screening",
    }
    for attempt in range(3):
        try:
            r = await client.post(OPENROUTER_URL, headers=headers, json=payload)
            if r.status_code == 429:
                await asyncio.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"].strip()
            # Strip markdown fences if present
            content = re.sub(r"^```json?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
            return json.loads(content)
        except Exception as e:
            if attempt == 2:
                raise
            await asyncio.sleep(2)
    raise RuntimeError("API failed after 3 attempts")


def edu_score(education: list) -> int:
    best = 1
    for e in education:
        degree = (e.get("degree") or "").lower()
        for kw, score in EDU_LEVELS.items():
            if kw in degree and score > best:
                best = score
    return best


def lang_score(level: str) -> int:
    level = (level or "").lower().strip()
    for kw, score in LANG_LEVELS.items():
        if kw in level:
            return score
    return 1


def compute_gap(experience: list) -> int:
    dated = []
    for e in experience:
        s = e.get("start")
        if not s:
            continue
        try:
            start = datetime.strptime(s[:7], "%Y-%m")
            end_raw = e.get("end", "present")
            if end_raw and end_raw != "present":
                end = datetime.strptime(end_raw[:7], "%Y-%m")
            else:
                end = datetime.now().replace(day=1)
            dated.append((start, end))
        except ValueError:
            continue
    if len(dated) < 2:
        return 0
    dated.sort(key=lambda x: x[0])
    gap = 0
    for i in range(1, len(dated)):
        diff = (dated[i][0].year - dated[i-1][1].year) * 12 + \
               (dated[i][0].month - dated[i-1][1].month)
        if diff > 0:
            gap += diff
    return gap


def extract_features(parsed: dict) -> dict:
    exp = parsed.get("experience") or []
    edu = parsed.get("education") or []
    skills = parsed.get("skills") or {}
    langs = parsed.get("languages") or []
    certs = parsed.get("certifications") or []

    durations = [e.get("duration_months") or 0 for e in exp]
    total_months = sum(d for d in durations if d)
    total_years = round(total_months / 12, 2)
    num_pos = len(exp)
    avg_tenure = round(total_months / num_pos, 1) if num_pos else 0.0

    tech = skills.get("technical") or []
    methods = skills.get("methods") or []
    mgmt = skills.get("management") or []
    total_skills = len(tech) + len(methods) + len(mgmt)

    sections = [
        bool(parsed.get("full_name") or parsed.get("email")),
        bool(parsed.get("summary")),
        bool(edu),
        bool(exp),
        bool(tech or methods),
        bool(langs),
    ]

    max_lang = max((lang_score(l.get("level", "")) for l in langs), default=0)

    has_senior = int(any(
        kw in (e.get("title") or "").lower()
        for e in exp for kw in SENIORITY_KEYWORDS
    ))

    latest_dur = durations[0] if durations else 0

    summary = parsed.get("summary") or ""
    has_summary = 1 if len(summary.strip()) > 20 else 0

    parse_qual = {"complete": 2, "partial": 1, "poor": 0}.get(
        parsed.get("parse_quality", "partial"), 1)

    return {
        "total_years_experience": total_years,
        "num_positions": num_pos,
        "avg_tenure_months": avg_tenure,
        "education_level_score": edu_score(edu),
        "total_skills_count": total_skills,
        "has_certifications": 1 if certs else 0,
        "language_count": len(langs),
        "section_completeness_score": sum(sections),
        "max_language_score": max_lang,
        "has_senior_title": has_senior,
        "career_gap_months": compute_gap(exp),
        "latest_job_duration": latest_dur,
        "has_summary": has_summary,
        "num_certifications": len(certs),
        "parse_quality_score": parse_qual,
    }


async def main():
    # Load labels
    labels = {}
    with open(LABELS_PATH) as f:
        for row in csv.DictReader(f):
            label = "Invite" if row["passed_next_stage"].strip() == "1" else "Reject"
            labels[row["filename"].strip()] = label

    print(f"Labels: {len(labels)} | Invite={sum(1 for v in labels.values() if v=='Invite')} | Reject={sum(1 for v in labels.values() if v=='Reject')}")

    files = sorted(CVDIR.glob("*.txt"))
    results = []
    errors = 0

    async with httpx.AsyncClient(timeout=60.0) as client:
        for i, cv_path in enumerate(files):
            label = labels.get(cv_path.name)
            if not label:
                continue
            raw = cv_path.read_text(encoding="utf-8")
            try:
                parsed = await call_api(raw, client)
                feats = extract_features(parsed)
                feats["recommendation"] = label
                results.append(feats)
                if (i + 1) % 20 == 0 or (i + 1) == len(files):
                    print(f"  [{i+1}/{len(files)}] {len(results)} OK, {errors} ERR")
            except Exception as e:
                errors += 1
                print(f"  [{i+1}] ERR {cv_path.name}: {e}")
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.5)

    cols = FEATURE_COLUMNS + ["recommendation"]
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(results)

    invite = sum(1 for r in results if r["recommendation"] == "Invite")
    reject = sum(1 for r in results if r["recommendation"] == "Reject")
    print(f"\nDone! {len(results)} CVs → {OUT_PATH}")
    print(f"  Invite={invite} | Reject={reject} | Errors={errors}")


if __name__ == "__main__":
    asyncio.run(main())
