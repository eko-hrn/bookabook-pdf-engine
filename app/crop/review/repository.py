"""Repository Layer for Review Persistence (Phase 1.2.2.7).

Implements database abstraction and SQLite repository with atomic transactions,
parameterized queries, foreign key enforcement, and UTC timestamp preservation.
"""

from __future__ import annotations

import abc
import contextlib
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Generator, Optional, Union

from app.crop.models.enums import (
    ClassificationStatus,
    CropReadinessStatus,
    LayoutType,
)
from app.crop.review.db import init_database
from app.crop.review.enums import (
    DocumentReviewStatus,
    ReviewDecisionState,
    ReviewEventType,
)
from app.crop.review.models import (
    DocumentReviewSummary,
    PageReviewRecord,
    ReviewHistory,
    ReviewHistoryEntry,
    ReviewSession,
)


class DuplicateSessionError(ValueError):
    """Raised when an attempt is made to create a session with an existing ID."""

    pass


class ReviewRepository(abc.ABC):
    """Abstract base class defining persistent review storage operations."""

    @abc.abstractmethod
    def create_session(self, session: ReviewSession) -> None:
        """Persist a new ReviewSession with its pages and initial history."""
        pass

    @abc.abstractmethod
    def session_exists(self, session_id: str) -> bool:
        """Check if a session exists by ID."""
        pass

    @abc.abstractmethod
    def get_session(self, session_id: str) -> Optional[ReviewSession]:
        """Retrieve a complete ReviewSession by ID."""
        pass

    @abc.abstractmethod
    def get_page_record(self, session_id: str, page_number: int) -> Optional[PageReviewRecord]:
        """Retrieve a single PageReviewRecord for a session and page number."""
        pass

    @abc.abstractmethod
    def record_page_decision(
        self,
        session_id: str,
        page_number: int,
        page_record: PageReviewRecord,
        history_entry: ReviewHistoryEntry,
        updated_summary: DocumentReviewSummary,
        updated_at: datetime,
    ) -> None:
        """Atomically persist a page decision, history entry, and updated document summary."""
        pass

    @abc.abstractmethod
    def record_page_notes(
        self,
        session_id: str,
        page_number: int,
        page_record: PageReviewRecord,
        history_entry: ReviewHistoryEntry,
        updated_at: datetime,
    ) -> None:
        """Atomically persist updated page notes and history entry."""
        pass

    @abc.abstractmethod
    def list_sessions(self) -> list[ReviewSession]:
        """List all stored review sessions."""
        pass

    @abc.abstractmethod
    def get_history(self, session_id: str, page_number: Optional[int] = None) -> list[ReviewHistoryEntry]:
        """Retrieve chronological history entries for a session or page."""
        pass

    @abc.abstractmethod
    def get_document_summary(self, session_id: str) -> Optional[DocumentReviewSummary]:
        """Retrieve the current document review summary for a session."""
        pass

    @abc.abstractmethod
    def delete_session(self, session_id: str) -> bool:
        """Delete a review session and its associated records and history."""
        pass


