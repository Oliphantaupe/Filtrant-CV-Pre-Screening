from pathlib import Path
from pydantic import ConfigDict, field_validator
from pydantic_settings import BaseSettings

# Root of the backend package — one level above src/
# Local: backend/src/config.py → backend/
# Docker: /app/src/config.py → /app/  (matches WORKDIR in Dockerfile)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    database_url: str

    @field_validator("database_url", mode="before")
    @classmethod
    def fix_postgres_scheme(cls, v: str) -> str:
        # Railway injects postgres:// but psycopg2 requires postgresql://
        if isinstance(v, str) and v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v
    env: str = "development"
    log_level: str = "INFO"

    # CORS — comma-separated origins, or "*" for development
    cors_origins: str = "*"

    # Upload limits
    max_file_size_mb: int = 5

    # Paths — absolute by default so they work regardless of CWD; Docker overrides via env vars
    incoming_cvs_path: str = str(_PROJECT_ROOT / "data" / "incoming_cvs")
    processed_cvs_path: str = str(_PROJECT_ROOT / "data" / "processed_cvs")
    failed_cvs_path: str = str(_PROJECT_ROOT / "data" / "failed_cvs")
    ml_model_path: str = str(_PROJECT_ROOT / "ml" / "model.joblib")

    # File watcher
    watcher_interval: int = 10  # seconds between polls

    model_config = ConfigDict(env_file=".env")

    @property
    def cors_origins_list(self) -> list[str]:
        if self.cors_origins == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


settings = Settings()
