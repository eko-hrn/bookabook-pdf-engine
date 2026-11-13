"""SQLAlchemy schema definitions mirroring migrations/001_create_books_tables.sql.

Stores book and exported JPG page metadata plus StorageAdapter object keys ONLY.
Raw binary JPG payloads are never stored in PostgreSQL.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
)

metadata = MetaData()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


books_table = Table(
    "books",
    metadata,
    Column("book_id", Text, primary_key=True),
    Column("title", Text, nullable=False),
    Column("author", Text, nullable=False, default=""),
    Column("authors_all", Text, nullable=False, default=""),
    Column("description", Text, nullable=False, default=""),
    Column("year", Integer, nullable=True),
    Column("age_group", Text, nullable=False, default=""),
    Column("sponsor", Text, nullable=False, default=""),
    Column("content_pages", Integer, nullable=False),
    Column("phone", Text, nullable=False, default=""),
    Column("email", Text, nullable=False, default=""),
    Column("source_filename", Text, nullable=False),
    Column("total_exported_pages", Integer, nullable=False),
    Column("cover_filename", Text, nullable=False, default="COVER.jpg"),
    Column("backcover_filename", Text, nullable=False, default="BACKCOVER.jpg"),
    Column("storage_backend", Text, nullable=False, default="local"),
    Column("validation_summary", JSON, nullable=False, default=dict),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
    Column("updated_at", DateTime(timezone=True), nullable=False, default=_utc_now),
    CheckConstraint("content_pages >= 0", name="ck_books_content_pages_nonneg"),
    CheckConstraint("total_exported_pages >= 1", name="ck_books_total_pages_pos"),
)

Index("idx_books_created_at", books_table.c.created_at.desc())

book_pages_table = Table(
    "book_pages",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "book_id",
        Text,
        ForeignKey("books.book_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("page_key", Text, nullable=False),
    Column("filename", Text, nullable=False),
    Column("page_kind", Text, nullable=False),
    Column("order_index", Integer, nullable=False),
    Column("source_pdf_page", Integer, nullable=False),
    Column("quadrant", Integer, nullable=True),
    Column("width_px", Integer, nullable=False),
    Column("height_px", Integer, nullable=False),
    Column("dpi", Integer, nullable=False, default=300),
    Column("file_size_bytes", Integer, nullable=False),
    Column("quality_used", Integer, nullable=False),
    Column("subsampling_used", Text, nullable=False, default="4:2:0"),
    Column("compression_tier", Text, nullable=False),
    Column("sha256", Text, nullable=False),
    Column("object_key", Text, nullable=False),
    Column("is_blank", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
    CheckConstraint(
        "page_kind IN ('COVER', 'CONTENT', 'BACKCOVER')",
        name="ck_book_pages_kind",
    ),
    CheckConstraint("file_size_bytes > 0 AND file_size_bytes <= 2000000", name="ck_book_pages_size"),
    UniqueConstraint("book_id", "filename", name="uq_book_pages_book_filename"),
    UniqueConstraint("book_id", "order_index", name="uq_book_pages_book_order"),
)

Index(
    "idx_book_pages_book_order",
    book_pages_table.c.book_id,
    book_pages_table.c.order_index.asc(),
)

