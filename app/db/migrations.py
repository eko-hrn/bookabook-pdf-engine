"""Database engine construction and idempotent schema migration runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from sqlalchemy import Engine, NullPool, create_engine, event, text

from app.db.models import metadata

DEFAULT_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def normalize_database_url(raw_url: str) -> str:
    """Normalize Supabase/PostgreSQL or SQLite URLs for SQLAlchemy 2 + psycopg."""
    cleaned = raw_url.strip()
    if cleaned.startswith("postgres://"):
        return "postgresql+psycopg://" + cleaned[len("postgres://") :]
    if cleaned.startswith("postgresql://"):
        return "postgresql+psycopg://" + cleaned[len("postgresql://") :]
    return cleaned


def build_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy Engine tuned cleanly for Supabase PostgreSQL or local SQLite."""
    normalized = normalize_database_url(database_url)
    if normalized.startswith("postgresql+psycopg://"):
        connect_args: dict[str, Any] = {"prepare_threshold": 0}
        if "sslmode" not in normalized:
            connect_args["sslmode"] = "require"
        return create_engine(
            normalized,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
    if normalized.startswith("sqlite"):
        engine = create_engine(
            normalized,
            poolclass=NullPool,
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine
    return create_engine(normalized, pool_pre_ping=True)


def run_migrations(
    engine: Engine,
    migrations_dir: Optional[Path] = None,
) -> list[str]:
    """Apply SQL migrations on PostgreSQL/Supabase or metadata DDL on SQLite test DBs."""
    target_dir = migrations_dir or DEFAULT_MIGRATIONS_DIR
    applied: list[str] = []

    if engine.dialect.name == "postgresql" and target_dir.is_dir():
        sql_files = sorted(target_dir.glob("*.sql"))
        with engine.begin() as conn:
            for sql_file in sql_files:
                sql_script = sql_file.read_text(encoding="utf-8")
                for statement in _split_sql_statements(sql_script):
                    conn.execute(text(statement))
                applied.append(sql_file.name)
        return applied

    # Fallback dialect (e.g. SQLite automated tests) uses identical metadata DDL
    metadata.create_all(engine)
    applied.append("sqlalchemy_metadata_create_all")
    return applied


def _split_sql_statements(sql_script: str) -> list[str]:
    """Split plain PostgreSQL migration script into executable non-empty statements."""
    lines = [
        line
        for line in sql_script.splitlines()
        if not line.strip().startswith("--")
    ]
    cleaned = "\n".join(lines)
    return [stmt.strip() for stmt in cleaned.split(";") if stmt.strip()]
