"""Enumeration types for the Preview Review Workflow (Phase 1.2.2.6).

Defines decision types, document-level review states, and audit event types.
"""

from enum import Enum


class ReviewDecisionState(str, Enum):
    """Supported manual review decisions for individual pages (Spec §11 & Phase 1.2.2.6)."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_REVISION = "NEEDS_REVISION"


class DocumentReviewStatus(str, Enum):
    """Aggregate review status for an entire document (Phase 1.2.2.6 §4)."""

    PENDING_REVIEW = "PENDING_REVIEW"
    PARTIALLY_REVIEWED = "PARTIALLY_REVIEWED"
    REVIEW_COMPLETED = "REVIEW_COMPLETED"
    REVIEW_REJECTED = "REVIEW_REJECTED"
    REVIEW_BLOCKED = "REVIEW_BLOCKED"


class ReviewEventType(str, Enum):
    """Audit event types captured in ReviewHistory."""

    SESSION_CREATED = "SESSION_CREATED"
    DECISION_RECORDED = "DECISION_RECORDED"
    NOTES_UPDATED = "NOTES_UPDATED"

