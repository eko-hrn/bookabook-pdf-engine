-- Migration 001: Supabase PostgreSQL schema for Bookabook book catalog and exported JPG page metadata.
-- Note: Raw JPG binaries are NEVER stored in PostgreSQL; they reside in StorageAdapter (Local / Cloudflare R2).

CREATE TABLE IF NOT EXISTS books (
    book_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT NOT NULL DEFAULT '',
    authors_all TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    year INTEGER,
    age_group TEXT NOT NULL DEFAULT '',
    sponsor TEXT NOT NULL DEFAULT '',
    content_pages INTEGER NOT NULL CHECK (content_pages >= 0),
    phone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    source_filename TEXT NOT NULL,
    total_exported_pages INTEGER NOT NULL CHECK (total_exported_pages >= 1),
    cover_filename TEXT NOT NULL DEFAULT 'COVER.jpg',
    backcover_filename TEXT NOT NULL DEFAULT 'BACKCOVER.jpg',
    storage_backend TEXT NOT NULL DEFAULT 'local',
    validation_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_books_created_at
    ON books (created_at DESC);

CREATE TABLE IF NOT EXISTS book_pages (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(book_id) ON DELETE CASCADE,
    page_key TEXT NOT NULL,
    filename TEXT NOT NULL,
    page_kind TEXT NOT NULL CHECK (page_kind IN ('COVER', 'CONTENT', 'BACKCOVER')),
    order_index INTEGER NOT NULL CHECK (order_index >= 0),
    source_pdf_page INTEGER NOT NULL CHECK (source_pdf_page >= 1),
    quadrant INTEGER,
    width_px INTEGER NOT NULL CHECK (width_px > 0),
    height_px INTEGER NOT NULL CHECK (height_px > 0),
    dpi INTEGER NOT NULL DEFAULT 300 CHECK (dpi > 0),
    file_size_bytes INTEGER NOT NULL CHECK (file_size_bytes > 0 AND file_size_bytes <= 2000000),
    quality_used INTEGER NOT NULL CHECK (quality_used BETWEEN 1 AND 100),
    subsampling_used TEXT NOT NULL DEFAULT '4:2:0',
    compression_tier TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    object_key TEXT NOT NULL,
    is_blank BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_book_pages_book_filename UNIQUE (book_id, filename),
    CONSTRAINT uq_book_pages_book_order UNIQUE (book_id, order_index)
);

CREATE INDEX IF NOT EXISTS idx_book_pages_book_order
    ON book_pages (book_id, order_index ASC);

