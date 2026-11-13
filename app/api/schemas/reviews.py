"""Review workflow API schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.crop.review.enums import ReviewDecisionState
from app.crop.review.models import (
    DocumentReviewSummary,
    PageReviewRecord,
    ReviewHistoryEntry,
    ReviewSession,
)


class CreateReviewSessionRequest(BaseModel):
    """Payload to initiate a review session."""

    document_id: str = Field(..., description="Document identifier for which to create the review session")
    session_id: Optional[str] = Field(None, description="Optional custom session UUID")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional custom session metadata")


class RecordDecisionRequest(BaseModel):
    """Payload to record an operator decision on a specific page."""

    decision: ReviewDecisionState = Field(..., description="Target decision state: APPROVED, REJECTED, NEEDS_REVISION, PENDING")
    reviewer_id: str = Field(..., min_length=1, description="Unique operator/reviewer identifier")
    notes: Optional[str] = Field(None, description="Optional review notes")
    reason: Optional[str] = Field(None, description="Optional rationale or justification for decision")


class UpdateNotesRequest(BaseModel):
    """Payload to update review notes on a specific page."""

    reviewer_id: str = Field(..., min_length=1, description="Operator identifier updating notes")
    notes: str = Field(..., min_length=1, description="New or appended note content")


__all__ = [
    "CreateReviewSessionRequest",
    "RecordDecisionRequest",
    "UpdateNotesRequest",
    "ReviewSession",
    "PageReviewRecord",
    "DocumentReviewSummary",
    "ReviewHistoryEntry",
]

