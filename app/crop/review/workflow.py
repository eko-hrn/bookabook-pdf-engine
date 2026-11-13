"""Preview Review Workflow Engine (Phase 1.2.2.6 & Phase 1.2.2.7).

Manages review sessions, enforces review decision state transitions,
tracks immutable audit history, and persists all data to SQLite storage.

Strict Guarantees:
1. Immutability: Never alters source PDF, crop formulas, or crop coordinates.
2. Safety: UNKNOWN_LAYOUT pages cannot be approved; REJECTED pages cannot proceed.
3. Cover review: Cover Spread remains MANUAL_REVIEW_REQUIRED until explicitly approved.
4. Non-nominal Single Page: Preserves normalization policy hold and warnings.
5. UTC Timestamps: All timestamps are recorded strictly in UTC.
6. Separation of Concerns: REVIEW_COMPLETED is distinct from production rendering authorization.
7. Persistence: All sessions, decisions, notes, and history survive application restarts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union
import uuid

from app.crop.calculator.unresolved import (
    UNRESOLVED_COVER_WIDTH_DISCREPANCY,
    UNRESOLVED_ROUNDING_1PX,
    UNRESOLVED_SINGLE_PAGE_NORMALIZATION_POLICY,
)
from app.crop.models.document_crop_plan import DocumentCropPlan
from app.crop.models.enums import (
    ClassificationStatus,
    CropReadinessStatus,
    LayoutType,
)
from app.crop.preview.models import PreviewDocumentPayload
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
from app.crop.review.repository import (
    DuplicateSessionError,
    ReviewRepository,
    SQLiteReviewRepository,
)
from app.crop.validator.report import DocumentValidationReport


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal review state transition is attempted."""

    pass


class SessionNotFoundError(KeyError):
    """Raised when a requested review session ID does not exist."""

    pass


class PageNotFoundError(KeyError):
    """Raised when a requested page number is not found in the review session."""

    pass


