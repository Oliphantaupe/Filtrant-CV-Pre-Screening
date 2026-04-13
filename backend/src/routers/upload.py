import json
import logging
import uuid

from fastapi import APIRouter, UploadFile, File, HTTPException

from src.config import settings
from src.db import get_conn
from src.services.extractor import extract_text, compute_hash
from src.services.llm_parser import parse_cv
from src.services.features import extract_features
from src.services.predictor import predict

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["upload"])


async def _process_cv_bytes(file_bytes: bytes, filename: str) -> dict:
    """Core CV processing logic."""
    if len(file_bytes) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {settings.max_file_size_mb} MB.",
        )
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        raw_text, fmt = extract_text(file_bytes, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not raw_text.strip():
        raise HTTPException(status_code=422, detail="No readable text found in the file.")

    file_hash = compute_hash(file_bytes)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM candidates WHERE file_hash = %s", (file_hash,))
            existing = cur.fetchone()
        if existing:
            logger.info("Duplicate upload rejected: %s (hash=%s)", filename, file_hash[:12])
            raise HTTPException(status_code=409, detail="This CV has already been processed.")

    candidate_id = str(uuid.uuid4())

    try:
        cv = await parse_cv(raw_text)
        logger.info(
            "Parsed [%s] %s — quality=%s missing=%d",
            candidate_id[:8], filename, cv.parse_quality, len(cv.missing_fields),
        )
    except Exception as e:
        logger.error("Claude parse failed for %s: %s", filename, e)
        _log_event(candidate_id, "parse_failed", str(e), filename, fmt, file_hash)
        raise HTTPException(status_code=502, detail=f"CV parsing failed: {e}")

    features = extract_features(cv)
    recommendation, confidence = predict(features)
    logger.info(
        "Prediction [%s]: %s (confidence=%.3f)",
        candidate_id[:8], recommendation, confidence or 0,
    )

    cv_dict = cv.model_dump()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO candidates
                    (id, source_filename, source_format, parse_quality,
                     cv_data, recommendation, confidence, file_hash, missing_fields)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    candidate_id, filename, fmt, cv.parse_quality,
                    json.dumps(cv_dict), recommendation, confidence,
                    file_hash, json.dumps(cv.missing_fields),
                ),
            )
            cur.execute(
                "INSERT INTO processing_log (candidate_id, event, detail) VALUES (%s, %s, %s)",
                (candidate_id, "uploaded",
                 f"format={fmt} quality={cv.parse_quality} prediction={recommendation}"),
            )
        conn.commit()

    return {
        "id": candidate_id,
        "name": cv.personal.full_name,
        "target_role": cv.target_role,
        "recommendation": recommendation,
        "confidence": confidence,
        "parse_quality": cv.parse_quality,
        "missing_fields": cv.missing_fields,
    }


@router.post("/upload", status_code=201)
async def upload_cv(file: UploadFile = File(...)):
    filename = file.filename or "unknown"
    logger.info("Upload received: %s", filename)
    file_bytes = await file.read()
    return await _process_cv_bytes(file_bytes, filename)


def _log_event(candidate_id: str, event: str, detail: str,
               filename: str, fmt: str, file_hash: str) -> None:
    """Best-effort write to processing_log for failed uploads."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO candidates
                        (id, source_filename, source_format, parse_quality,
                         cv_data, recommendation, file_hash)
                    VALUES (%s, %s, %s, 'poor', '{}', 'error', %s)
                    ON CONFLICT (file_hash) DO NOTHING
                    """,
                    (candidate_id, filename, fmt, file_hash),
                )
                cur.execute(
                    "INSERT INTO processing_log (candidate_id, event, detail) VALUES (%s, %s, %s)",
                    (candidate_id, event, detail),
                )
            conn.commit()
    except Exception:
        pass  # log failure is non-critical
