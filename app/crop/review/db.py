"""Database Schema, Migrations, and Utilities for Review Persistence (Phase 1.2.2.7).

Provides SQLite database initialization, schema version tracking, backup,
and restore utilities.

Guarantees:
1. Parameterized SQL queries: Prevents SQL injection.
2. Foreign key constraints: Enforces referential integrity (ON DELETE CASCADE).
3. Repeatable initialization: Safe to call repeatedly without data loss.
4. Schema version tracking: Manages migrations transparently via schema_migrations.
5. Online backup and restore: Uses SQLite native backup API without locking.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from typing import Union

# Schema Versioning
CURRENT_SCHEMA_VERSION = 1
SCHEMA_DESCRIPTION_V1 = "Initial review workflow tables and indexes"

# Default Directory & Database Path
DEFAULT_DATA_DIR = Path("data")
DEFAULT_REVIEW_DB_PATH = DEFAULT_DATA_DIR / "bookabook_review.db"

# SQL DDL for Schema Version 1
SCHEMA_V1_DDL = """
-- Table 1: Review Sessions
CREATE TABLE IF NOT EXISTS review_sessions (
    session_id TEXT PRIMARY KEY,
    source_filename TEXT NOT NULL,
    total_pages INTEGER NOT NULL,
    status TEXT NOT NULL,
    approved_pages_count INTEGER NOT NULL DEFAULT 0,
    rejected_pages_count INTEGER NOT NULL DEFAULT 0,
    needs_revision_pages_count INTEGER NOT NULL DEFAULT 0,
    pending_pages_count INTEGER NOT NULL DEFAULT 0,
    is_review_completed INTEGER NOT NULL DEFAULT 0,
    requires_production_authorization INTEGER NOT NULL DEFAULT 1,
    summary_message TEXT NOT NULL DEFAULT '',
    unresolved_discrepancies TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    reviewed_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

-- Table 2: Page Review Records
CREATE TABLE IF NOT EXISTS page_review_records (
    session_id TEXT NOT NULL,
    pdf_page_index INTEGER NOT NULL,
    pdf_page_number INTEGER NOT NULL,
    layout_type TEXT,
    classification_status TEXT NOT NULL,
    crop_readiness TEXT NOT NULL,
    review_decision TEXT NOT NULL DEFAULT 'PENDING',
    reviewer_id TEXT,
    reviewed_at TEXT,
    notes TEXT,
    warnings TEXT NOT NULL DEFAULT '[]',
    unresolved_discrepancies TEXT NOT NULL DEFAULT '[]',
    is_cover INTEGER NOT NULL DEFAULT 0,
    is_non_nominal INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (session_id, pdf_page_number),
    FOREIGN KEY (session_id) REFERENCES review_sessions(session_id) ON DELETE CASCADE
);

-- Table 3: Review History (Audit Trail)
CREATE TABLE IF NOT EXISTS review_history (
    entry_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    pdf_page_index INTEGER,
    pdf_page_number INTEGER,
    event_type TEXT NOT NULL,
    previous_decision TEXT,
    new_decision TEXT,
    reviewer_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    notes TEXT,
    reason TEXT,
    FOREIGN KEY (session_id) REFERENCES review_sessions(session_id) ON DELETE CASCADE
);

-- Indexes for performance & query isolation
CREATE INDEX IF NOT EXISTS idx_review_history_session_page 
    ON review_history (session_id, pdf_page_number);

CREATE INDEX IF NOT EXISTS idx_page_records_session_decision 
    ON page_review_records (session_id, review_decision);

CREATE INDEX IF NOT EXISTS idx_review_sessions_status 
    ON review_sessions (status);
"""


def init_database(
    db_path: Union[str, Path] = DEFAULT_REVIEW_DB_PATH,
    verbose: bool = False,
) -> None:
    """Initialize the SQLite review database and apply migrations.

    Safe to run repeatedly. Never drops or deletes existing data.

    Args:
        db_path: Path to the SQLite database file or ':memory:'.
        verbose: If True, prints migration information.
    """
    is_memory = str(db_path) == ":memory:"

    if not is_memory:
        path_obj = Path(db_path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON;")

        # Create schema_migrations table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                description TEXT NOT NULL,
                applied_at TEXT NOT NULL
            );
        """)
        conn.commit()

        # Check current version
        cur = conn.cursor()
        cur.execute("SELECT MAX(version) FROM schema_migrations;")
        row = cur.fetchone()
        current_version = row[0] if (row and row[0] is not None) else 0

        if current_version < CURRENT_SCHEMA_VERSION:
            # Apply V1 schema
            conn.executescript(SCHEMA_V1_DDL)
            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO schema_migrations (version, description, applied_at) VALUES (?, ?, ?);",
                (CURRENT_SCHEMA_VERSION, SCHEMA_DESCRIPTION_V1, now_iso),
            )
            conn.commit()
            if verbose:
                print(f"Applied schema migration v{CURRENT_SCHEMA_VERSION} to {db_path}")
    finally:
        conn.close()


def get_schema_version(db_path: Union[str, Path] = DEFAULT_REVIEW_DB_PATH) -> int:
    """Return the current schema migration version of the database.

    Returns 0 if the database is uninitialized.
    """
    if str(db_path) != ":memory:" and not Path(db_path).exists():
        return 0

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations';")
        if not cur.fetchone():
            return 0
        cur.execute("SELECT MAX(version) FROM schema_migrations;")
        row = cur.fetchone()
        return row[0] if (row and row[0] is not None) else 0
    finally:
        conn.close()


def backup_database(
    source_path: Union[str, Path],
    backup_path: Union[str, Path],
) -> None:
    """Create an online backup of the SQLite database using native backup API.

    Ensures zero database corruption without exclusive write locking.

    Args:
        source_path: Path to source SQLite database file.
        backup_path: Destination path for the backup file.
    """
    src_p = Path(source_path)
    dst_p = Path(backup_path)

    if not src_p.exists():
        raise FileNotFoundError(f"Source database not found for backup: {src_p}")

    dst_p.parent.mkdir(parents=True, exist_ok=True)

    src_conn = sqlite3.connect(str(src_p))
    dst_conn = sqlite3.connect(str(dst_p))
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()


def restore_database(
    backup_path: Union[str, Path],
    target_path: Union[str, Path],
) -> None:
    """Restore an SQLite database from a backup file using native backup API.

    Args:
        backup_path: Path to the existing backup file.
        target_path: Destination path where the database will be restored.
    """
    bak_p = Path(backup_path)
    tgt_p = Path(target_path)

    if not bak_p.exists():
        raise FileNotFoundError(f"Backup file not found for restore: {bak_p}")

    tgt_p.parent.mkdir(parents=True, exist_ok=True)

    src_conn = sqlite3.connect(str(bak_p))
    dst_conn = sqlite3.connect(str(tgt_p))
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

