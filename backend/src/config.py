from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    database_url: str
    env: str = "development"
    log_level: str = "INFO"

    # CORS — comma-separated origins, or "*" for development
    cors_origins: str = "*"

    # Upload limits
    max_file_size_mb: int = 5

    # Paths (relative to /app inside Docker, override locally)
    ml_model_path: str = "./ml/model.joblib"

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
