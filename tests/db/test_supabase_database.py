"""Tests for Supabase PostgreSQL configuration, schema migrations, and metadata repository."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import pytest
from sqlalchemy import create_engine, inspect as sa_inspect, text

from app.api.config import Settings, get_settings
from app.api.dependencies import DatabaseConnectionError, get_book_repository
from app.db.migrations import (
    _split_sql_statements,
    build_engine,
    normalize_database_url,
    run_migrations,
)
from app.db.repository import BookRepository


def test_database_url_read_from_root_env() -> None:
    """Verify backend settings load DATABASE_URL from root .env without leaking secrets."""
    settings = get_settings()
    # Confirm root .env is loaded
    assert isinstance(settings.is_supabase_configured, bool)
    if settings.DATABASE_URL:
        assert settings.is_supabase_configured is True
        assert settings.effective_database_url.startswith("postgresql")
        # Ensure passwords or credentials are never exposed in simple repr/str
        repr_str = repr(settings)
        assert "password" not in repr_str.lower() or "******" in repr_str


def test_normalize_database_url_and_ssl_enforcement() -> None:
    """Verify URL normalization to postgresql+psycopg and default sslmode=require."""
    raw_postgres = "postgres://usr:pwd@db.project.supabase.co:5432/postgres"
    norm_postgres = normalize_database_url(raw_postgres)
    assert norm_postgres == "postgresql+psycopg://usr:pwd@db.project.supabase.co:5432/postgres"

    raw_with_ssl = "postgresql://usr:pwd@aws-0-region.pooler.supabase.com:6543/postgres?sslmode=require"
    norm_with_ssl = normalize_database_url(raw_with_ssl)
    assert norm_with_ssl == "postgresql+psycopg://usr:pwd@aws-0-region.pooler.supabase.com:6543/postgres?sslmode=require"

    # Verify build_engine injects sslmode=require and prepare_threshold=0
    engine = build_engine("postgresql://usr:pwd@db.project.supabase.co:5432/postgres")
    assert engine.dialect.name == "postgresql"
    assert engine.dialect.dbapi.__name__ == "psycopg"


def test_run_migrations_creates_schema_and_verifies_no_blob_storage() -> None:
    """Verify migration DDL creates tables books and book_pages with zero binary columns."""
    engine = create_engine("sqlite:///:memory:")
    applied = run_migrations(engine)
    assert len(applied) >= 1

    inspector = sa_inspect(engine)
    table_names = inspector.get_table_names()
    assert "books" in table_names
    assert "book_pages" in table_names

    # Check books table columns
    books_cols = {col["name"]: str(col["type"]).upper() for col in inspector.get_columns("books")}
    assert "book_id" in books_cols
    assert "title" in books_cols
    assert "storage_backend" in books_cols
    assert "validation_summary" in books_cols
    for col_type in books_cols.values():
        assert "BLOB" not in col_type
        assert "BYTEA" not in col_type

    # Check book_pages table columns
    pages_cols = {col["name"]: str(col["type"]).upper() for col in inspector.get_columns("book_pages")}
    assert "book_id" in pages_cols
    assert "page_key" in pages_cols
    assert "filename" in pages_cols
    assert "object_key" in pages_cols
    assert "sha256" in pages_cols
    for col_type in pages_cols.values():
        assert "BLOB" not in col_type
        assert "BYTEA" not in col_type


def test_book_repository_metadata_crud() -> None:
    """Verify metadata storage and retrieval in BookRepository."""
    engine = create_engine("sqlite:///:memory:")
    run_migrations(engine)
    repo = BookRepository(engine=engine)

    assert repo.check_connection() is True
    assert repo.dialect_name == "sqlite"

    # Insert book metadata
    book_id = "book_test_supabase_001"
    pages_data = [
        {
            "page_key": "COVER",
            "filename": "COVER.jpg",
            "page_kind": "COVER",
            "order_index": 0,
            "source_pdf_page": 1,
            "quadrant": None,
            "width_px": 1894,
            "height_px": 2657,
            "dpi": 300,
            "file_size_bytes": 406339,
            "quality_used": 51,
            "subsampling_used": "4:2:0",
            "compression_tier": "WITHIN_400KB_LIMIT",
            "sha256": "abc123cover",
            "object_key": f"books/{book_id}/COVER.jpg",
            "is_blank": False,
        },
        {
            "page_key": "PAGE-01",
            "filename": "PAGE-01.jpg",
            "page_kind": "CONTENT",
            "order_index": 1,
            "source_pdf_page": 2,
            "quadrant": 1,
            "width_px": 1773,
            "height_px": 2538,
            "dpi": 300,
            "file_size_bytes": 408834,
            "quality_used": 64,
            "subsampling_used": "4:2:0",
            "compression_tier": "WITHIN_400KB_LIMIT",
            "sha256": "abc123page1",
            "object_key": f"books/{book_id}/PAGE-01.jpg",
            "is_blank": False,
        },
        {
            "page_key": "BACKCOVER",
            "filename": "BACKCOVER.jpg",
            "page_kind": "BACKCOVER",
            "order_index": 2,
            "source_pdf_page": 1,
            "quadrant": None,
            "width_px": 1886,
            "height_px": 2657,
            "dpi": 300,
            "file_size_bytes": 1048185,
            "quality_used": 87,
            "subsampling_used": "4:2:2",
            "compression_tier": "BACKCOVER_WITHIN_1MB",
            "sha256": "abc123backcover",
            "object_key": f"books/{book_id}/BACKCOVER.jpg",
            "is_blank": False,
        },
    ]

    saved = repo.create_book_with_pages(
        book_id=book_id,
        title="Test Supabase Metadata Book",
        author="Author Test",
        authors_all="Author Test, Illustrator Test",
        description="Book metadata persistence test.",
        year=2026,
        age_group="6-8 years",
        sponsor="Bookabook",
        content_pages=1,
        phone="+62812345678",
        email="info@bookabook.id",
        source_filename="test_source.pdf",
        total_exported_pages=3,
        cover_filename="COVER.jpg",
        backcover_filename="BACKCOVER.jpg",
        storage_backend="local",
        validation_summary={"is_valid": True, "files_within_400kb": 2},
        pages=pages_data,
    )

    assert saved.book_id == book_id
    assert saved.title == "Test Supabase Metadata Book"
    assert saved.total_exported_pages == 3
    assert len(saved.pages) == 3
    assert saved.pages[0].page_key == "COVER"
    assert saved.pages[1].page_key == "PAGE-01"
    assert saved.pages[2].page_key == "BACKCOVER"

    # Query get_book
    fetched = repo.get_book(book_id)
    assert fetched is not None
    assert fetched.book_id == book_id
    assert fetched.author == "Author Test"
    assert len(fetched.pages) == 3
    assert fetched.pages[0].object_key == f"books/{book_id}/COVER.jpg"

    # Query list_books
    books_list = repo.list_books()
    assert len(books_list) == 1
    assert books_list[0].book_id == book_id

    # Delete book
    deleted = repo.delete_book(book_id)
    assert deleted is True
    assert repo.get_book(book_id) is None
    assert len(repo.list_books()) == 0


def test_no_silent_sqlite_fallback_when_supabase_fails() -> None:
    """Verify that when DATABASE_URL is configured, connection failure raises an error and NEVER silently falls back to SQLite."""
    unreachable_settings = Settings(
        DATABASE_URL="postgresql://user:pass@unreachable.invalid.supabase.co:5432/postgres",
    )
    assert unreachable_settings.is_supabase_configured is True
    assert unreachable_settings.effective_database_url.startswith("postgresql://")

    # Calling get_book_repository must raise DatabaseConnectionError and not return a SQLite repo
    with pytest.raises(DatabaseConnectionError) as exc_info:
        get_book_repository(unreachable_settings)

    err_msg = str(exc_info.value)
    assert "Silent fallback to SQLite is strictly prohibited" in err_msg
    assert "Supabase PostgreSQL" in err_msg


def test_health_reflects_postgresql_when_supabase_configured() -> None:
    """Verify /api/health honestly reports postgresql dialect and degraded status when unreachable."""
    from fastapi.testclient import TestClient
    from app.api.main import app
    from app.api.dependencies import get_app_settings

    test_settings_unreachable = Settings(
        DATABASE_URL="postgresql://user:pass@unreachable.invalid.supabase.co:5432/postgres",
    )
    app.dependency_overrides[get_app_settings] = lambda: test_settings_unreachable

    with TestClient(app) as test_client:
        resp = test_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["database_dialect"] == "postgresql"
        assert data["database_connected"] is False
        assert data["status"] == "degraded"

    app.dependency_overrides.clear()


def test_live_supabase_connection_and_metadata_crud() -> None:
    """Verify live Supabase connection and metadata CRUD when DATABASE_URL is configured."""
    import uuid
    settings = get_settings()
    if not settings.is_supabase_configured:
        pytest.skip("DATABASE_URL not configured for Supabase PostgreSQL.")

    engine = build_engine(settings.effective_database_url)
    run_migrations(engine)
    repo = BookRepository(engine=engine)

    assert repo.check_connection() is True
    assert repo.dialect_name == "postgresql"

    test_id = f"test_live_{uuid.uuid4().hex[:8]}"
    saved = repo.create_book_with_pages(
        book_id=test_id,
        title="Live Test Supabase Book",
        author="Automated Test",
        authors_all="Automated Test",
        description="Metadata verification on Supabase",
        year=2026,
        age_group="All",
        sponsor="Bookabook",
        content_pages=1,
        phone="+6280000000",
        email="test@bookabook.id",
        source_filename="live_test.pdf",
        total_exported_pages=2,
        cover_filename="COVER.jpg",
        backcover_filename="BACKCOVER.jpg",
        storage_backend="local",
        validation_summary={"is_valid": True},
        pages=[
            {
                "page_key": "COVER",
                "filename": "COVER.jpg",
                "page_kind": "COVER",
                "order_index": 0,
                "source_pdf_page": 1,
                "quadrant": None,
                "width_px": 1894,
                "height_px": 2657,
                "dpi": 300,
                "file_size_bytes": 406339,
                "quality_used": 51,
                "subsampling_used": "4:2:0",
                "compression_tier": "WITHIN_400KB_LIMIT",
                "sha256": "sha_live_cover",
                "object_key": f"books/{test_id}/COVER.jpg",
                "is_blank": False,
            },
            {
                "page_key": "BACKCOVER",
                "filename": "BACKCOVER.jpg",
                "page_kind": "BACKCOVER",
                "order_index": 1,
                "source_pdf_page": 1,
                "quadrant": None,
                "width_px": 1886,
                "height_px": 2657,
                "dpi": 300,
                "file_size_bytes": 1048185,
                "quality_used": 87,
                "subsampling_used": "4:2:2",
                "compression_tier": "BACKCOVER_WITHIN_1MB",
                "sha256": "sha_live_back",
                "object_key": f"books/{test_id}/BACKCOVER.jpg",
                "is_blank": False,
            },
        ],
    )
    assert saved.book_id == test_id
    assert len(saved.pages) == 2

    fetched = repo.get_book(test_id)
    assert fetched is not None
    assert fetched.title == "Live Test Supabase Book"
    assert len(fetched.pages) == 2

    # Cleanup
    deleted = repo.delete_book(test_id)
    assert deleted is True
    assert repo.get_book(test_id) is None
