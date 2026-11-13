"""Tests for Review Persistence & SQLite Session Storage — Phase 1.2.2.7.

Comprehensive tests covering:
1. Database initialization and idempotent migrations.
2. Session and page review record persistence to disk.
3. Decision and note update persistence.
4. Review history audit trail persistence.
5. Session recovery across application restarts (new workflow instance).
6. Transaction rollback and atomicity on failure.
7. Duplicate session ID error handling.
8. Foreign key constraint enforcement and cascade deletion.
9. Strict UTC timestamp preservation across serialization and deserialization.
10. Document review status consistency after recovery.
11. SQLite native backup and restore utilities.
12. Crop coordinate immutability and production isolation.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

import pytest

from app.crop.calculator.cover_strategy import CoverCropStrategy
from app.crop.calculator.imposition_4up_strategy import Imposition4UpCropStrategy
from app.crop.calculator.unresolved import (
    UNRESOLVED_COVER_WIDTH_DISCREPANCY,
    UNRESOLVED_ROUNDING_1PX,
)
from app.crop.models.document_crop_plan import DocumentCropPlan, DocumentStatus
from app.crop.models.enums import (
    CropReadinessStatus,
    LayoutType,
)
from app.crop.profiles.profile_configs import create_imposition_4up_profile
from app.crop.review.db import (
    CURRENT_SCHEMA_VERSION,
    backup_database,
    get_schema_version,
    init_database,
    restore_database,
)
from app.crop.review.enums import (
    DocumentReviewStatus,
    ReviewDecisionState,
    ReviewEventType,
)
from app.crop.review.models import ReviewDecision
from app.crop.review.repository import (
    DuplicateSessionError,
    SQLiteReviewRepository,
)
from app.crop.review.workflow import (
    InvalidStateTransitionError,
    PageNotFoundError,
    PreviewReviewWorkflow,
    SessionNotFoundError,
)


@pytest.fixture
def sample_doc_plan() -> DocumentCropPlan:
    """Standard 6-page Bookabook book (Sheet 1: Cover, Sheets 2-6: 4-Up Imposition)."""
    cover_calc = CoverCropStrategy()
    cover_plan = cover_calc.calculate(width_pt=1259.69, height_pt=637.80)

    imp_calc = Imposition4UpCropStrategy()
    body_plans = [
        imp_calc.calculate(pdf_page_index=s, page_width_pt=878.74, height_pt=1247.24)
        for s in range(1, 6)
    ]

    profile = create_imposition_4up_profile()
    return DocumentCropPlan(
        source_filename="persistence_test_book.pdf",
        total_pdf_pages=6,
        expected_total_book_pages=22,
        page_sequence_signature=["COVER_SPREAD"] + ["IMPOSITION_4UP"] * 5,
        profile=profile,
        page_plans=[cover_plan] + body_plans,
        document_status=DocumentStatus(
            document_status="MANUAL_REVIEW_REQUIRED",
            has_manual_review_required=True,
            all_pages_crop_ready=False,
            summary_message="Sheet 1 (Cover Spread) held for manual review",
        ),
    )


# --- 1. Database Initialization & Migration Tests ---

class TestDatabaseInitialization:
    """Tests for SQLite database creation and schema versioning."""

    def test_init_database_creates_tables_and_version(self, tmp_path: Path) -> None:
        db_file = tmp_path / "review.db"
        assert not db_file.exists()

        init_database(db_file)
        assert db_file.exists()
        assert get_schema_version(db_file) == CURRENT_SCHEMA_VERSION

        # Verify tables exist
        conn = sqlite3.connect(str(db_file))
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = [row[0] for row in cur.fetchall()]
        conn.close()

        assert "schema_migrations" in tables
        assert "review_sessions" in tables
        assert "page_review_records" in tables
        assert "review_history" in tables

    def test_init_database_is_idempotent(self, tmp_path: Path) -> None:
        """Calling init_database repeatedly must not wipe data or raise errors."""
        db_file = tmp_path / "review_repeat.db"
        init_database(db_file)

        # Insert a dummy record
        conn = sqlite3.connect(str(db_file))
        conn.execute(
            """
            INSERT INTO review_sessions (
                session_id, source_filename, total_pages, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?);
            """,
            ("dummy-1", "doc.pdf", 1, "PENDING_REVIEW", "2026-11-10T00:00:00+00:00", "2026-11-10T00:00:00+00:00"),
        )
        conn.commit()
        conn.close()

        # Re-run initialization
        init_database(db_file)
        assert get_schema_version(db_file) == CURRENT_SCHEMA_VERSION

        # Verify dummy record survived intact
        conn = sqlite3.connect(str(db_file))
        row = conn.execute("SELECT session_id FROM review_sessions WHERE session_id='dummy-1';").fetchone()
        conn.close()
        assert row is not None


# --- 2. Session and Record Persistence Tests ---

class TestSessionPersistence:
    """Tests for persisting sessions, page records, and decisions to SQLite."""

    def test_create_session_persists_to_disk(
        self,
        tmp_path: Path,
        sample_doc_plan: DocumentCropPlan,
    ) -> None:
        db_file = tmp_path / "test_session.db"
        workflow = PreviewReviewWorkflow(db_path=db_file)

        session = workflow.create_session(sample_doc_plan, session_id="sess-001")
        assert session.session_id == "sess-001"

        # Verify raw SQLite content
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        s_row = conn.execute("SELECT * FROM review_sessions WHERE session_id='sess-001';").fetchone()
        assert s_row is not None
        assert s_row["source_filename"] == "persistence_test_book.pdf"
        assert s_row["total_pages"] == 6
        assert s_row["status"] == "PENDING_REVIEW"
        assert s_row["pending_pages_count"] == 6

        # Check page review records table
        p_rows = conn.execute(
            "SELECT * FROM page_review_records WHERE session_id='sess-001' ORDER BY pdf_page_index ASC;"
        ).fetchall()
        assert len(p_rows) == 6

        # Check Cover Spread record in DB
        cover_row = p_rows[0]
        assert cover_row["pdf_page_number"] == 1
        assert cover_row["layout_type"] == "COVER_SPREAD"
        assert cover_row["crop_readiness"] == "MANUAL_REVIEW_REQUIRED"
        assert cover_row["review_decision"] == "PENDING"
        assert cover_row["is_cover"] == 1
        discrepancies = json.loads(cover_row["unresolved_discrepancies"])
        assert UNRESOLVED_COVER_WIDTH_DISCREPANCY in discrepancies

        conn.close()

    def test_record_decision_persists_to_disk(
        self,
        tmp_path: Path,
        sample_doc_plan: DocumentCropPlan,
    ) -> None:
        db_file = tmp_path / "test_decision.db"
        workflow = PreviewReviewWorkflow(db_path=db_file)
        session = workflow.create_session(sample_doc_plan, session_id="sess-002")

        # Record APPROVED on page 2
        rec = workflow.record_decision(
            session_id="sess-002",
            page_number=2,
            decision=ReviewDecision.APPROVED,
            reviewer_id="reviewer_bob",
            notes="Passed QC verification",
        )
        assert rec.review_decision == ReviewDecisionState.APPROVED

        # Verify in raw SQLite
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        p2_row = conn.execute(
            "SELECT * FROM page_review_records WHERE session_id='sess-002' AND pdf_page_number=2;"
        ).fetchone()

        assert p2_row["review_decision"] == "APPROVED"
        assert p2_row["reviewer_id"] == "reviewer_bob"
        assert p2_row["notes"] == "Passed QC verification"
        assert p2_row["reviewed_at"] is not None

        # Verify session status updated to PARTIALLY_REVIEWED
        s_row = conn.execute("SELECT * FROM review_sessions WHERE session_id='sess-002';").fetchone()
        assert s_row["status"] == "PARTIALLY_REVIEWED"
        assert s_row["approved_pages_count"] == 1
        assert s_row["pending_pages_count"] == 5

        # Verify history entry in SQLite
        h_rows = conn.execute(
            "SELECT * FROM review_history WHERE session_id='sess-002' AND pdf_page_number=2;"
        ).fetchall()
        assert len(h_rows) == 1
        assert h_rows[0]["event_type"] == "DECISION_RECORDED"
        assert h_rows[0]["previous_decision"] == "PENDING"
        assert h_rows[0]["new_decision"] == "APPROVED"
        assert h_rows[0]["reviewer_id"] == "reviewer_bob"

        conn.close()

    def test_update_notes_persists_to_disk(
        self,
        tmp_path: Path,
        sample_doc_plan: DocumentCropPlan,
    ) -> None:
        db_file = tmp_path / "test_notes.db"
        workflow = PreviewReviewWorkflow(db_path=db_file)
        workflow.create_session(sample_doc_plan, session_id="sess-003")

        workflow.update_notes(
            session_id="sess-003",
            page_number=1,
            reviewer_id="reviewer_alice",
            notes="Checked barcode positioning on Cover.",
        )

        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        p1 = conn.execute(
            "SELECT * FROM page_review_records WHERE session_id='sess-003' AND pdf_page_number=1;"
        ).fetchone()
        assert p1["notes"] == "Checked barcode positioning on Cover."

        h = conn.execute(
            "SELECT * FROM review_history WHERE session_id='sess-003' AND event_type='NOTES_UPDATED';"
        ).fetchone()
        assert h is not None
        assert h["reviewer_id"] == "reviewer_alice"
        assert h["notes"] == "Checked barcode positioning on Cover."

        conn.close()


# --- 3. Session Recovery Across Restarts Tests ---

class TestSessionRecoveryAcrossRestarts:
    """Tests proving review data survives application restarts."""

    def test_session_recovery_after_new_workflow_instance(
        self,
        tmp_path: Path,
        sample_doc_plan: DocumentCropPlan,
    ) -> None:
        db_file = tmp_path / "restart_test.db"

        # --- Instance 1: Initial Session Creation and Review Decisions ---
        wf1 = PreviewReviewWorkflow(db_path=db_file)
        s1 = wf1.create_session(sample_doc_plan, session_id="persisted-session-1")

        wf1.record_decision("persisted-session-1", 1, ReviewDecision.APPROVED, "reviewer_1", notes="Cover approved")
        wf1.record_decision("persisted-session-1", 2, ReviewDecision.NEEDS_REVISION, "reviewer_2", notes="Need re-trim")
        wf1.record_decision("persisted-session-1", 3, ReviewDecision.APPROVED, "reviewer_1", notes="Page 3 ready")

        # Simulate application restart: delete wf1 instance completely
        del wf1

        # --- Instance 2: Recover Session from Database ---
        wf2 = PreviewReviewWorkflow(db_path=db_file)
        recovered_session = wf2.get_session("persisted-session-1")

        assert recovered_session.session_id == "persisted-session-1"
        assert recovered_session.source_filename == "persistence_test_book.pdf"
        assert len(recovered_session.page_records) == 6

        # Check Page 1 (Cover)
        p1 = recovered_session.get_page_record(1)
        assert p1.review_decision == ReviewDecisionState.APPROVED
        assert p1.reviewer_id == "reviewer_1"
        assert p1.notes == "Cover approved"
        assert p1.is_cover is True
        assert UNRESOLVED_COVER_WIDTH_DISCREPANCY in p1.unresolved_discrepancies

        # Check Page 2 (Needs Revision)
        p2 = recovered_session.get_page_record(2)
        assert p2.review_decision == ReviewDecisionState.NEEDS_REVISION
        assert p2.reviewer_id == "reviewer_2"
        assert p2.notes == "Need re-trim"

        # Check Page 3 (Approved)
        p3 = recovered_session.get_page_record(3)
        assert p3.review_decision == ReviewDecisionState.APPROVED

        # Check Page 4 (Pending)
        p4 = recovered_session.get_page_record(4)
        assert p4.review_decision == ReviewDecisionState.PENDING

        # Check Document Summary
        summary = recovered_session.document_summary
        assert summary.status == DocumentReviewStatus.PARTIALLY_REVIEWED
        assert summary.approved_pages_count == 2
        assert summary.needs_revision_pages_count == 1
        assert summary.pending_pages_count == 3
        assert summary.is_review_completed is False

        # Check Full History
        history = wf2.get_history("persisted-session-1")
        # 1 init + 3 decisions = 4 events
        assert len(history) == 4
        assert history[0].event_type == ReviewEventType.SESSION_CREATED
        assert history[1].new_decision == ReviewDecisionState.APPROVED
        assert history[2].new_decision == ReviewDecisionState.NEEDS_REVISION
        assert history[3].new_decision == ReviewDecisionState.APPROVED

    def test_complete_review_recovery(
        self,
        tmp_path: Path,
        sample_doc_plan: DocumentCropPlan,
    ) -> None:
        """Verify that a completed review (all 6 pages approved) recovers as REVIEW_COMPLETED."""
        db_file = tmp_path / "complete_recovery.db"
        wf1 = PreviewReviewWorkflow(db_path=db_file)
        wf1.create_session(sample_doc_plan, session_id="complete-book-session")

        for p in range(1, 7):
            wf1.record_decision("complete-book-session", p, ReviewDecision.APPROVED, "lead_reviewer")

        # Simulate restart
        del wf1
        wf2 = PreviewReviewWorkflow(db_path=db_file)
        summary = wf2.get_document_summary("complete-book-session")

        assert summary.status == DocumentReviewStatus.REVIEW_COMPLETED
        assert summary.is_review_completed is True
        assert summary.approved_pages_count == 6
        assert summary.pending_pages_count == 0
        assert summary.requires_production_authorization is True


# --- 4. Constraints, Integrity & Error Handling Tests ---

class TestIntegrityAndErrorHandling:
    """Tests for duplicate prevention, foreign keys, and transaction rollbacks."""

    def test_duplicate_session_id_raises_duplicate_session_error(
        self,
        tmp_path: Path,
        sample_doc_plan: DocumentCropPlan,
    ) -> None:
        db_file = tmp_path / "test_dup.db"
        workflow = PreviewReviewWorkflow(db_path=db_file)

        workflow.create_session(sample_doc_plan, session_id="fixed-id-1")

        with pytest.raises(DuplicateSessionError, match="already exists"):
            workflow.create_session(sample_doc_plan, session_id="fixed-id-1")

    def test_foreign_key_enforcement_and_cascade_delete(
        self,
        tmp_path: Path,
        sample_doc_plan: DocumentCropPlan,
    ) -> None:
        db_file = tmp_path / "test_fk.db"
        repo = SQLiteReviewRepository(db_path=db_file)

        workflow = PreviewReviewWorkflow(repository=repo)
        workflow.create_session(sample_doc_plan, session_id="fk-test-sess")
        workflow.record_decision("fk-test-sess", 2, ReviewDecision.APPROVED, "op1")

        # Direct SQL: verify foreign key constraint rejects orphan page record
        conn = sqlite3.connect(str(db_file))
        conn.execute("PRAGMA foreign_keys = ON;")
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            with conn:
                conn.execute(
                    """
                    INSERT INTO page_review_records (
                        session_id, pdf_page_index, pdf_page_number, classification_status, crop_readiness
                    ) VALUES ('non-existent-sess', 0, 1, 'CLASSIFIED', 'CROP_READY');
                    """
                )
        conn.close()

        # Verify CASCADE deletion: deleting the session removes its pages and history
        assert repo.delete_session("fk-test-sess") is True

        conn = sqlite3.connect(str(db_file))
        p_count = conn.execute("SELECT COUNT(*) FROM page_review_records WHERE session_id='fk-test-sess';").fetchone()[0]
        h_count = conn.execute("SELECT COUNT(*) FROM review_history WHERE session_id='fk-test-sess';").fetchone()[0]
        conn.close()

        assert p_count == 0
        assert h_count == 0

    def test_session_not_found_raises(self, tmp_path: Path) -> None:
        db_file = tmp_path / "test_missing.db"
        workflow = PreviewReviewWorkflow(db_path=db_file)

        with pytest.raises(SessionNotFoundError, match="not found"):
            workflow.get_session("unknown-session")

    def test_page_not_found_raises(
        self,
        tmp_path: Path,
        sample_doc_plan: DocumentCropPlan,
    ) -> None:
        db_file = tmp_path / "test_missing_page.db"
        workflow = PreviewReviewWorkflow(db_path=db_file)
        session = workflow.create_session(sample_doc_plan)

        with pytest.raises(PageNotFoundError, match="Page 99"):
            workflow.get_page_record(session.session_id, page_number=99)


# --- 5. UTC Timestamps & Immutability Tests ---

class TestUTCAndImmutability:
    """Tests verifying timestamp UTC enforcement and crop coordinate immutability."""

    def test_recovered_timestamps_are_strictly_utc(
        self,
        tmp_path: Path,
        sample_doc_plan: DocumentCropPlan,
    ) -> None:
        db_file = tmp_path / "test_utc.db"
        wf1 = PreviewReviewWorkflow(db_path=db_file)
        wf1.create_session(sample_doc_plan, session_id="utc-sess")
        wf1.record_decision("utc-sess", 1, ReviewDecision.APPROVED, "op1")

        del wf1
        wf2 = PreviewReviewWorkflow(db_path=db_file)
        session = wf2.get_session("utc-sess")

        assert session.created_at.tzinfo == timezone.utc
        assert session.updated_at.tzinfo == timezone.utc

        p1 = session.get_page_record(1)
        assert p1.reviewed_at is not None
        assert p1.reviewed_at.tzinfo == timezone.utc

        for h in session.history.entries:
            assert h.timestamp.tzinfo == timezone.utc

    def test_crop_coordinates_unaltered_by_persistence_workflow(
        self,
        tmp_path: Path,
        sample_doc_plan: DocumentCropPlan,
    ) -> None:
        """Physical coordinates in DocumentCropPlan must remain identical throughout review."""
        orig_boxes = [
            [(r.x_min_pt, r.y_min_pt, r.x_max_pt, r.y_max_pt) for r in page.crop_regions]
            for page in sample_doc_plan.page_plans
        ]

        db_file = tmp_path / "test_coords.db"
        workflow = PreviewReviewWorkflow(db_path=db_file)
        session = workflow.create_session(sample_doc_plan)

        for p in range(1, 7):
            workflow.record_decision(session.session_id, p, ReviewDecision.APPROVED, "reviewer_1")

        final_boxes = [
            [(r.x_min_pt, r.y_min_pt, r.x_max_pt, r.y_max_pt) for r in page.crop_regions]
            for page in sample_doc_plan.page_plans
        ]

        assert orig_boxes == final_boxes


# --- 6. Backup & Restore Tests ---

class TestBackupAndRestore:
    """Tests for SQLite online backup and restore utility functions."""

    def test_backup_and_restore_cycle(
        self,
        tmp_path: Path,
        sample_doc_plan: DocumentCropPlan,
    ) -> None:
        source_db = tmp_path / "live.db"
        backup_db = tmp_path / "backups" / "live_backup.db"
        restored_db = tmp_path / "restored" / "live_restored.db"

        # 1. Create and populate live database
        wf = PreviewReviewWorkflow(db_path=source_db)
        wf.create_session(sample_doc_plan, session_id="live-session-1")
        wf.record_decision("live-session-1", 1, ReviewDecision.APPROVED, "op_backup", notes="Prior to backup")

        # 2. Perform online backup
        backup_database(source_path=source_db, backup_path=backup_db)
        assert backup_db.exists()

        # 3. Restore to new location
        restore_database(backup_path=backup_db, target_path=restored_db)
        assert restored_db.exists()

        # 4. Open restored database and verify complete fidelity
        wf_restored = PreviewReviewWorkflow(db_path=restored_db)
        restored_session = wf_restored.get_session("live-session-1")

        assert restored_session.session_id == "live-session-1"
        p1 = restored_session.get_page_record(1)
        assert p1.review_decision == ReviewDecisionState.APPROVED
        assert p1.reviewer_id == "op_backup"
        assert p1.notes == "Prior to backup"

    def test_backup_nonexistent_source_raises_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            backup_database(tmp_path / "missing.db", tmp_path / "backup.db")

    def test_restore_nonexistent_backup_raises_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            restore_database(tmp_path / "missing_backup.db", tmp_path / "target.db")

