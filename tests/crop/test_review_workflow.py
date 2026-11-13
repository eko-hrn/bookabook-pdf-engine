"""Tests for Preview Review Workflow — Phase 1.2.2.6.

Comprehensive unit and integration tests covering:
1. Review session creation from DocumentCropPlan.
2. Page review record attributes, layout types, and readiness states.
3. Every supported review decision (APPROVED, REJECTED, NEEDS_REVISION, PENDING).
4. State transition rules and rejection of invalid transitions.
5. Cover Spread explicit review rules and unresolved discrepancy preservation.
6. UNKNOWN_LAYOUT restrictions (cannot be approved, document is REVIEW_BLOCKED).
7. REJECTED page restrictions (document becomes REVIEW_REJECTED, cannot proceed).
8. Chronological audit history and notes updates.
9. Document-level status aggregation across all states.
10. Strict UTC timestamp enforcement across all models.
11. Immutability of PDF points and crop coordinates during review.
12. Strict production rendering isolation and non-authorization guardrails.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.crop.calculator.cover_strategy import CoverCropStrategy
from app.crop.calculator.imposition_4up_strategy import Imposition4UpCropStrategy
from app.crop.calculator.single_page_strategy import SinglePageCropStrategy
from app.crop.calculator.unresolved import (
    UNRESOLVED_COVER_WIDTH_DISCREPANCY,
    UNRESOLVED_ROUNDING_1PX,
    UNRESOLVED_SINGLE_PAGE_NORMALIZATION_POLICY,
)
from app.crop.models.crop_region import CropRegion
from app.crop.models.document_crop_plan import DocumentCropPlan, DocumentStatus
from app.crop.models.enums import (
    BlankPageStatus,
    ClassificationStatus,
    CropReadinessStatus,
    CropStrategyType,
    LayoutType,
    Orientation,
)
from app.crop.models.page_crop_plan import PageCropPlan
from app.crop.preview.engine import PreviewVisualizationEngine
from app.crop.profiles.profile_configs import (
    create_cover_profile,
    create_imposition_4up_profile,
    create_single_page_profile,
)
from app.crop.review.enums import (
    DocumentReviewStatus,
    ReviewDecisionState,
    ReviewEventType,
)
from app.crop.review.models import (
    DocumentReviewSummary,
    PageReviewRecord,
    ReviewDecision,
    ReviewHistory,
    ReviewHistoryEntry,
    ReviewSession,
)
from app.crop.review.workflow import (
    InvalidStateTransitionError,
    PageNotFoundError,
    PreviewReviewWorkflow,
    SessionNotFoundError,
)


# --- Test Fixtures ---

@pytest.fixture
def standard_6page_doc_plan() -> DocumentCropPlan:
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
        source_filename="standard_book_6sheets.pdf",
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


@pytest.fixture
def doc_plan_with_unknown_layout() -> DocumentCropPlan:
    """Document containing an unclassified / UNKNOWN_LAYOUT page."""
    profile = create_imposition_4up_profile()

    page_unknown = PageCropPlan(
        pdf_page_index=0,
        pdf_page_number=1,
        width_pt=500.0,
        height_pt=700.0,
        orientation=Orientation.PORTRAIT,
        rotation=0,
        layout_type=None,
        classification_status=ClassificationStatus.UNKNOWN_LAYOUT,
        confidence_score=0.1,
        crop_strategy=None,
        crop_readiness=CropReadinessStatus.NOT_APPLICABLE,
        manual_review_flags=[],
        crop_regions=[],
        expected_page_yield=0,
    )

    imp_calc = Imposition4UpCropStrategy(profile)
    page_4up = imp_calc.calculate(pdf_page_index=1, page_width_pt=878.74, height_pt=1247.24)

    return DocumentCropPlan(
        source_filename="unknown_sheet_book.pdf",
        total_pdf_pages=2,
        expected_total_book_pages=4,
        page_sequence_signature=["UNKNOWN_LAYOUT", "IMPOSITION_4UP"],
        profile=profile,
        page_plans=[page_unknown, page_4up],
        document_status=DocumentStatus(
            document_status="REJECTED_UNKNOWN_LAYOUT",
            has_unknown_layout=True,
            has_manual_review_required=False,
            all_pages_crop_ready=False,
            summary_message="Sheet 1 classified as UNKNOWN_LAYOUT",
        ),
    )


# --- 1. Review Session Creation Tests ---

class TestReviewSessionCreation:
    """Tests for ReviewSession creation and retrieval."""

    def test_create_session_success(self, standard_6page_doc_plan: DocumentCropPlan) -> None:
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(standard_6page_doc_plan)

        assert isinstance(session, ReviewSession)
        assert session.source_filename == "standard_book_6sheets.pdf"
        assert len(session.page_records) == 6
        assert session.document_summary.total_pages == 6
        assert session.document_summary.status == DocumentReviewStatus.PENDING_REVIEW
        assert session.document_summary.pending_pages_count == 6
        assert session.document_summary.approved_pages_count == 0
        assert session.document_summary.is_review_completed is False

    def test_create_session_with_custom_id(self, standard_6page_doc_plan: DocumentCropPlan) -> None:
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(standard_6page_doc_plan, session_id="custom-session-123")

        assert session.session_id == "custom-session-123"
        retrieved = workflow.get_session("custom-session-123")
        assert retrieved.session_id == "custom-session-123"

    def test_get_session_not_found_raises(self) -> None:
        workflow = PreviewReviewWorkflow()
        with pytest.raises(SessionNotFoundError, match="not found"):
            workflow.get_session("non-existent-session-id")

    def test_list_sessions(self, standard_6page_doc_plan: DocumentCropPlan) -> None:
        workflow = PreviewReviewWorkflow()
        assert len(workflow.list_sessions()) == 0

        s1 = workflow.create_session(standard_6page_doc_plan, session_id="s1")
        s2 = workflow.create_session(standard_6page_doc_plan, session_id="s2")

        sessions = workflow.list_sessions()
        assert len(sessions) == 2
        assert s1 in sessions
        assert s2 in sessions

    def test_initial_history_contains_session_created_event(
        self,
        standard_6page_doc_plan: DocumentCropPlan,
    ) -> None:
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(standard_6page_doc_plan)

        assert session.history.total_events == 1
        entry = session.history.entries[0]
        assert entry.event_type == ReviewEventType.SESSION_CREATED
        assert entry.reviewer_id == "SYSTEM"
        assert entry.timestamp.tzinfo == timezone.utc


# --- 2. Page Review Record Tests ---

class TestPageReviewRecord:
    """Tests for individual PageReviewRecord properties and retrieval."""

    def test_page_record_initial_state(self, standard_6page_doc_plan: DocumentCropPlan) -> None:
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(standard_6page_doc_plan)

        # Page 1: Cover Spread
        page1 = session.get_page_record(1)
        assert page1 is not None
        assert page1.pdf_page_number == 1
        assert page1.pdf_page_index == 0
        assert page1.layout_type == LayoutType.COVER_SPREAD
        assert page1.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED
        assert page1.review_decision == ReviewDecisionState.PENDING
        assert page1.is_cover is True
        assert UNRESOLVED_COVER_WIDTH_DISCREPANCY in page1.unresolved_discrepancies
        assert UNRESOLVED_ROUNDING_1PX in page1.unresolved_discrepancies

        # Page 2: 4-Up Imposition
        page2 = session.get_page_record(2)
        assert page2 is not None
        assert page2.pdf_page_number == 2
        assert page2.pdf_page_index == 1
        assert page2.layout_type == LayoutType.IMPOSITION_4UP
        assert page2.crop_readiness == CropReadinessStatus.CROP_READY
        assert page2.review_decision == ReviewDecisionState.PENDING
        assert page2.is_cover is False

    def test_get_page_record_not_found_raises(self, standard_6page_doc_plan: DocumentCropPlan) -> None:
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(standard_6page_doc_plan)

        with pytest.raises(PageNotFoundError, match="Page 99 not found"):
            workflow.get_page_record(session.session_id, page_number=99)

    def test_single_page_non_nominal_record_flags(self) -> None:
        calc = SinglePageCropStrategy()
        plan_non = calc.calculate(pdf_page_index=0, page_width_pt=430.0, page_height_pt=620.0)

        profile = create_single_page_profile()
        doc_plan = DocumentCropPlan(
            source_filename="single_non_nominal.pdf",
            total_pdf_pages=1,
            expected_total_book_pages=1,
            page_sequence_signature=["SINGLE_PAGE"],
            profile=profile,
            page_plans=[plan_non],
            document_status=DocumentStatus(
                document_status="MANUAL_REVIEW_REQUIRED",
                has_manual_review_required=True,
                all_pages_crop_ready=False,
                summary_message="Non-nominal single page",
            ),
        )

        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(doc_plan)
        p1 = session.get_page_record(1)

        assert p1.is_non_nominal is True
        assert UNRESOLVED_SINGLE_PAGE_NORMALIZATION_POLICY in p1.unresolved_discrepancies


# --- 3. Review Decisions and Transition Rules Tests ---

class TestReviewDecisionsAndTransitions:
    """Tests for recording decisions and enforcing transition rules."""

    def test_record_decision_approved(self, standard_6page_doc_plan: DocumentCropPlan) -> None:
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(standard_6page_doc_plan)

        # Approve sheet 2 (4-Up)
        rec = workflow.record_decision(
            session_id=session.session_id,
            page_number=2,
            decision=ReviewDecision.APPROVED,
            reviewer_id="reviewer_alice",
            notes="Visual inspection passed. Midpoint cuts aligned.",
        )

        assert rec.review_decision == ReviewDecisionState.APPROVED
        assert rec.reviewer_id == "reviewer_alice"
        assert rec.notes == "Visual inspection passed. Midpoint cuts aligned."
        assert rec.reviewed_at is not None
        assert rec.reviewed_at.tzinfo == timezone.utc

    def test_record_decision_needs_revision(self, standard_6page_doc_plan: DocumentCropPlan) -> None:
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(standard_6page_doc_plan)

        rec = workflow.record_decision(
            session_id=session.session_id,
            page_number=3,
            decision=ReviewDecision.NEEDS_REVISION,
            reviewer_id="reviewer_bob",
            reason="Tick mark deviation suspected",
        )

        assert rec.review_decision == ReviewDecisionState.NEEDS_REVISION
        assert rec.reviewer_id == "reviewer_bob"

    def test_record_decision_rejected(self, standard_6page_doc_plan: DocumentCropPlan) -> None:
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(standard_6page_doc_plan)

        rec = workflow.record_decision(
            session_id=session.session_id,
            page_number=4,
            decision=ReviewDecision.REJECTED,
            reviewer_id="reviewer_carol",
            reason="Unacceptable image distortion on sheet",
        )

        assert rec.review_decision == ReviewDecisionState.REJECTED
        assert rec.reviewer_id == "reviewer_carol"

    def test_empty_reviewer_id_raises_value_error(self, standard_6page_doc_plan: DocumentCropPlan) -> None:
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(standard_6page_doc_plan)

        with pytest.raises(ValueError, match="non-empty string"):
            workflow.record_decision(
                session_id=session.session_id,
                page_number=2,
                decision=ReviewDecision.APPROVED,
                reviewer_id="",
            )

        with pytest.raises(ValueError, match="non-empty string"):
            workflow.record_decision(
                session_id=session.session_id,
                page_number=2,
                decision=ReviewDecision.APPROVED,
                reviewer_id="   ",
            )

    def test_rejected_page_cannot_proceed_directly_to_approved(
        self,
        standard_6page_doc_plan: DocumentCropPlan,
    ) -> None:
        """REJECTED pages cannot proceed directly to APPROVED."""
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(standard_6page_doc_plan)

        # Reject page 2
        workflow.record_decision(
            session_id=session.session_id,
            page_number=2,
            decision=ReviewDecision.REJECTED,
            reviewer_id="reviewer_alice",
            reason="Defect identified",
        )

        # Attempt to approve rejected page directly
        with pytest.raises(InvalidStateTransitionError, match=r"REJECTED.*cannot proceed"):
            workflow.record_decision(
                session_id=session.session_id,
                page_number=2,
                decision=ReviewDecision.APPROVED,
                reviewer_id="reviewer_alice",
            )

    def test_rejected_page_can_move_to_needs_revision_first(
        self,
        standard_6page_doc_plan: DocumentCropPlan,
    ) -> None:
        """A rejected page can be set to NEEDS_REVISION, and subsequently approved after revision."""
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(standard_6page_doc_plan)

        # Reject
        workflow.record_decision(
            session_id=session.session_id,
            page_number=2,
            decision=ReviewDecision.REJECTED,
            reviewer_id="reviewer_alice",
        )

        # Move to NEEDS_REVISION
        rec_rev = workflow.record_decision(
            session_id=session.session_id,
            page_number=2,
            decision=ReviewDecision.NEEDS_REVISION,
            reviewer_id="reviewer_bob",
            notes="Revised tick anchors applied",
        )
        assert rec_rev.review_decision == ReviewDecisionState.NEEDS_REVISION

        # Now it can be approved
        rec_app = workflow.record_decision(
            session_id=session.session_id,
            page_number=2,
            decision=ReviewDecision.APPROVED,
            reviewer_id="reviewer_bob",
            notes="Verified revision",
        )
        assert rec_app.review_decision == ReviewDecisionState.APPROVED

    def test_evaluated_page_cannot_revert_to_pending(
        self,
        standard_6page_doc_plan: DocumentCropPlan,
    ) -> None:
        """Completed evaluations cannot silently revert to PENDING."""
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(standard_6page_doc_plan)

        # Approve page 2
        workflow.record_decision(
            session_id=session.session_id,
            page_number=2,
            decision=ReviewDecision.APPROVED,
            reviewer_id="reviewer_alice",
        )

        # Attempt to revert to PENDING
        with pytest.raises(InvalidStateTransitionError, match="Cannot revert"):
            workflow.record_decision(
                session_id=session.session_id,
                page_number=2,
                decision=ReviewDecisionState.PENDING,
                reviewer_id="reviewer_alice",
            )


# --- 4. Cover Spread Approval Rules ---

class TestCoverApprovalRules:
    """Tests for Cover Spread explicit review and discrepancy preservation."""

    def test_cover_requires_explicit_review(self, standard_6page_doc_plan: DocumentCropPlan) -> None:
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(standard_6page_doc_plan)

        cover_record = session.get_page_record(1)
        assert cover_record.is_cover is True
        assert cover_record.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED
        assert cover_record.review_decision == ReviewDecisionState.PENDING

        # Explicit operator review
        rec = workflow.record_decision(
            session_id=session.session_id,
            page_number=1,
            decision=ReviewDecision.APPROVED,
            reviewer_id="senior_operator_dave",
            notes="Spine width 15.02 mm verified against physical proof.",
        )

        assert rec.review_decision == ReviewDecisionState.APPROVED
        assert rec.reviewer_id == "senior_operator_dave"

        # Discrepancies MUST be preserved even when approved
        assert UNRESOLVED_COVER_WIDTH_DISCREPANCY in rec.unresolved_discrepancies
        assert UNRESOLVED_ROUNDING_1PX in rec.unresolved_discrepancies

        # Crop readiness from classifier/guardrails is NOT mutated
        assert rec.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED


# --- 5. UNKNOWN_LAYOUT Restrictions ---

class TestUnknownLayoutRestrictions:
    """Tests for UNKNOWN_LAYOUT handling in review."""

    def test_unknown_layout_page_cannot_be_approved(
        self,
        doc_plan_with_unknown_layout: DocumentCropPlan,
    ) -> None:
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(doc_plan_with_unknown_layout)

        p1 = session.get_page_record(1)
        assert p1.classification_status == ClassificationStatus.UNKNOWN_LAYOUT

        # Attempting to approve an UNKNOWN_LAYOUT page must be rejected
        with pytest.raises(InvalidStateTransitionError, match="UNKNOWN_LAYOUT and cannot be approved"):
            workflow.record_decision(
                session_id=session.session_id,
                page_number=1,
                decision=ReviewDecision.APPROVED,
                reviewer_id="op_alice",
            )

    def test_unknown_layout_document_is_review_blocked(
        self,
        doc_plan_with_unknown_layout: DocumentCropPlan,
    ) -> None:
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(doc_plan_with_unknown_layout)

        assert session.document_summary.status == DocumentReviewStatus.REVIEW_BLOCKED
        assert "UNKNOWN_LAYOUT" in session.document_summary.summary_message

    def test_unknown_layout_page_can_be_rejected(
        self,
        doc_plan_with_unknown_layout: DocumentCropPlan,
    ) -> None:
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(doc_plan_with_unknown_layout)

        rec = workflow.record_decision(
            session_id=session.session_id,
            page_number=1,
            decision=ReviewDecision.REJECTED,
            reviewer_id="op_alice",
            reason="Unknown layout cannot be processed",
        )
        assert rec.review_decision == ReviewDecisionState.REJECTED


# --- 6. Review History and Audit Trail Tests ---

class TestReviewHistory:
    """Tests for chronological history tracking and notes updates."""

    def test_audit_history_records_every_decision_change(
        self,
        standard_6page_doc_plan: DocumentCropPlan,
    ) -> None:
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(standard_6page_doc_plan)

        workflow.record_decision(session.session_id, 2, ReviewDecision.NEEDS_REVISION, "op1", notes="Check alignment")
        workflow.record_decision(session.session_id, 2, ReviewDecision.APPROVED, "op2", notes="Re-aligned and approved")

        history = workflow.get_history(session.session_id, page_number=2)
        assert len(history) == 2

        # Event 1: PENDING -> NEEDS_REVISION
        assert history[0].previous_decision == ReviewDecisionState.PENDING
        assert history[0].new_decision == ReviewDecisionState.NEEDS_REVISION
        assert history[0].reviewer_id == "op1"

        # Event 2: NEEDS_REVISION -> APPROVED
        assert history[1].previous_decision == ReviewDecisionState.NEEDS_REVISION
        assert history[1].new_decision == ReviewDecisionState.APPROVED
        assert history[1].reviewer_id == "op2"

    def test_update_notes_records_history_without_changing_decision(
        self,
        standard_6page_doc_plan: DocumentCropPlan,
    ) -> None:
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(standard_6page_doc_plan)

        workflow.record_decision(session.session_id, 2, ReviewDecision.APPROVED, "op1", notes="Initial note")
        workflow.update_notes(session.session_id, 2, "op2", "Appended audit remarks")

        p2 = workflow.get_page_record(session.session_id, 2)
        assert p2.notes == "Appended audit remarks"
        assert p2.review_decision == ReviewDecisionState.APPROVED

        history = workflow.get_history(session.session_id, page_number=2)
        assert len(history) == 2
        assert history[1].event_type == ReviewEventType.NOTES_UPDATED
        assert history[1].notes == "Appended audit remarks"
        assert history[1].reviewer_id == "op2"


# --- 7. Document Review Status Aggregation Tests ---

class TestDocumentStatusAggregation:
    """Tests for document-level status derivation."""

    def test_pending_review_when_all_pages_pending(
        self,
        standard_6page_doc_plan: DocumentCropPlan,
    ) -> None:
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(standard_6page_doc_plan)

        summary = workflow.get_document_summary(session.session_id)
        assert summary.status == DocumentReviewStatus.PENDING_REVIEW
        assert summary.pending_pages_count == 6
        assert summary.approved_pages_count == 0
        assert summary.is_review_completed is False

    def test_partially_reviewed_when_some_pages_approved(
        self,
        standard_6page_doc_plan: DocumentCropPlan,
    ) -> None:
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(standard_6page_doc_plan)

        workflow.record_decision(session.session_id, 1, ReviewDecision.APPROVED, "op1")
        workflow.record_decision(session.session_id, 2, ReviewDecision.APPROVED, "op1")

        summary = workflow.get_document_summary(session.session_id)
        assert summary.status == DocumentReviewStatus.PARTIALLY_REVIEWED
        assert summary.approved_pages_count == 2
        assert summary.pending_pages_count == 4
        assert summary.is_review_completed is False

    def test_partially_reviewed_when_page_needs_revision(
        self,
        standard_6page_doc_plan: DocumentCropPlan,
    ) -> None:
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(standard_6page_doc_plan)

        for p in range(1, 6):
            workflow.record_decision(session.session_id, p, ReviewDecision.APPROVED, "op1")
        workflow.record_decision(session.session_id, 6, ReviewDecision.NEEDS_REVISION, "op1")

        summary = workflow.get_document_summary(session.session_id)
        assert summary.status == DocumentReviewStatus.PARTIALLY_REVIEWED
        assert summary.is_review_completed is False

    def test_review_rejected_when_any_page_rejected(
        self,
        standard_6page_doc_plan: DocumentCropPlan,
    ) -> None:
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(standard_6page_doc_plan)

        for p in range(1, 6):
            workflow.record_decision(session.session_id, p, ReviewDecision.APPROVED, "op1")
        workflow.record_decision(session.session_id, 6, ReviewDecision.REJECTED, "op1", reason="Torn page")

        summary = workflow.get_document_summary(session.session_id)
        assert summary.status == DocumentReviewStatus.REVIEW_REJECTED
        assert summary.rejected_pages_count == 1
        assert summary.is_review_completed is False

    def test_review_completed_only_when_all_pages_approved(
        self,
        standard_6page_doc_plan: DocumentCropPlan,
    ) -> None:
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(standard_6page_doc_plan)

        # Approve all 6 pages
        for p in range(1, 7):
            workflow.record_decision(
                session_id=session.session_id,
                page_number=p,
                decision=ReviewDecision.APPROVED,
                reviewer_id="lead_reviewer",
                notes=f"Page {p} passed inspection",
            )

        summary = workflow.get_document_summary(session.session_id)
        assert summary.status == DocumentReviewStatus.REVIEW_COMPLETED
        assert summary.is_review_completed is True
        assert summary.approved_pages_count == 6
        assert summary.pending_pages_count == 0
        assert summary.rejected_pages_count == 0
        assert summary.needs_revision_pages_count == 0
        assert summary.reviewed_at is not None
        assert summary.reviewed_at.tzinfo == timezone.utc


# --- 8. Safety, Immutability & Production Isolation Tests ---

class TestSafetyAndImmutability:
    """Tests ensuring crop coordinates, PDF points, and production boundaries remain unbreached."""

    def test_crop_coordinates_remain_immutable_during_review(
        self,
        standard_6page_doc_plan: DocumentCropPlan,
    ) -> None:
        """Review decisions must NEVER modify underlying crop coordinates or dimensions."""
        p2_before = standard_6page_doc_plan.page_plans[1]
        coords_before = [
            (r.x_min_pt, r.y_min_pt, r.x_max_pt, r.y_max_pt, r.target_width_px, r.target_height_px)
            for r in p2_before.crop_regions
        ]

        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(standard_6page_doc_plan)

        # Execute multiple review actions
        workflow.record_decision(session.session_id, 2, ReviewDecision.APPROVED, "op1")
        workflow.update_notes(session.session_id, 2, "op1", "Updated note")

        p2_after = standard_6page_doc_plan.page_plans[1]
        coords_after = [
            (r.x_min_pt, r.y_min_pt, r.x_max_pt, r.y_max_pt, r.target_width_px, r.target_height_px)
            for r in p2_after.crop_regions
        ]

        assert coords_before == coords_after

    def test_production_rendering_not_authorized_by_review_completed(
        self,
        standard_6page_doc_plan: DocumentCropPlan,
    ) -> None:
        """REVIEW_COMPLETED does not authorize production rendering by itself."""
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(standard_6page_doc_plan)

        for p in range(1, 7):
            workflow.record_decision(session.session_id, p, ReviewDecision.APPROVED, "op1")

        summary = workflow.get_document_summary(session.session_id)
        assert summary.is_review_completed is True
        assert summary.requires_production_authorization is True

    def test_all_timestamps_are_strictly_utc(
        self,
        standard_6page_doc_plan: DocumentCropPlan,
    ) -> None:
        """All timestamps in session, records, history, and summaries must use UTC."""
        workflow = PreviewReviewWorkflow()
        session = workflow.create_session(standard_6page_doc_plan)

        assert session.created_at.tzinfo == timezone.utc
        assert session.updated_at.tzinfo == timezone.utc

        workflow.record_decision(session.session_id, 1, ReviewDecision.APPROVED, "op1")
        p1 = session.get_page_record(1)
        assert p1.reviewed_at.tzinfo == timezone.utc

        for entry in session.history.entries:
            assert entry.timestamp.tzinfo == timezone.utc
