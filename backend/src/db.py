import logging
import time

import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
from src.config import settings

logger = logging.getLogger(__name__)
_pool: pool.SimpleConnectionPool | None = None


def init_db(retries: int = 10, delay: float = 3.0) -> None:
    global _pool
    for attempt in range(1, retries + 1):
        try:
            _pool = pool.SimpleConnectionPool(1, 10, dsn=settings.database_url)
            _create_tables()
            return
        except psycopg2.OperationalError as e:
            if attempt == retries:
                raise
            logger.warning("DB not ready (attempt %d/%d): %s — retrying in %.0fs", attempt, retries, e, delay)
            time.sleep(delay)


def _create_tables() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS candidates (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    processed_at TIMESTAMPTZ DEFAULT NOW(),
                    source_filename TEXT NOT NULL,
                    source_format TEXT NOT NULL,
                    parse_quality TEXT NOT NULL,
                    cv_data JSONB NOT NULL,
                    recommendation TEXT NOT NULL,
                    confidence NUMERIC(4,3),
                    file_hash TEXT UNIQUE,
                    missing_fields JSONB DEFAULT '[]',
                    explanation JSONB DEFAULT NULL,
                    hr_decision TEXT DEFAULT NULL,
                    override_reason TEXT DEFAULT NULL,
                    overridden_at TIMESTAMPTZ DEFAULT NULL
                );

                ALTER TABLE candidates ADD COLUMN IF NOT EXISTS explanation JSONB DEFAULT NULL;
                ALTER TABLE candidates ADD COLUMN IF NOT EXISTS hr_decision TEXT DEFAULT NULL;
                ALTER TABLE candidates ADD COLUMN IF NOT EXISTS override_reason TEXT DEFAULT NULL;
                ALTER TABLE candidates ADD COLUMN IF NOT EXISTS overridden_at TIMESTAMPTZ DEFAULT NULL;
                ALTER TABLE candidates ADD COLUMN IF NOT EXISTS recommendation_base TEXT DEFAULT NULL;
                ALTER TABLE candidates ADD COLUMN IF NOT EXISTS confidence_base NUMERIC(4,3) DEFAULT NULL;
                ALTER TABLE candidates ADD COLUMN IF NOT EXISTS explanation_base JSONB DEFAULT NULL;

                CREATE TABLE IF NOT EXISTS processing_log (
                    id SERIAL PRIMARY KEY,
                    candidate_id UUID REFERENCES candidates(id),
                    event TEXT NOT NULL,
                    detail TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_candidates_processed_at
                    ON candidates (processed_at DESC);
                CREATE INDEX IF NOT EXISTS idx_candidates_recommendation
                    ON candidates (recommendation);
            """)
        conn.commit()


@contextmanager
def get_conn():
    conn = _pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


def close_db() -> None:
    if _pool:
        _pool.closeall()
