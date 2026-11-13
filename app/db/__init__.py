"""Database persistence package (Supabase PostgreSQL + SQL migrations)."""

from app.db.migrations import build_engine, normalize_database_url, run_migrations
from app.db.models import book_pages_table, books_table, metadata
from app.db.repository import BookRepository, StoredBookPageRecord, StoredBookRecord

__all__ = [
    "BookRepository",
    "StoredBookPageRecord",
    "StoredBookRecord",
    "book_pages_table",
    "books_table",
    "build_engine",
    "metadata",
    "normalize_database_url",
    "run_migrations",
]

