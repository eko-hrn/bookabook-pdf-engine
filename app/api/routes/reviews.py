"""Review workflow routes."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_preview_service, get_review_workflow
from app.api.schemas.reviews import (
    CreateReviewSessionRequest,
    RecordDecisionRequest,
    UpdateNotesRequest,
)
from app.api.services.preview_service import PreviewService
from app.crop.review.models import (
    DocumentReviewSummary,
    PageReviewRecord,
    ReviewHistoryEntry,
    ReviewSession,
)
from app.crop.review.workflow import PreviewReviewWorkflow

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.post(
    "/sessions",
    response_model=ReviewSession,
    status_code=201,
    summary="Create Review Session",
)
def create_review_session(
    payload: CreateReviewSessionRequest,
    preview_service: PreviewService = Depends(get_preview_service),
    workflow: PreviewReviewWorkflow = Depends(get_review_workflow),
) -> ReviewSession:
    """Create a persistent review session for an uploaded document."""
    doc_plan, val_report, preview_payload = preview_service.get_or_build_preview_pipeline(
        payload.document_id
    )

    session_meta = dict(payload.metadata or {})
    session_meta["document_id"] = payload.document_id

    session = workflow.create_session(
        doc_plan=doc_plan,
        preview_payload=preview_payload,
        validation_report=val_report,
        session_id=payload.session_id,
        metadata=session_meta,
    )
    return session


@router.get(
    "/sessions/{session_id}",
    response_model=ReviewSession,
    summary="Get Review Session",
)
def get_review_session(
    session_id: str,
    workflow: PreviewReviewWorkflow = Depends(get_review_workflow),
) -> ReviewSession:
    """Retrieve full review session state including all page review records."""
    return workflow.get_session(session_id)


@router.get(
    "/sessions/{session_id}/pages/{page_number}",
    response_model=PageReviewRecord,
    summary="Get Page Review Record",
)
def get_page_record(
    session_id: str,
    page_number: int,
    workflow: PreviewReviewWorkflow = Depends(get_review_workflow),
) -> PageReviewRecord:
    """Retrieve review record and current decision state for a single page."""
    return workflow.get_page_record(session_id=session_id, page_number=page_number)


@router.post(
    "/sessions/{session_id}/pages/{page_number}/decision",
    response_model=PageReviewRecord,
    summary="Record Review Decision",
)
def record_decision(
    session_id: str,
    page_number: int,
    payload: RecordDecisionRequest,
    workflow: PreviewReviewWorkflow = Depends(get_review_workflow),
) -> PageReviewRecord:
    """Record an operator review decision (APPROVED, REJECTED, NEEDS_REVISION)."""
    return workflow.record_decision(
        session_id=session_id,
        page_number=page_number,
        decision=payload.decision,
        reviewer_id=payload.reviewer_id,
        notes=payload.notes,
        reason=payload.reason,
    )


@router.patch(
    "/sessions/{session_id}/pages/{page_number}/notes",
    response_model=PageReviewRecord,
    summary="Update Page Notes",
)
def update_page_notes(
    session_id: str,
    page_number: int,
    payload: UpdateNotesRequest,
    workflow: PreviewReviewWorkflow = Depends(get_review_workflow),
) -> PageReviewRecord:
    """Update or append operator notes on a page review record without changing its decision."""
    return workflow.update_notes(
        session_id=session_id,
        page_number=page_number,
        reviewer_id=payload.reviewer_id,
        notes=payload.notes,
    )


@router.get(
    "/sessions/{session_id}/history",
    response_model=List[ReviewHistoryEntry],
    summary="Get Session Audit History",
)
def get_session_history(
    session_id: str,
    page_number: Optional[int] = Query(None, description="Optional page number filter"),
    workflow: PreviewReviewWorkflow = Depends(get_review_workflow),
) -> List[ReviewHistoryEntry]:
    """Retrieve chronological audit trail of all review events for a session."""
    return workflow.get_history(session_id=session_id, page_number=page_number)


@router.get(
    "/sessions/{session_id}/summary",
    response_model=DocumentReviewSummary,
    summary="Get Review Session Summary",
)
def get_session_summary(
    session_id: str,
    workflow: PreviewReviewWorkflow = Depends(get_review_workflow),
) -> DocumentReviewSummary:
    """Retrieve summary aggregation (counts of approved, rejected, pending, and overall status)."""
    return workflow.get_document_summary(session_id)
