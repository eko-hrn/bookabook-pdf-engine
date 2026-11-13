"""Repository layer for Bookabook metadata and exported JPG object references."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Engine, delete, desc, insert, select, text

from app.db.models import book_pages_table, books_table


@dataclass(frozen=True)
class StoredBookPageRecord:
    """Metadata row for one exported 300 DPI JPEG belonging to a saved book."""

    book_id: str
    page_key: str
    filename: str
    page_kind: str
    order_index: int
    source_pdf_page: int
    quadrant: Optional[int]
    width_px: int
    height_px: int
    dpi: int
    file_size_bytes: int
    quality_used: int
    subsampling_used: str
    compression_tier: str
    sha256: str
    object_key: str
    is_blank: bool
    created_at: datetime


@dataclass(frozen=True)
class StoredBookRecord:
    """Metadata row for one saved Bookabook book."""

    book_id: str
    title: str
    author: str
    authors_all: str
    description: str
    year: Optional[int]
    age_group: str
    sponsor: str
    content_pages: int
    phone: str
    email: str
    source_filename: str
    total_exported_pages: int
    cover_filename: str
    backcover_filename: str
    storage_backend: str
    validation_summary: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    pages: list[StoredBookPageRecord]


class BookRepository:
    """SQLAlchemy-backed metadata repository targeting Supabase PostgreSQL."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @property
    def dialect_name(self) -> str:
        return str(self.engine.dialect.name)

    def check_connection(self) -> bool:
        try:
            with self.engine.connect() as conn:
                val = conn.execute(text("SELECT 1")).scalar()
                return val == 1
        except Exception:
            return False

    def create_book_with_pages(
        self,
        *,
        book_id: str,
        title: str,
        author: str,
        authors_all: str,
        description: str,
        year: Optional[int],
        age_group: str,
        sponsor: str,
        content_pages: int,
        phone: str,
        email: str,
        source_filename: str,
        total_exported_pages: int,
        cover_filename: str,
        backcover_filename: str,
        storage_backend: str,
        validation_summary: dict[str, Any],
        pages: list[dict[str, Any]],
    ) -> StoredBookRecord:
        now = datetime.now(timezone.utc)
        book_values = {
            "book_id": book_id,
            "title": title,
            "author": author,
            "authors_all": authors_all,
            "description": description,
            "year": year,
            "age_group": age_group,
            "sponsor": sponsor,
            "content_pages": content_pages,
            "phone": phone,
            "email": email,
            "source_filename": source_filename,
            "total_exported_pages": total_exported_pages,
            "cover_filename": cover_filename,
            "backcover_filename": backcover_filename,
            "storage_backend": storage_backend,
            "validation_summary": validation_summary,
            "created_at": now,
            "updated_at": now,
        }

        page_rows = [
            {
                "book_id": book_id,
                "page_key": p["page_key"],
                "filename": p["filename"],
                "page_kind": p["page_kind"],
                "order_index": p["order_index"],
                "source_pdf_page": p["source_pdf_page"],
                "quadrant": p.get("quadrant"),
                "width_px": p["width_px"],
                "height_px": p["height_px"],
                "dpi": p["dpi"],
                "file_size_bytes": p["file_size_bytes"],
                "quality_used": p["quality_used"],
                "subsampling_used": p["subsampling_used"],
                "compression_tier": p["compression_tier"],
                "sha256": p["sha256"],
                "object_key": p["object_key"],
                "is_blank": bool(p.get("is_blank", False)),
                "created_at": now,
            }
            for p in pages
        ]

        with self.engine.begin() as conn:
            conn.execute(insert(books_table).values(**book_values))
            if page_rows:
                conn.execute(insert(book_pages_table), page_rows)

        created = self.get_book(book_id)
        if created is None:
            raise RuntimeError(f"Failed reloading newly persisted book '{book_id}'.")
        return created

    def list_books(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[StoredBookRecord]:
        with self.engine.connect() as conn:
            rows = (
                conn.execute(
                    select(books_table)
                    .order_by(desc(books_table.c.created_at))
                    .limit(limit)
                    .offset(offset)
                )
                .mappings()
                .all()
            )
            if not rows:
                return []

            book_ids = [r["book_id"] for r in rows]
            page_rows = (
                conn.execute(
                    select(book_pages_table)
                    .where(book_pages_table.c.book_id.in_(book_ids))
                    .order_by(book_pages_table.c.book_id, book_pages_table.c.order_index.asc())
                )
                .mappings()
                .all()
            )

        pages_by_book: dict[str, list[StoredBookPageRecord]] = {}
        for pr in page_rows:
            pages_by_book.setdefault(pr["book_id"], []).append(_row_to_page(pr))

        return [_row_to_book(row, pages_by_book.get(row["book_id"], [])) for row in rows]

    def get_book(self, book_id: str) -> Optional[StoredBookRecord]:
        with self.engine.connect() as conn:
            row = (
                conn.execute(
                    select(books_table).where(books_table.c.book_id == book_id)
                )
                .mappings()
                .first()
            )
            if row is None:
                return None
            page_rows = (
                conn.execute(
                    select(book_pages_table)
                    .where(book_pages_table.c.book_id == book_id)
                    .order_by(book_pages_table.c.order_index.asc())
                )
                .mappings()
                .all()
            )

        return _row_to_book(row, [_row_to_page(pr) for pr in page_rows])

    def delete_book(self, book_id: str) -> bool:
        with self.engine.begin() as conn:
            res = conn.execute(
                delete(books_table).where(books_table.c.book_id == book_id)
            )
            return bool(res.rowcount and res.rowcount > 0)


def _row_to_page(row: Any) -> StoredBookPageRecord:
    return StoredBookPageRecord(
        book_id=row["book_id"],
        page_key=row["page_key"],
        filename=row["filename"],
        page_kind=row["page_kind"],
        order_index=int(row["order_index"]),
        source_pdf_page=int(row["source_pdf_page"]),
        quadrant=int(row["quadrant"]) if row["quadrant"] is not None else None,
        width_px=int(row["width_px"]),
        height_px=int(row["height_px"]),
        dpi=int(row["dpi"]),
        file_size_bytes=int(row["file_size_bytes"]),
        quality_used=int(row["quality_used"]),
        subsampling_used=str(row["subsampling_used"]),
        compression_tier=str(row["compression_tier"]),
        sha256=str(row["sha256"]),
        object_key=str(row["object_key"]),
        is_blank=bool(row["is_blank"]),
        created_at=row["created_at"],
    )


def _row_to_book(row: Any, pages: list[StoredBookPageRecord]) -> StoredBookRecord:
    return StoredBookRecord(
        book_id=row["book_id"],
        title=row["title"],
        author=row["author"] or "",
        authors_all=row["authors_all"] or "",
        description=row["description"] or "",
        year=int(row["year"]) if row["year"] is not None else None,
        age_group=row["age_group"] or "",
        sponsor=row["sponsor"] or "",
        content_pages=int(row["content_pages"]),
        phone=row["phone"] or "",
        email=row["email"] or "",
        source_filename=row["source_filename"],
        total_exported_pages=int(row["total_exported_pages"]),
        cover_filename=row["cover_filename"],
        backcover_filename=row["backcover_filename"],
        storage_backend=row["storage_backend"],
        validation_summary=dict(row["validation_summary"] or {}),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        pages=pages,
    )

