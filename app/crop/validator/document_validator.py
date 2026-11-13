"""Document-level validation rules (Phase 1.2.2.3).

Validates:
1. Page sequence integrity (sequential 0..N-1 indices, matching page numbers).
2. Expected total book page yield vs sum of page-level yields.
3. Page sequence signature consistency.
4. DocumentStatus aggregation logic (Spec §12: AggregateDoc -> HasUnknown -> HasManualReview).
5. Preservation of distinction between page-level readiness and document-level status.
"""

from __future__ import annotations

from typing import Optional

from app.crop.models.document_crop_plan import DocumentCropPlan
from app.crop.models.enums import ClassificationStatus, CropReadinessStatus
from app.crop.models.project_profile import ProjectTrimProfile


def validate_document_plan_integrity(
    doc_plan: DocumentCropPlan,
    profile: Optional[ProjectTrimProfile] = None,
) -> tuple[list[str], list[str]]:
    """Validate a DocumentCropPlan against document-level integrity rules.

    Returns:
        (errors, warnings)
    """
    effective_profile = profile or getattr(doc_plan, "profile", None)
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Page count check
    actual_page_count = len(doc_plan.page_plans)
    if doc_plan.total_pdf_pages != actual_page_count:
        errors.append(
            f"Document total_pdf_pages ({doc_plan.total_pdf_pages}) does not match "
            f"actual page_plans count ({actual_page_count})"
        )

    # 2. Page sequence integrity
    for i, plan in enumerate(doc_plan.page_plans):
        if plan.pdf_page_index != i:
            errors.append(
                f"Page at position {i} has pdf_page_index={plan.pdf_page_index}, expected {i}"
            )
        if plan.pdf_page_number != i + 1:
            errors.append(
                f"Page at position {i} has pdf_page_number={plan.pdf_page_number}, expected {i + 1}"
            )

    # 3. Total yield sum check
    computed_yield = sum(p.expected_page_yield for p in doc_plan.page_plans)
    if doc_plan.expected_total_book_pages != computed_yield:
        errors.append(
            f"Document expected_total_book_pages ({doc_plan.expected_total_book_pages}) "
            f"does not match sum of page yields ({computed_yield})"
        )

    # 4. Page sequence signature check
    expected_signature = [
        p.layout_type.value if p.layout_type else "UNKNOWN"
        for p in doc_plan.page_plans
    ]
    if doc_plan.page_sequence_signature != expected_signature:
        errors.append(
            f"Document page_sequence_signature does not match page layouts: "
            f"declared={doc_plan.page_sequence_signature}, expected={expected_signature}"
        )

    # 5. DocumentStatus aggregation verification (Spec §12)
    has_unknown = any(
        p.classification_status == ClassificationStatus.UNKNOWN_LAYOUT
        for p in doc_plan.page_plans
    )
    has_manual_review = any(
        p.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED
        for p in doc_plan.page_plans
    )
    all_crop_ready = not has_unknown and not has_manual_review

    expected_status_str = (
        "REJECTED_UNKNOWN_LAYOUT"
        if has_unknown
        else "MANUAL_REVIEW_REQUIRED"
        if has_manual_review
        else "AUTO_READY_FOR_PREVIEW"
    )

    doc_status = doc_plan.document_status

    if doc_status.document_status != expected_status_str:
        errors.append(
            f"Document status aggregation mismatch: declared='{doc_status.document_status}', "
            f"expected='{expected_status_str}' based on page readiness states."
        )

    if doc_status.has_unknown_layout != has_unknown:
        errors.append(
            f"DocumentStatus.has_unknown_layout={doc_status.has_unknown_layout} "
            f"does not match actual page states ({has_unknown})"
        )
    if doc_status.has_manual_review_required != has_manual_review:
        errors.append(
            f"DocumentStatus.has_manual_review_required={doc_status.has_manual_review_required} "
            f"does not match actual page states ({has_manual_review})"
        )
    if doc_status.all_pages_crop_ready != all_crop_ready:
        errors.append(
            f"DocumentStatus.all_pages_crop_ready={doc_status.all_pages_crop_ready} "
            f"does not match actual page states ({all_crop_ready})"
        )

    # 6. Profile ID check
    if profile is not None and getattr(doc_plan, "profile", None) is not None:
        if doc_plan.profile.profile_id != profile.profile_id:
            warnings.append(
                f"Document profile ID ('{doc_plan.profile.profile_id}') differs from "
                f"validator profile ID ('{profile.profile_id}')"
            )

    return errors, warnings
