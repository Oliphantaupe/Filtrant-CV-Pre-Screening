import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import settings
from src.db import init_db, close_db
from src.routers import upload, export
from src.services.watcher import watch_incoming

# ─── Logging setup ────────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("filtrant")


# ─── App lifecycle ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Filtrant API (env=%s)", settings.env)
    init_db()
    logger.info("Database ready")
    watcher = asyncio.create_task(watch_incoming())
    yield
    watcher.cancel()
    await asyncio.gather(watcher, return_exceptions=True)
    close_db()
    logger.info("Shutdown complete")


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Filtrant — CV Pre-Screening API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(export.router)


# ─── Global exception handler ─────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/api/v1/health", tags=["system"])
def health():
    from src.db import get_conn
    db_ok = False
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        db_ok = True
    except Exception:
        logger.warning("Health check: DB unreachable")

    fair_model = os.path.join(os.path.dirname(settings.ml_model_path), "model_fair.joblib")
    model_ok = os.path.exists(fair_model) or os.path.exists(settings.ml_model_path)

    body = {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "env": settings.env,
        "model_file": model_ok,
    }
    return JSONResponse(status_code=200 if db_ok else 503, content=body)
