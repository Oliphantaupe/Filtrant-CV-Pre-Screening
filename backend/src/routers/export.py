import csv
import io
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from src.db import get_conn
from src.services.features import extract_features, FEATURE_COLUMNS
from src.models.cv_schema import CVSchema

router = APIRouter(prefix="/api/v1", tags=["candidates"])


@router.get("/candidates")
def list_candidates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    recommendation: str | None = Query(None),
    date_from: str | None = Query(None, description="YYYY-MM-DD — inclusive start date"),
    date_to: str | None = Query(None, description="YYYY-MM-DD — inclusive end date"),
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

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
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
                ORDER BY processed_at DESC
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
                       parse_quality, recommendation, confidence, cv_data, missing_fields
                FROM candidates WHERE id = %s
                """,
                (candidate_id,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Candidate not found")

    cols = ["id", "processed_at", "source_filename", "source_format",
            "parse_quality", "recommendation", "confidence", "cv_data", "missing_fields"]
    result = dict(zip(cols, row))
    if result["processed_at"]:
        result["processed_at"] = result["processed_at"].isoformat()
    return result