class PreviewReviewWorkflow:
    """Coordinator for preview inspection, review decisions, and persistent session storage."""

    def __init__(
        self,
        db_path: Optional[Union[str, Path]] = None,
        repository: Optional[ReviewRepository] = None,
    ) -> None:
        """Initialize workflow with a persistent or in-memory repository.

        Args:
            db_path: Path to SQLite database file or ':memory:'. If None and repository is None,
                     defaults to ':memory:' for isolated, non-destructive test execution.
            repository: Custom ReviewRepository instance.
        """
        if repository is not None:
            self._repo: ReviewRepository = repository
        elif db_path is not None:
            self._repo = SQLiteReviewRepository(db_path=db_path)
        else:
            self._repo = SQLiteReviewRepository(db_path=":memory:")

        # In-memory reference cache for active instances in the current session
        self._sessions_cache: dict[str, ReviewSession] = {}

    def create_session(
        self,
        doc_plan: DocumentCropPlan,
        preview_payload: Optional[PreviewDocumentPayload] = None,
        validation_report: Optional[DocumentValidationReport] = None,
        session_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ReviewSession:
        """Create and persist a new ReviewSession from a DocumentCropPlan.

        Initializes all pages in PENDING state and captures warnings,
        unresolved discrepancies, and layout metadata.

        Args:
            doc_plan: Validated DocumentCropPlan containing page plans.
            preview_payload: Optional PreviewDocumentPayload from PreviewVisualizationEngine.
            validation_report: Optional DocumentValidationReport from CropPlanValidator.
            session_id: Optional explicit session ID (defaults to new UUID4).
            metadata: Optional additional metadata dictionary.

        Returns:
            Newly initialized and persisted ReviewSession.
        """
        sid = session_id or str(uuid.uuid4())
        now_utc = datetime.now(timezone.utc)

        if self._repo.session_exists(sid):
            raise DuplicateSessionError(f"Review session '{sid}' already exists.")

        page_records: list[PageReviewRecord] = []
        doc_discrepancies: set[str] = set()

        for page_plan in doc_plan.page_plans:
            # 1. Collect warnings from all available sources
            page_warnings: list[str] = [f.value for f in page_plan.manual_review_flags]
            page_discrepancies: list[str] = []

            # 2. Check layout-specific discrepancies
            is_cover = (page_plan.layout_type == LayoutType.COVER_SPREAD)
            is_non_nominal = False

            if is_cover:
                page_discrepancies.append(UNRESOLVED_COVER_WIDTH_DISCREPANCY)
                page_discrepancies.append(UNRESOLVED_ROUNDING_1PX)
                page_warnings.append("Cover Spread auto-crop is disabled. Hold for manual review.")

            if page_plan.layout_type == LayoutType.SINGLE_PAGE:
                if round(page_plan.width_pt, 2) != 425.52 or round(page_plan.height_pt, 2) != 609.12:
                    is_non_nominal = True
                    page_discrepancies.append(UNRESOLVED_SINGLE_PAGE_NORMALIZATION_POLICY)
                    page_warnings.append(
                        f"Non-nominal single page dimensions ({page_plan.width_pt:.2f}x{page_plan.height_pt:.2f} pt)."
                    )

            # 3. Incorporate preview payload warnings/discrepancies if available
            if preview_payload is not None:
                for p_prev in preview_payload.pages:
                    if p_prev.pdf_page_number == page_plan.pdf_page_number:
                        for w in p_prev.warnings:
                            if w not in page_warnings:
                                page_warnings.append(w)
                        for d in p_prev.unresolved_discrepancies:
                            if d not in page_discrepancies:
                                page_discrepancies.append(d)

            # 4. Incorporate validator report warnings if available
            if validation_report is not None:
                for p_val in validation_report.page_reports:
                    if p_val.pdf_page_number == page_plan.pdf_page_number:
                        for w in p_val.warnings:
                            if w not in page_warnings:
                                page_warnings.append(w)

            doc_discrepancies.update(page_discrepancies)

            record = PageReviewRecord(
                pdf_page_index=page_plan.pdf_page_index,
                pdf_page_number=page_plan.pdf_page_number,
                layout_type=page_plan.layout_type,
                classification_status=page_plan.classification_status,
                crop_readiness=page_plan.crop_readiness,
                review_decision=ReviewDecisionState.PENDING,
                reviewer_id=None,
                reviewed_at=None,
                notes=None,
                warnings=page_warnings,
                unresolved_discrepancies=page_discrepancies,
                is_cover=is_cover,
                is_non_nominal=is_non_nominal,
                history=[],
            )
            page_records.append(record)

        # Create history and initial event
        history = ReviewHistory()
        init_event = ReviewHistoryEntry(
            pdf_page_index=None,
            pdf_page_number=None,
            event_type=ReviewEventType.SESSION_CREATED,
            previous_decision=None,
            new_decision=ReviewDecisionState.PENDING,
            reviewer_id="SYSTEM",
            timestamp=now_utc,
            notes=f"Review session created for document '{doc_plan.source_filename}' ({len(page_records)} pages)",
            reason="INITIALIZATION",
        )
        history.add_entry(init_event)

        # Calculate initial DocumentReviewSummary
        initial_summary = self._calculate_document_summary(
            pages=page_records,
            session_id=sid,
            source_filename=doc_plan.source_filename,
            unresolved_discrepancies=doc_discrepancies,
        )

        session = ReviewSession(
            session_id=sid,
            source_filename=doc_plan.source_filename,
            created_at=now_utc,
            updated_at=now_utc,
            page_records=page_records,
            document_summary=initial_summary,
            history=history,
            metadata=metadata or {},
        )

        # Persist to database
        self._repo.create_session(session)
        self._sessions_cache[sid] = session
        return session

    def get_session(self, session_id: str) -> ReviewSession:
        """Retrieve a ReviewSession by its session ID.

        Raises:
            SessionNotFoundError: If session_id does not exist.
        """
        session = self._repo.get_session(session_id)
        if session is None:
            raise SessionNotFoundError(f"Review session '{session_id}' not found.")
        return session

    def list_sessions(self) -> list[ReviewSession]:
        """Return all active ReviewSessions."""
        return self._repo.list_sessions()

    def get_page_record(self, session_id: str, page_number: int) -> PageReviewRecord:
        """Retrieve a PageReviewRecord by 1-based page number.

        Raises:
            SessionNotFoundError: If session does not exist.
            PageNotFoundError: If page_number is not in the session.
        """
        if not self._repo.session_exists(session_id):
            raise SessionNotFoundError(f"Review session '{session_id}' not found.")

        record = self._repo.get_page_record(session_id, page_number)
        if record is None:
            raise PageNotFoundError(f"Page {page_number} not found in review session '{session_id}'.")
        return record

    def record_decision(
        self,
        session_id: str,
        page_number: int,
        decision: Union[ReviewDecisionState, str],
        reviewer_id: str,
        notes: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> PageReviewRecord:
        """Record an explicit operator review decision for a page.

        Enforces all state transition rules:
        - UNKNOWN_LAYOUT pages cannot be approved.
        - REJECTED pages cannot proceed directly to APPROVED.
        - Already reviewed pages cannot be reverted to PENDING.
        - Cover Spread requires an explicit reviewer decision.
        - Records immutable history entries with UTC timestamps.
        - Persists all changes atomically in a database transaction.

        Args:
            session_id: Review session ID.
            page_number: 1-based PDF page number.
            decision: Target decision (APPROVED, REJECTED, NEEDS_REVISION, PENDING).
            reviewer_id: Identifier of the operator/reviewer.
            notes: Optional review notes.
            reason: Optional justification or revision request.

        Returns:
            Updated PageReviewRecord.
        """
        if not reviewer_id or not reviewer_id.strip():
            raise ValueError("Reviewer identifier must be a non-empty string.")

        target_state = ReviewDecisionState(decision)
        session = self.get_session(session_id)
        page_record = self.get_page_record(session_id, page_number)
        current_state = page_record.review_decision

        # --- Rule 1: UNKNOWN_LAYOUT Restriction ---
        if (
            page_record.classification_status == ClassificationStatus.UNKNOWN_LAYOUT
            or page_record.layout_type is None
        ):
            if target_state == ReviewDecisionState.APPROVED:
                raise InvalidStateTransitionError(
                    f"Page {page_number} has classification UNKNOWN_LAYOUT and cannot be approved."
                )

        # --- Rule 2: REJECTED Pages Cannot Proceed Directly ---
        if current_state == ReviewDecisionState.REJECTED and target_state == ReviewDecisionState.APPROVED:
            raise InvalidStateTransitionError(
                f"Page {page_number} is in REJECTED state and cannot proceed directly to APPROVED. "
                f"It must be set to NEEDS_REVISION first."
            )

        # --- Rule 3: Cannot Revert to PENDING ---
        if (
            current_state in (ReviewDecisionState.APPROVED, ReviewDecisionState.REJECTED, ReviewDecisionState.NEEDS_REVISION)
            and target_state == ReviewDecisionState.PENDING
        ):
            raise InvalidStateTransitionError(
                f"Page {page_number} has already been reviewed ({current_state.value}). "
                f"Cannot revert an evaluated page back to PENDING."
            )

        now_utc = datetime.now(timezone.utc)

        # Create history entry
        history_entry = ReviewHistoryEntry(
            pdf_page_index=page_record.pdf_page_index,
            pdf_page_number=page_number,
            event_type=ReviewEventType.DECISION_RECORDED,
            previous_decision=current_state,
            new_decision=target_state,
            reviewer_id=reviewer_id.strip(),
            timestamp=now_utc,
            notes=notes,
            reason=reason,
        )

        # Apply update in-memory to page record
        page_record.review_decision = target_state
        page_record.reviewer_id = reviewer_id.strip()
        page_record.reviewed_at = now_utc
        if notes:
            page_record.notes = notes

        # Update page list in memory for summary calculation
        updated_pages: list[PageReviewRecord] = []
        for p in session.page_records:
            if p.pdf_page_number == page_number:
                updated_pages.append(page_record)
            else:
                updated_pages.append(p)

        # Re-aggregate document summary
        updated_summary = self._calculate_document_summary(
            pages=updated_pages,
            session_id=session.session_id,
            source_filename=session.source_filename,
        )

        # Persist atomically to database
        self._repo.record_page_decision(
            session_id=session_id,
            page_number=page_number,
            page_record=page_record,
            history_entry=history_entry,
            updated_summary=updated_summary,
            updated_at=now_utc,
        )

        page_record.history.append(history_entry)

        # Synchronize in-memory cache if active
        if session_id in self._sessions_cache:
            cached_s = self._sessions_cache[session_id]
            cached_s.updated_at = now_utc
            cached_s.document_summary = updated_summary
            cached_s.history.add_entry(history_entry)
            for p in cached_s.page_records:
                if p.pdf_page_number == page_number:
                    p.review_decision = target_state
                    p.reviewer_id = reviewer_id.strip()
                    p.reviewed_at = now_utc
                    if notes:
                        p.notes = notes
                    p.history.append(history_entry)

        return page_record

    def update_notes(
        self,
        session_id: str,
        page_number: int,
        reviewer_id: str,
        notes: str,
    ) -> PageReviewRecord:
        """Update review notes on a page record without altering the current decision.

        Args:
            session_id: Review session ID.
            page_number: 1-based page number.
            reviewer_id: Identifier of the operator making the note update.
            notes: New or appended note content.

        Returns:
            Updated PageReviewRecord.
        """
        if not reviewer_id or not reviewer_id.strip():
            raise ValueError("Reviewer identifier must be a non-empty string.")
        if not notes or not notes.strip():
            raise ValueError("Review notes cannot be empty.")

        page_record = self.get_page_record(session_id, page_number)
        now_utc = datetime.now(timezone.utc)

        history_entry = ReviewHistoryEntry(
            pdf_page_index=page_record.pdf_page_index,
            pdf_page_number=page_number,
            event_type=ReviewEventType.NOTES_UPDATED,
            previous_decision=page_record.review_decision,
            new_decision=page_record.review_decision,
            reviewer_id=reviewer_id.strip(),
            timestamp=now_utc,
            notes=notes.strip(),
            reason="NOTES_UPDATE",
        )

        page_record.notes = notes.strip()

        # Persist atomically to database
        self._repo.record_page_notes(
            session_id=session_id,
            page_number=page_number,
            page_record=page_record,
            history_entry=history_entry,
            updated_at=now_utc,
        )

        page_record.history.append(history_entry)

        # Synchronize in-memory cache if active
        if session_id in self._sessions_cache:
            cached_s = self._sessions_cache[session_id]
            cached_s.updated_at = now_utc
            cached_s.history.add_entry(history_entry)
            for p in cached_s.page_records:
                if p.pdf_page_number == page_number:
                    p.notes = notes.strip()
                    p.history.append(history_entry)

        return page_record

    def get_history(
        self,
        session_id: str,
        page_number: Optional[int] = None,
    ) -> list[ReviewHistoryEntry]:
        """Return the chronological audit history for a session or specific page.

        Args:
            session_id: Review session ID.
            page_number: Optional 1-based page number to filter history.

        Returns:
            List of ReviewHistoryEntry objects in chronological order.
        """
        if not self._repo.session_exists(session_id):
            raise SessionNotFoundError(f"Review session '{session_id}' not found.")
        return self._repo.get_history(session_id, page_number)

    def get_document_summary(self, session_id: str) -> DocumentReviewSummary:
        """Return the current DocumentReviewSummary for a session."""
        summary = self._repo.get_document_summary(session_id)
        if summary is None:
            raise SessionNotFoundError(f"Review session '{session_id}' not found.")
        return summary

    def _calculate_document_summary(
        self,
        pages: list[PageReviewRecord],
        session_id: str,
        source_filename: str,
        unresolved_discrepancies: Optional[set[str]] = None,
    ) -> DocumentReviewSummary:
        """Recompute document-level review metrics and status based on all pages."""
        total = len(pages)

        approved = sum(1 for p in pages if p.review_decision == ReviewDecisionState.APPROVED)
        rejected = sum(1 for p in pages if p.review_decision == ReviewDecisionState.REJECTED)
        needs_revision = sum(1 for p in pages if p.review_decision == ReviewDecisionState.NEEDS_REVISION)
        pending = sum(1 for p in pages if p.review_decision == ReviewDecisionState.PENDING)

        has_unknown = any(
            p.classification_status == ClassificationStatus.UNKNOWN_LAYOUT or p.layout_type is None
            for p in pages
        )

        # Status Hierarchy:
        # 1. REVIEW_BLOCKED: UNKNOWN_LAYOUT sheets present that cannot be processed
        # 2. REVIEW_REJECTED: One or more pages have been explicitly rejected
        # 3. REVIEW_COMPLETED: Every single page has been approved
        # 4. PENDING_REVIEW: No pages have been evaluated yet
        # 5. PARTIALLY_REVIEWED: In progress (some approved/revision, some pending)
        if has_unknown:
            status = DocumentReviewStatus.REVIEW_BLOCKED
            msg = "Document contains UNKNOWN_LAYOUT sheets that cannot be approved."
        elif rejected > 0:
            status = DocumentReviewStatus.REVIEW_REJECTED
            msg = f"Document review rejected: {rejected} of {total} page(s) marked REJECTED."
        elif approved == total:
            status = DocumentReviewStatus.REVIEW_COMPLETED
            msg = f"Document review completed: all {total} pages approved by reviewer."
        elif pending == total:
            status = DocumentReviewStatus.PENDING_REVIEW
            msg = f"Review pending: 0 of {total} pages reviewed."
        else:
            status = DocumentReviewStatus.PARTIALLY_REVIEWED
            parts = []
            if approved:
                parts.append(f"{approved} approved")
            if pending:
                parts.append(f"{pending} pending")
            if needs_revision:
                parts.append(f"{needs_revision} needs revision")
            msg = f"Review in progress: {', '.join(parts)}."

        is_completed = (status == DocumentReviewStatus.REVIEW_COMPLETED)
        reviewed_at = (
            datetime.now(timezone.utc)
            if (is_completed or status == DocumentReviewStatus.REVIEW_REJECTED)
            else None
        )

        # Collect all unresolved discrepancies
        all_discrepancies: set[str] = set()
        if unresolved_discrepancies:
            all_discrepancies.update(unresolved_discrepancies)
        for p in pages:
            all_discrepancies.update(p.unresolved_discrepancies)

        return DocumentReviewSummary(
            session_id=session_id,
            source_filename=source_filename,
            total_pages=total,
            approved_pages_count=approved,
            rejected_pages_count=rejected,
            needs_revision_pages_count=needs_revision,
            pending_pages_count=pending,
            status=status,
            is_review_completed=is_completed,
            requires_production_authorization=True,
            summary_message=msg,
            unresolved_discrepancies=sorted(list(all_discrepancies)),
            reviewed_at=reviewed_at,
        )
