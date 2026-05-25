import csv
import io
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from src.db import get_conn
from src.services.features import extract_features, FEATURE_COLUMNS
from src.models.cv_schema import CVSchema

router = APIRouter(prefix="/api/v1", tags=["candidates"])

FAIRNESS_REPORT_PATH = Path(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ml", "fairness_report.json"))


class OverrideRequest(BaseModel):
    hr_decision: str       # "Invite" | "Reject"
    override_reason: str


@router.get("/candidates")
def list_candidates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    recommendation: str | None = Query(None),
    date_from: str | None = Query(None, description="YYYY-MM-DD — inclusive start date"),
    date_to: str | None = Query(None, description="YYYY-MM-DD — inclusive end date"),
    search: str | None = Query(None),
    sort_by: str | None = Query('date_desc'),
):
    offset = (page - 1) * page_size
    filters = []
    params = []

    if recommendation:
        filters.append("recommendation = %s")
        params.append(recommendation)
    if date_from:
        filters.append("(processed_at AT TIME ZONE 'UTC')::date >= %s")
        params.append(date_from)
    if date_to:
        filters.append("(processed_at AT TIME ZONE 'UTC')::date <= %s")
        params.append(date_to)
    if search:
        filters.append("(cv_data->'personal'->>'full_name' ILIKE %s OR cv_data->>'target_role' ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    
    order_clause = "ORDER BY "
    is_confidence_sort = sort_by in ('confidence_desc', 'confidence_asc')
    if not recommendation and is_confidence_sort:
        order_clause += "CASE WHEN recommendation = 'Invite' THEN 1 ELSE 2 END ASC, "

    if sort_by == 'confidence_desc':
        order_clause += "confidence DESC NULLS LAST"
    elif sort_by == 'confidence_asc':
        order_clause += "confidence ASC NULLS LAST"
    elif sort_by == 'date_asc':
        order_clause += "processed_at ASC, id ASC"
    else:
        order_clause += "processed_at DESC, id DESC"
    params += [page_size, offset]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, processed_at, source_filename, source_format,
                       parse_quality, recommendation, confidence,
                       cv_data->'personal'->>'full_name' AS name,
                       cv_data->'personal'->>'email' AS email,
                       cv_data->>'target_role' AS target_role
                FROM candidates
                {where}
                {order_clause}
                LIMIT %s OFFSET %s
                """,
                params,
            )
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            cur.execute(f"SELECT COUNT(*) FROM candidates {where}", params[:-2])
            total = cur.fetchone()[0]

    candidates = [dict(zip(cols, row)) for row in rows]
    for c in candidates:
        if c["processed_at"]:
            c["processed_at"] = c["processed_at"].isoformat()

    return {"total": total, "page": page, "page_size": page_size, "items": candidates}


@router.get("/candidates/export.csv")
def export_csv():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, cv_data, recommendation FROM candidates")
            rows = cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id"] + FEATURE_COLUMNS + ["recommendation"])

    for row_id, cv_data, recommendation in rows:
        try:
            cv = CVSchema(**cv_data)
            features = extract_features(cv)
            writer.writerow([row_id] + [features[c] for c in FEATURE_COLUMNS] + [recommendation])
        except Exception:
            continue

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=candidates.csv"},
    )


@router.get("/candidates/{candidate_id}")
def get_candidate(candidate_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, processed_at, source_filename, source_format,
                       parse_quality, recommendation, confidence, cv_data, missing_fields,
                       explanation, hr_decision, override_reason, overridden_at
                FROM candidates WHERE id = %s
                """,
                (candidate_id,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Candidate not found")

    cols = ["id", "processed_at", "source_filename", "source_format",
            "parse_quality", "recommendation", "confidence", "cv_data", "missing_fields",
            "explanation", "hr_decision", "override_reason", "overridden_at"]
    result = dict(zip(cols, row))
    if result["processed_at"]:
        result["processed_at"] = result["processed_at"].isoformat()
    if result["overridden_at"]:
        result["overridden_at"] = result["overridden_at"].isoformat()
    return result


@router.post("/candidates/{candidate_id}/override")
def override_decision(candidate_id: str, body: OverrideRequest):
    if body.hr_decision not in ("Invite", "Reject"):
        raise HTTPException(status_code=400, detail="hr_decision must be 'Invite' or 'Reject'")
    if not body.override_reason.strip():
        raise HTTPException(status_code=400, detail="override_reason is required")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM candidates WHERE id = %s", (candidate_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Candidate not found")
            cur.execute(
                """
                UPDATE candidates
                SET hr_decision = %s, override_reason = %s, overridden_at = NOW()
                WHERE id = %s
                """,
                (body.hr_decision, body.override_reason.strip(), candidate_id),
            )
            # AI Act Art. 14 — human override must be traceable in the audit log
            cur.execute(
                "INSERT INTO processing_log (candidate_id, event, detail) VALUES (%s, %s, %s)",
                (candidate_id, "hr_override", f"{body.hr_decision} — {body.override_reason.strip()}"),
            )
        conn.commit()
    return {"status": "ok", "hr_decision": body.hr_decision}


@router.get("/fairness/metrics")
def get_fairness_metrics():
    if not FAIRNESS_REPORT_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Fairness report not found. Run train_fair.py first.",
        )
    return json.loads(FAIRNESS_REPORT_PATH.read_text())
