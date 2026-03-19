import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
from src.config import settings

_pool: pool.SimpleConnectionPool | None = None


def init_db() -> None:
    global _pool
    _pool = pool.SimpleConnectionPool(1, 10, dsn=settings.database_url)
    _create_tables()


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
                    missing_fields JSONB DEFAULT '[]'
                );

                CREATE TABLE IF NOT EXISTS processing_log (
                    id SERIAL PRIMARY KEY,
                    candidate_id UUID REFERENCES candidates(id),
                    event TEXT NOT NULL,
                    detail TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
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
