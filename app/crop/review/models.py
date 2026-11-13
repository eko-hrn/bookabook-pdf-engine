"""Pydantic Models for Preview Review Workflow (Phase 1.2.2.6).

Defines structured data structures for review sessions, per-page review records,
decision audit logs, and document-level review summaries.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, ClassVar, Optional
import uuid

from pydantic import BaseModel, Field

from app.crop.models.enums import (
    ClassificationStatus,
    CropReadinessStatus,
    LayoutType,
)
from app.crop.review.enums import (
    DocumentReviewStatus,
    ReviewDecisionState,
    ReviewEventType,
)


class ReviewDecision(BaseModel):
    """Structured Pydantic model representing a manual review decision.

    Exposes class-level shortcuts (APPROVED, REJECTED, NEEDS_REVISION, PENDING)
    for idiomatic decision assignment while remaining a fully validated BaseModel.
    """

    PENDING: ClassVar[ReviewDecisionState] = ReviewDecisionState.PENDING
    APPROVED: ClassVar[ReviewDecisionState] = ReviewDecisionState.APPROVED
    REJECTED: ClassVar[ReviewDecisionState] = ReviewDecisionState.REJECTED
    NEEDS_REVISION: ClassVar[ReviewDecisionState] = ReviewDecisionState.NEEDS_REVISION

    decision: ReviewDecisionState = Field(
        ...,
        description="Review decision value: APPROVED, REJECTED, NEEDS_REVISION, PENDING",
    )
    reviewer_id: str = Field(
        ...,
        min_length=1,
        description="Identifier of the operator/reviewer recording the decision",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the decision",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Optional operator review notes or remarks",
    )
    reason: Optional[str] = Field(
        default=None,
        description="Optional justification for rejection or revision request",
    )


class ReviewHistoryEntry(BaseModel):
    """Immutable audit trail entry capturing a discrete review event."""

    entry_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this history entry",
    )
    pdf_page_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="Zero-based PDF page index (None if document-level event)",
    )
    pdf_page_number: Optional[int] = Field(
        default=None,
        ge=1,
        description="One-based PDF page number (None if document-level event)",
    )
    event_type: ReviewEventType = Field(
        ...,
        description="Type of review action: SESSION_CREATED, DECISION_RECORDED, NOTES_UPDATED",
    )
    previous_decision: Optional[ReviewDecisionState] = Field(
        default=None,
        description="Decision state prior to this action",
    )
    new_decision: Optional[ReviewDecisionState] = Field(
        default=None,
        description="New decision state resulting from this action",
    )
    reviewer_id: str = Field(
        ...,
        min_length=1,
        description="Identifier of the operator/system initiating the action",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the event",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Notes recorded with this event",
    )
    reason: Optional[str] = Field(
        default=None,
        description="Justification or explanation for the event",
    )


class ReviewHistory(BaseModel):
    """Chronological audit trail of all review decisions and updates."""

    entries: list[ReviewHistoryEntry] = Field(
        default_factory=list,
        description="Chronological list of immutable history entries",
    )

    @property
    def total_events(self) -> int:
        """Total number of recorded events in this history."""
        return len(self.entries)

    def get_entries_for_page(self, page_number: int) -> list[ReviewHistoryEntry]:
        """Filter history entries for a specific 1-based page number."""
        return [e for e in self.entries if e.pdf_page_number == page_number]

    def add_entry(self, entry: ReviewHistoryEntry) -> None:
        """Append an audit entry to the chronological log."""
        self.entries.append(entry)


class PageReviewRecord(BaseModel):
    """Review record and current status for a single PDF page."""

    pdf_page_index: int = Field(
        ...,
        ge=0,
        description="Zero-based page index in the PDF document",
    )
    pdf_page_number: int = Field(
        ...,
        ge=1,
        description="One-based page number (pdf_page_index + 1)",
    )
    layout_type: Optional[LayoutType] = Field(
        default=None,
        description="Classified layout type (None if UNKNOWN_LAYOUT)",
    )
    classification_status: ClassificationStatus = Field(
        default=ClassificationStatus.CLASSIFIED,
        description="Outcome from layout classifier (Spec §2)",
    )
    crop_readiness: CropReadinessStatus = Field(
        ...,
        description="Crop readiness status from safety guardrails (Spec §2, §11)",
    )
    review_decision: ReviewDecisionState = Field(
        default=ReviewDecisionState.PENDING,
        description="Current manual review decision: APPROVED, REJECTED, NEEDS_REVISION, PENDING",
    )
    reviewer_id: Optional[str] = Field(
        default=None,
        description="Reviewer identifier who recorded the latest decision",
    )
    reviewed_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp when the latest decision was recorded",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Current operator review notes",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Related warnings from crop plan, validator, or preview engine",
    )
    unresolved_discrepancies: list[str] = Field(
        default_factory=list,
        description="Preserved unresolved discrepancies (e.g. UNRESOLVED_COVER_WIDTH_DISCREPANCY)",
    )
    is_cover: bool = Field(
        default=False,
        description="Whether this sheet represents a Cover Spread",
    )
    is_non_nominal: bool = Field(
        default=False,
        description="Whether this sheet exhibits non-nominal dimensions",
    )
    history: list[ReviewHistoryEntry] = Field(
        default_factory=list,
        description="Page-level audit log of decisions and note updates",
    )


class DocumentReviewSummary(BaseModel):
    """Document-level aggregated review status and metrics."""

    session_id: str = Field(
        ...,
        description="Associated review session ID",
    )
    source_filename: str = Field(
        ...,
        description="Source PDF filename",
    )
    total_pages: int = Field(
        ...,
        gt=0,
        description="Total PDF pages in the document",
    )
    approved_pages_count: int = Field(
        default=0,
        ge=0,
        description="Total pages with decision APPROVED",
    )
    rejected_pages_count: int = Field(
        default=0,
        ge=0,
        description="Total pages with decision REJECTED",
    )
    needs_revision_pages_count: int = Field(
        default=0,
        ge=0,
        description="Total pages with decision NEEDS_REVISION",
    )
    pending_pages_count: int = Field(
        default=0,
        ge=0,
        description="Total pages with decision PENDING",
    )
    status: DocumentReviewStatus = Field(
        ...,
        description="Document review status: PENDING_REVIEW, PARTIALLY_REVIEWED, REVIEW_COMPLETED, REVIEW_REJECTED, REVIEW_BLOCKED",
    )
    is_review_completed: bool = Field(
        default=False,
        description="True ONLY if status is REVIEW_COMPLETED",
    )
    requires_production_authorization: bool = Field(
        default=True,
        description="Strict safety guardrail: REVIEW_COMPLETED does not authorize production rendering by itself",
    )
    summary_message: str = Field(
        default="",
        description="Human-readable review summary message",
    )
    unresolved_discrepancies: list[str] = Field(
        default_factory=list,
        description="Document-wide unresolved discrepancies across all pages",
    )
    reviewed_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp when review reached completion or rejection",
    )


class ReviewSession(BaseModel):
    """Complete review session for an entire PDF document."""

    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the review session",
    )
    source_filename: str = Field(
        ...,
        description="Original source PDF filename",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when review session was created",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the most recent session update",
    )
    page_records: list[PageReviewRecord] = Field(
        default_factory=list,
        description="Ordered list of page review records (one per PDF page)",
    )
    document_summary: DocumentReviewSummary = Field(
        ...,
        description="Current aggregated document-level review summary",
    )
    history: ReviewHistory = Field(
        default_factory=ReviewHistory,
        description="Chronological audit history for the session",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional session context or metadata",
    )

    def get_page_record(self, page_number: int) -> Optional[PageReviewRecord]:
        """Retrieve a PageReviewRecord by 1-based page number."""
        for p in self.page_records:
            if p.pdf_page_number == page_number:
                return p
        return None

    @property
    def all_pages_approved(self) -> bool:
        """True if every page in this session has been explicitly APPROVED."""
        return (
            len(self.page_records) > 0
            and all(p.review_decision == ReviewDecisionState.APPROVED for p in self.page_records)
        )

    @property
    def has_rejected_pages(self) -> bool:
        """True if any page in this session has been marked REJECTED."""
        return any(p.review_decision == ReviewDecisionState.REJECTED for p in self.page_records)

