"""API Configuration & Settings.

Loads environment variables using pydantic-settings, provides sane defaults
for local development on Windows, and ensures runtime directories exist.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings for Bookabook PDF Engine Backend API."""

    PROJECT_NAME: str = "Bookabook PDF Engine API"
    API_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"

    # Runtime Data Directories
    DATA_DIR: Path = Path("data")
    UPLOAD_DIR: Path = Path("data/uploads")
    PREVIEW_DIR: Path = Path("data/previews")
    LOCAL_STORAGE_DIR: Path = Path("data/storage")
    DB_PATH: Path = Path("data/bookabook_review.db")

    # Metadata Database (Supabase PostgreSQL via DATABASE_URL)
    DATABASE_URL: Optional[str] = None

    # Supabase Storage Configuration
    SUPABASE_URL: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    SUPABASE_STORAGE_BUCKET: str = "bookabook-images"

    # Object Storage Backend ('local' for dev, 'supabase' for Supabase Storage, 'r2' for Cloudflare R2)
    STORAGE_BACKEND: str = "local"
    R2_ENDPOINT_URL: Optional[str] = None
    R2_ACCESS_KEY_ID: Optional[str] = None
    R2_SECRET_ACCESS_KEY: Optional[str] = None
    R2_BUCKET_NAME: Optional[str] = None
    R2_PUBLIC_BASE_URL: Optional[str] = None

    # Upload & Export Restrictions
    MAX_UPLOAD_SIZE_BYTES: int = 500 * 1024 * 1024  # 500 MB (supports 200-300 MB large PDFs)
    ALLOWED_EXTENSIONS: set[str] = {".pdf"}

    # Rendering Resolutions & JPEG Compression Policy
    PREVIEW_DPI: int = 100
    PRODUCTION_EXPORT_DPI: int = 300
    COVER_MAX_BYTES: int = 400 * 1024            # 409,600 bytes (400 KB)
    INSIDE_PAGE_MAX_BYTES: int = 400 * 1024      # 409,600 bytes (400 KB)
    BACKCOVER_MAX_BYTES: int = 1024 * 1024       # 1,048,576 bytes (1 MB)
    INITIAL_JPEG_QUALITY: int = 95
    MIN_JPEG_QUALITY_COVER: int = 40
    MIN_JPEG_QUALITY_INSIDE: int = 40
    MIN_JPEG_QUALITY_BACKCOVER: int = 65

    # CORS Settings
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    model_config = SettingsConfigDict(
        env_file=(str(Path(__file__).resolve().parents[2] / ".env"), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def is_supabase_configured(self) -> bool:
        """Whether a Supabase/PostgreSQL DATABASE_URL is explicitly configured."""
        return bool(self.DATABASE_URL and self.DATABASE_URL.strip())

    @property
    def effective_database_url(self) -> str:
        """Return Supabase PostgreSQL DATABASE_URL when set, else local SQLite fallback.

        CRITICAL: If DATABASE_URL is set, caller must never silently fallback to SQLite.
        """
        if self.is_supabase_configured:
            return self.DATABASE_URL.strip()
        resolved = self.DB_PATH.resolve()
        return f"sqlite:///{resolved.as_posix()}"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return [str(v)]

    def ensure_directories(self) -> None:
        """Create required runtime storage directories if they do not exist."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
        self.LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        if self.DB_PATH.parent:
            self.DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    settings = Settings()
    settings.ensure_directories()
    return settings

