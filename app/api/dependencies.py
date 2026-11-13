"""FastAPI dependency injection providers."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends
from sqlalchemy import Engine

from app.api.config import Settings, get_settings
from app.api.services.book_service import BookProcessingService
from app.api.services.document_service import DocumentService
from app.api.services.preview_service import PreviewService
from app.crop.review.workflow import PreviewReviewWorkflow
from app.db.migrations import build_engine, run_migrations
from app.db.repository import BookRepository
from app.storage.base import StorageAdapter
from app.storage.factory import create_storage_adapter


def get_app_settings() -> Settings:
    """Provide application configuration settings."""
    return get_settings()


def get_document_service(
    settings: Settings = Depends(get_app_settings),
) -> DocumentService:
    """Provide DocumentService instance."""
    return DocumentService(settings=settings)


def get_preview_service(
    doc_service: DocumentService = Depends(get_document_service),
    settings: Settings = Depends(get_app_settings),
) -> PreviewService:
    """Provide PreviewService instance."""
    return PreviewService(document_service=doc_service, settings=settings)


@lru_cache()
def _get_workflow_singleton(db_path_str: str) -> PreviewReviewWorkflow:
    """Cached PreviewReviewWorkflow instance per db_path."""
    return PreviewReviewWorkflow(db_path=db_path_str)


def get_review_workflow(
    settings: Settings = Depends(get_app_settings),
) -> PreviewReviewWorkflow:
    """Provide persistent PreviewReviewWorkflow instance backed by SQLite."""
    return _get_workflow_singleton(str(settings.DB_PATH))


class DatabaseConnectionError(RuntimeError):
    """Raised when Supabase PostgreSQL is configured but fails to connect or initialize."""


@lru_cache()
def _get_engine_singleton(database_url: str) -> Engine:
    """Cached SQLAlchemy Engine + idempotent schema migration runner."""
    engine = build_engine(database_url)
    try:
        run_migrations(engine)
    except Exception as exc:
        if engine.dialect.name == "postgresql":
            raise DatabaseConnectionError(
                f"Failed to connect or apply migrations to Supabase PostgreSQL: {exc}. "
                "Silent fallback to SQLite is strictly prohibited when DATABASE_URL is configured."
            ) from exc
        raise
    return engine


def get_book_repository(
    settings: Settings = Depends(get_app_settings),
) -> BookRepository:
    """Provide BookRepository configured from DATABASE_URL or local dev fallback.

    CRITICAL RULE: If DATABASE_URL is configured (Supabase PostgreSQL), NEVER silently fall back
    to SQLite if connection or migration fails. Raise a clear error.
    """
    database_url = settings.effective_database_url
    try:
        engine = _get_engine_singleton(database_url)
        return BookRepository(engine=engine)
    except Exception as exc:
        if settings.is_supabase_configured:
            raise DatabaseConnectionError(
                f"Supabase PostgreSQL is configured but could not be initialized: {exc}. "
                "Silent fallback to SQLite is strictly prohibited when DATABASE_URL is set."
            ) from exc
        raise


def get_storage_adapter(
    settings: Settings = Depends(get_app_settings),
) -> StorageAdapter:
    """Provide StorageAdapter ('local' dev or 'r2' Cloudflare R2)."""
    return create_storage_adapter(settings)


def get_book_service(
    settings: Settings = Depends(get_app_settings),
    storage: StorageAdapter = Depends(get_storage_adapter),
    repository: BookRepository = Depends(get_book_repository),
) -> BookProcessingService:
    """Provide BookProcessingService coordinating PDF crop, storage, and DB metadata."""
    return BookProcessingService(
        settings=settings,
        storage=storage,
        repository=repository,
    )