class SQLiteReviewRepository(ReviewRepository):
    """Persistent SQLite implementation of ReviewRepository."""

    def __init__(self, db_path: Union[str, Path] = ":memory:") -> None:
        """Initialize repository and verify/apply schema migrations.

        Args:
            db_path: Path to SQLite database file or ':memory:'.
        """
        self.db_path = str(db_path)
        self.is_memory = (self.db_path == ":memory:")

        # For in-memory database, hold open connection
        if self.is_memory:
            self._memory_conn = sqlite3.connect(":memory:")
            self._memory_conn.row_factory = sqlite3.Row
            self._memory_conn.execute("PRAGMA foreign_keys = ON;")
            init_database(self.db_path)
            # Reapply schema on memory connection
            from app.crop.review.db import SCHEMA_V1_DDL
            self._memory_conn.executescript(SCHEMA_V1_DDL)
        else:
            init_database(self.db_path)
            self._memory_conn = None

    @contextlib.contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager providing an SQLite connection with foreign keys enabled."""
        if self.is_memory and self._memory_conn is not None:
            yield self._memory_conn
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            try:
                yield conn
            finally:
                conn.close()

    def session_exists(self, session_id: str) -> bool:
        """Return True if session_id exists in the database."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM review_sessions WHERE session_id = ?;", (session_id,))
            return cur.fetchone() is not None

    def create_session(self, session: ReviewSession) -> None:
        """Persist a new review session atomically."""
        if self.session_exists(session.session_id):
            raise DuplicateSessionError(f"Review session '{session.session_id}' already exists.")

        sum_m = session.document_summary
        now_utc = session.created_at.isoformat()
        up_utc = session.updated_at.isoformat()
        rev_utc = sum_m.reviewed_at.isoformat() if sum_m.reviewed_at else None

        with self._get_connection() as conn:
            with conn:
                # 1. Insert session record
                conn.execute(
                    """
                    INSERT INTO review_sessions (
                        session_id, source_filename, total_pages, status,
                        approved_pages_count, rejected_pages_count,
                        needs_revision_pages_count, pending_pages_count,
                        is_review_completed, requires_production_authorization,
                        summary_message, unresolved_discrepancies,
                        created_at, updated_at, reviewed_at, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        session.session_id,
                        session.source_filename,
                        sum_m.total_pages,
                        sum_m.status.value,
                        sum_m.approved_pages_count,
                        sum_m.rejected_pages_count,
                        sum_m.needs_revision_pages_count,
                        sum_m.pending_pages_count,
                        1 if sum_m.is_review_completed else 0,
                        1 if sum_m.requires_production_authorization else 0,
                        sum_m.summary_message,
                        json.dumps(sum_m.unresolved_discrepancies),
                        now_utc,
                        up_utc,
                        rev_utc,
                        json.dumps(session.metadata),
                    ),
                )

                # 2. Insert page records
                for p in session.page_records:
                    p_rev_utc = p.reviewed_at.isoformat() if p.reviewed_at else None
                    conn.execute(
                        """
                        INSERT INTO page_review_records (
                            session_id, pdf_page_index, pdf_page_number, layout_type,
                            classification_status, crop_readiness, review_decision,
                            reviewer_id, reviewed_at, notes, warnings,
                            unresolved_discrepancies, is_cover, is_non_nominal
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            session.session_id,
                            p.pdf_page_index,
                            p.pdf_page_number,
                            p.layout_type.value if p.layout_type else None,
                            p.classification_status.value,
                            p.crop_readiness.value,
                            p.review_decision.value,
                            p.reviewer_id,
                            p_rev_utc,
                            p.notes,
                            json.dumps(p.warnings),
                            json.dumps(p.unresolved_discrepancies),
                            1 if p.is_cover else 0,
                            1 if p.is_non_nominal else 0,
                        ),
                    )

                # 3. Insert initial history entries
                for h in session.history.entries:
                    h_ts = h.timestamp.isoformat()
                    conn.execute(
                        """
                        INSERT INTO review_history (
                            entry_id, session_id, pdf_page_index, pdf_page_number,
                            event_type, previous_decision, new_decision,
                            reviewer_id, timestamp, notes, reason
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            h.entry_id,
                            session.session_id,
                            h.pdf_page_index,
                            h.pdf_page_number,
                            h.event_type.value,
                            h.previous_decision.value if h.previous_decision else None,
                            h.new_decision.value if h.new_decision else None,
                            h.reviewer_id,
                            h_ts,
                            h.notes,
                            h.reason,
                        ),
                    )

    def get_session(self, session_id: str) -> Optional[ReviewSession]:
        """Retrieve a complete ReviewSession by ID."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM review_sessions WHERE session_id = ?;", (session_id,))
            s_row = cur.fetchone()
            if not s_row:
                return None

            # Retrieve pages
            cur.execute(
                "SELECT * FROM page_review_records WHERE session_id = ? ORDER BY pdf_page_index ASC;",
                (session_id,),
            )
            p_rows = cur.fetchall()

            # Retrieve history
            cur.execute(
                "SELECT * FROM review_history WHERE session_id = ? ORDER BY rowid ASC;",
                (session_id,),
            )
            h_rows = cur.fetchall()

        # Reconstruct history
        all_history_entries: list[ReviewHistoryEntry] = []
        page_history_map: dict[int, list[ReviewHistoryEntry]] = {}

        for hr in h_rows:
            entry = ReviewHistoryEntry(
                entry_id=hr["entry_id"],
                pdf_page_index=hr["pdf_page_index"],
                pdf_page_number=hr["pdf_page_number"],
                event_type=ReviewEventType(hr["event_type"]),
                previous_decision=ReviewDecisionState(hr["previous_decision"]) if hr["previous_decision"] else None,
                new_decision=ReviewDecisionState(hr["new_decision"]) if hr["new_decision"] else None,
                reviewer_id=hr["reviewer_id"],
                timestamp=datetime.fromisoformat(hr["timestamp"]),
                notes=hr["notes"],
                reason=hr["reason"],
            )
            all_history_entries.append(entry)
            if hr["pdf_page_number"] is not None:
                page_history_map.setdefault(hr["pdf_page_number"], []).append(entry)

        # Reconstruct page records
        page_records: list[PageReviewRecord] = []
        for pr in p_rows:
            p_num = pr["pdf_page_number"]
            rec = PageReviewRecord(
                pdf_page_index=pr["pdf_page_index"],
                pdf_page_number=p_num,
                layout_type=LayoutType(pr["layout_type"]) if pr["layout_type"] else None,
                classification_status=ClassificationStatus(pr["classification_status"]),
                crop_readiness=CropReadinessStatus(pr["crop_readiness"]),
                review_decision=ReviewDecisionState(pr["review_decision"]),
                reviewer_id=pr["reviewer_id"],
                reviewed_at=datetime.fromisoformat(pr["reviewed_at"]) if pr["reviewed_at"] else None,
                notes=pr["notes"],
                warnings=json.loads(pr["warnings"]),
                unresolved_discrepancies=json.loads(pr["unresolved_discrepancies"]),
                is_cover=bool(pr["is_cover"]),
                is_non_nominal=bool(pr["is_non_nominal"]),
                history=page_history_map.get(p_num, []),
            )
            page_records.append(rec)

        # Reconstruct document summary
        summary = DocumentReviewSummary(
            session_id=s_row["session_id"],
            source_filename=s_row["source_filename"],
            total_pages=s_row["total_pages"],
            approved_pages_count=s_row["approved_pages_count"],
            rejected_pages_count=s_row["rejected_pages_count"],
            needs_revision_pages_count=s_row["needs_revision_pages_count"],
            pending_pages_count=s_row["pending_pages_count"],
            status=DocumentReviewStatus(s_row["status"]),
            is_review_completed=bool(s_row["is_review_completed"]),
            requires_production_authorization=bool(s_row["requires_production_authorization"]),
            summary_message=s_row["summary_message"],
            unresolved_discrepancies=json.loads(s_row["unresolved_discrepancies"]),
            reviewed_at=datetime.fromisoformat(s_row["reviewed_at"]) if s_row["reviewed_at"] else None,
        )

        return ReviewSession(
            session_id=s_row["session_id"],
            source_filename=s_row["source_filename"],
            created_at=datetime.fromisoformat(s_row["created_at"]),
            updated_at=datetime.fromisoformat(s_row["updated_at"]),
            page_records=page_records,
            document_summary=summary,
            history=ReviewHistory(entries=all_history_entries),
            metadata=json.loads(s_row["metadata_json"]),
        )

    def get_page_record(self, session_id: str, page_number: int) -> Optional[PageReviewRecord]:
        """Retrieve a single PageReviewRecord with its page-specific history."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM page_review_records WHERE session_id = ? AND pdf_page_number = ?;",
                (session_id, page_number),
            )
            pr = cur.fetchone()
            if not pr:
                return None

            cur.execute(
                "SELECT * FROM review_history WHERE session_id = ? AND pdf_page_number = ? ORDER BY rowid ASC;",
                (session_id, page_number),
            )
            h_rows = cur.fetchall()

        history_entries = [
            ReviewHistoryEntry(
                entry_id=hr["entry_id"],
                pdf_page_index=hr["pdf_page_index"],
                pdf_page_number=hr["pdf_page_number"],
                event_type=ReviewEventType(hr["event_type"]),
                previous_decision=ReviewDecisionState(hr["previous_decision"]) if hr["previous_decision"] else None,
                new_decision=ReviewDecisionState(hr["new_decision"]) if hr["new_decision"] else None,
                reviewer_id=hr["reviewer_id"],
                timestamp=datetime.fromisoformat(hr["timestamp"]),
                notes=hr["notes"],
                reason=hr["reason"],
            )
            for hr in h_rows
        ]

        return PageReviewRecord(
            pdf_page_index=pr["pdf_page_index"],
            pdf_page_number=pr["pdf_page_number"],
            layout_type=LayoutType(pr["layout_type"]) if pr["layout_type"] else None,
            classification_status=ClassificationStatus(pr["classification_status"]),
            crop_readiness=CropReadinessStatus(pr["crop_readiness"]),
            review_decision=ReviewDecisionState(pr["review_decision"]),
            reviewer_id=pr["reviewer_id"],
            reviewed_at=datetime.fromisoformat(pr["reviewed_at"]) if pr["reviewed_at"] else None,
            notes=pr["notes"],
            warnings=json.loads(pr["warnings"]),
            unresolved_discrepancies=json.loads(pr["unresolved_discrepancies"]),
            is_cover=bool(pr["is_cover"]),
            is_non_nominal=bool(pr["is_non_nominal"]),
            history=history_entries,
        )

    def record_page_decision(
        self,
        session_id: str,
        page_number: int,
        page_record: PageReviewRecord,
        history_entry: ReviewHistoryEntry,
        updated_summary: DocumentReviewSummary,
        updated_at: datetime,
    ) -> None:
        """Atomically update page record, insert history entry, and update document summary."""
        p_rev_utc = page_record.reviewed_at.isoformat() if page_record.reviewed_at else None
        h_ts = history_entry.timestamp.isoformat()
        up_utc = updated_at.isoformat()
        sum_rev_utc = updated_summary.reviewed_at.isoformat() if updated_summary.reviewed_at else None

        with self._get_connection() as conn:
            with conn:
                # 1. Update page review record
                conn.execute(
                    """
                    UPDATE page_review_records
                    SET review_decision = ?, reviewer_id = ?, reviewed_at = ?, notes = ?
                    WHERE session_id = ? AND pdf_page_number = ?;
                    """,
                    (
                        page_record.review_decision.value,
                        page_record.reviewer_id,
                        p_rev_utc,
                        page_record.notes,
                        session_id,
                        page_number,
                    ),
                )

                # 2. Insert history event
                conn.execute(
                    """
                    INSERT INTO review_history (
                        entry_id, session_id, pdf_page_index, pdf_page_number,
                        event_type, previous_decision, new_decision,
                        reviewer_id, timestamp, notes, reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        history_entry.entry_id,
                        session_id,
                        history_entry.pdf_page_index,
                        history_entry.pdf_page_number,
                        history_entry.event_type.value,
                        history_entry.previous_decision.value if history_entry.previous_decision else None,
                        history_entry.new_decision.value if history_entry.new_decision else None,
                        history_entry.reviewer_id,
                        h_ts,
                        history_entry.notes,
                        history_entry.reason,
                    ),
                )

                # 3. Update session summary and updated_at timestamp
                conn.execute(
                    """
                    UPDATE review_sessions
                    SET status = ?, approved_pages_count = ?, rejected_pages_count = ?,
                        needs_revision_pages_count = ?, pending_pages_count = ?,
                        is_review_completed = ?, summary_message = ?,
                        unresolved_discrepancies = ?, updated_at = ?, reviewed_at = ?
                    WHERE session_id = ?;
                    """,
                    (
                        updated_summary.status.value,
                        updated_summary.approved_pages_count,
                        updated_summary.rejected_pages_count,
                        updated_summary.needs_revision_pages_count,
                        updated_summary.pending_pages_count,
                        1 if updated_summary.is_review_completed else 0,
                        updated_summary.summary_message,
                        json.dumps(updated_summary.unresolved_discrepancies),
                        up_utc,
                        sum_rev_utc,
                        session_id,
                    ),
                )

    def record_page_notes(
        self,
        session_id: str,
        page_number: int,
        page_record: PageReviewRecord,
        history_entry: ReviewHistoryEntry,
        updated_at: datetime,
    ) -> None:
        """Atomically persist updated page notes and history entry."""
        h_ts = history_entry.timestamp.isoformat()
        up_utc = updated_at.isoformat()

        with self._get_connection() as conn:
            with conn:
                conn.execute(
                    """
                    UPDATE page_review_records
                    SET notes = ?
                    WHERE session_id = ? AND pdf_page_number = ?;
                    """,
                    (page_record.notes, session_id, page_number),
                )

                conn.execute(
                    """
                    INSERT INTO review_history (
                        entry_id, session_id, pdf_page_index, pdf_page_number,
                        event_type, previous_decision, new_decision,
                        reviewer_id, timestamp, notes, reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        history_entry.entry_id,
                        session_id,
                        history_entry.pdf_page_index,
                        history_entry.pdf_page_number,
                        history_entry.event_type.value,
                        history_entry.previous_decision.value if history_entry.previous_decision else None,
                        history_entry.new_decision.value if history_entry.new_decision else None,
                        history_entry.reviewer_id,
                        h_ts,
                        history_entry.notes,
                        history_entry.reason,
                    ),
                )

                conn.execute(
                    "UPDATE review_sessions SET updated_at = ? WHERE session_id = ?;",
                    (up_utc, session_id),
                )

    def list_sessions(self) -> list[ReviewSession]:
        """List all review sessions ordered by creation date descending."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT session_id FROM review_sessions ORDER BY created_at DESC;")
            rows = cur.fetchall()

        sessions: list[ReviewSession] = []
        for r in rows:
            s = self.get_session(r["session_id"])
            if s:
                sessions.append(s)
        return sessions

    def get_history(self, session_id: str, page_number: Optional[int] = None) -> list[ReviewHistoryEntry]:
        """Retrieve chronological history entries for a session or page."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            if page_number is not None:
                cur.execute(
                    "SELECT * FROM review_history WHERE session_id = ? AND pdf_page_number = ? ORDER BY rowid ASC;",
                    (session_id, page_number),
                )
            else:
                cur.execute(
                    "SELECT * FROM review_history WHERE session_id = ? ORDER BY rowid ASC;",
                    (session_id,),
                )
            rows = cur.fetchall()

        return [
            ReviewHistoryEntry(
                entry_id=hr["entry_id"],
                pdf_page_index=hr["pdf_page_index"],
                pdf_page_number=hr["pdf_page_number"],
                event_type=ReviewEventType(hr["event_type"]),
                previous_decision=ReviewDecisionState(hr["previous_decision"]) if hr["previous_decision"] else None,
                new_decision=ReviewDecisionState(hr["new_decision"]) if hr["new_decision"] else None,
                reviewer_id=hr["reviewer_id"],
                timestamp=datetime.fromisoformat(hr["timestamp"]),
                notes=hr["notes"],
                reason=hr["reason"],
            )
            for hr in rows
        ]

    def get_document_summary(self, session_id: str) -> Optional[DocumentReviewSummary]:
        """Retrieve DocumentReviewSummary for a session."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM review_sessions WHERE session_id = ?;", (session_id,))
            r = cur.fetchone()
            if not r:
                return None

        return DocumentReviewSummary(
            session_id=r["session_id"],
            source_filename=r["source_filename"],
            total_pages=r["total_pages"],
            approved_pages_count=r["approved_pages_count"],
            rejected_pages_count=r["rejected_pages_count"],
            needs_revision_pages_count=r["needs_revision_pages_count"],
            pending_pages_count=r["pending_pages_count"],
            status=DocumentReviewStatus(r["status"]),
            is_review_completed=bool(r["is_review_completed"]),
            requires_production_authorization=bool(r["requires_production_authorization"]),
            summary_message=r["summary_message"],
            unresolved_discrepancies=json.loads(r["unresolved_discrepancies"]),
            reviewed_at=datetime.fromisoformat(r["reviewed_at"]) if r["reviewed_at"] else None,
        )

    def delete_session(self, session_id: str) -> bool:
        """Delete a review session and all cascading records. Returns True if deleted."""
        with self._get_connection() as conn:
            with conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM review_sessions WHERE session_id = ?;", (session_id,))
                return cur.rowcount > 0

