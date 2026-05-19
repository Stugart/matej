from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# kutaj_api/settings.py -> apps/api/kutaj_api/ -> apps/api/ -> apps/ -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_env: str = "dev"
    app_base_url: str = "http://127.0.0.1:8000"
    app_log_level: str = "INFO"
    app_secret_key: str = ""

    # --- Persistence ---
    database_url: str = "postgresql+asyncpg://kutaj:kutaj_dev_only@127.0.0.1:5432/kutaj"
    redis_url: str = "redis://127.0.0.1:6379/0"

    # --- Storage ---
    storage_root: Path = Path("./storage/audio")
    tmp_root: Path = Path("./storage/tmp")

    # --- Upload limits ---
    max_audio_upload_bytes: int = 200 * 1024 * 1024
    max_audio_duration_seconds: int = 1800
    allowed_audio_mime: str = (
        "audio/mpeg,audio/mp4,audio/webm,audio/wav,audio/ogg,audio/x-m4a"
    )

    # --- Retention ---
    soft_delete_retention_days: int = 90

    # --- External APIs ---
    openai_api_key: str = ""
    openai_whisper_model: str = "whisper-1"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # --- Auth ---
    jwt_secret_key: str = ""
    jwt_access_ttl_seconds: int = 900
    jwt_refresh_ttl_seconds: int = 30 * 24 * 3600

    # --- CORS ---
    cors_allowed_origins: str = "http://127.0.0.1:5173,http://127.0.0.1:8000"

    # --- Embeddings ---
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def allowed_audio_mime_set(self) -> set[str]:
        return {m.strip() for m in self.allowed_audio_mime.split(",") if m.strip()}

    @property
    def is_prod(self) -> bool:
        return self.app_env.lower() == "prod"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.is_prod:
        # Fail-fast: nesmieme nasadiť produkciu s dev defaultmi.
        for key in ("app_secret_key", "jwt_secret_key"):
            value = getattr(s, key)
            if not value or len(value) < 32:
                raise RuntimeError(f"{key.upper()} must be >=32 chars in prod")
    return s
