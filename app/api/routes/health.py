"""Health check router."""

from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

from fastapi import APIRouter, Depends

from app.api.config import Settings
from app.api.dependencies import get_app_settings, get_book_repository
from app.api.schemas.health import HealthResponse
from app.db.repository import BookRepository

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Service Health Check")
def get_health(
    settings: Settings = Depends(get_app_settings),
) -> HealthResponse:
    """Check service health, review SQLite, and books metadata DB connectivity."""
    review_db_ok = False
    try:
        conn = sqlite3.connect(str(settings.DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        res = cursor.fetchone()
        conn.close()
        review_db_ok = (res is not None and res[0] == 1)
    except Exception:
        review_db_ok = False

    metadata_db_ok = False
    database_dialect = "postgresql" if settings.is_supabase_configured else "sqlite"
    try:
        repo = get_book_repository(settings)
        metadata_db_ok = repo.check_connection()
        database_dialect = repo.dialect_name
    except Exception:
        metadata_db_ok = False

    db_ok = review_db_ok and metadata_db_ok

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        app_name=settings.PROJECT_NAME,
        version=settings.API_VERSION,
        database_connected=db_ok,
        database_dialect=database_dialect,
        storage_backend=settings.STORAGE_BACKEND,
        timestamp=datetime.now(timezone.utc),
    )

