"""DocumentCropPlan model — aggregate crop plan for an entire PDF document.

Combines per-page crop plans with document-level validation and status
aggregation. Follows the document-level integrity logic from Spec §12
(flowchart AggregateDoc → HasUnknown → HasManualReview).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.crop.models.enums import CropReadinessStatus, ClassificationStatus
from app.crop.models.page_crop_plan import PageCropPlan
from app.crop.models.crop_validation import CropValidationResult
from app.crop.models.project_profile import ProjectTrimProfile


class DocumentStatus(BaseModel):
    """Aggregated document-level processing status.

    Follows the document-level integrity validation logic from Spec §12.
    """

    has_unknown_layout: bool = Field(
        default=False,
        description="Whether any page has UNKNOWN_LAYOUT classification",
    )
    has_manual_review_required: bool = Field(
        default=False,
        description="Whether any page has MANUAL_REVIEW_REQUIRED readiness",
    )
    all_pages_crop_ready: bool = Field(
        default=False,
        description="Whether all classified pages have CROP_READY readiness",
    )
    document_status: str = Field(
        ...,
        description=(
            "Aggregated status: "
            "'REJECTED_UNKNOWN_LAYOUT' | "
            "'MANUAL_REVIEW_REQUIRED' | "
            "'AUTO_READY_FOR_PREVIEW'"
        ),
    )

    @model_validator(mode="after")
    def _validate_document_status(self) -> "DocumentStatus":
        """Validate document status follows Spec §12 aggregation logic."""
        valid_statuses = {
            "REJECTED_UNKNOWN_LAYOUT",
            "MANUAL_REVIEW_REQUIRED",
            "AUTO_READY_FOR_PREVIEW",
        }
        if self.document_status not in valid_statuses:
            raise ValueError(
                f"document_status must be one of {valid_statuses}. "
                f"Got: {self.document_status}"
            )

        if self.has_unknown_layout:
            if self.document_status != "REJECTED_UNKNOWN_LAYOUT":
                raise ValueError(
                    "Document with UNKNOWN_LAYOUT pages must be REJECTED_UNKNOWN_LAYOUT"
                )
        elif self.has_manual_review_required:
            if self.document_status != "MANUAL_REVIEW_REQUIRED":
                raise ValueError(
                    "Document with MANUAL_REVIEW_REQUIRED pages (and no UNKNOWN) "
                    "must be MANUAL_REVIEW_REQUIRED"
                )
        else:
            if self.document_status != "AUTO_READY_FOR_PREVIEW":
                raise ValueError(
                    "Document with all pages CROP_READY must be AUTO_READY_FOR_PREVIEW"
                )
        return self


class DocumentCropPlan(BaseModel):
    """Complete crop plan for an entire PDF document.

    Aggregates per-page crop plans and derives document-level status
    following the aggregation logic in Spec §12.
    """

    # --- Document identity ---
    source_filename: str = Field(
        ...,
        min_length=1,
        description="Original PDF filename",
    )
    total_pdf_pages: int = Field(
        ..., gt=0,
        description="Total number of pages in the PDF document (Spec §3.B)",
    )

    # --- Profile reference ---
    profile: ProjectTrimProfile = Field(
        ...,
        description="Project trim profile used for this document",
    )

    # --- Per-page plans ---
    page_plans: list[PageCropPlan] = Field(
        ...,
        min_length=1,
        description="Ordered list of crop plans for each PDF page",
    )

    # --- Document-level status ---
    document_status: DocumentStatus = Field(
        ...,
        description="Aggregated document-level processing status (Spec §12)",
    )

    # --- Yield summary ---
    expected_total_book_pages: int = Field(
        ..., ge=0,
        description="Total expected book pages from all sheets (Spec §3.B)",
    )
    page_sequence_signature: list[str] = Field(
        ...,
        description=(
            "Pattern of layout types per page, e.g. "
            "['COVER_SPREAD', 'IMPOSITION_4UP', ...] (Spec §3.B)"
        ),
    )

    # --- Validation results ---
    validation_results: list[CropValidationResult] = Field(
        default_factory=list,
        description="Validation results for each crop region",
    )

    @model_validator(mode="after")
    def _validate_page_count(self) -> "DocumentCropPlan":
        """Ensure page_plans count matches total_pdf_pages."""
        if len(self.page_plans) != self.total_pdf_pages:
            raise ValueError(
                f"page_plans count ({len(self.page_plans)}) does not match "
                f"total_pdf_pages ({self.total_pdf_pages})"
            )
        return self

    @model_validator(mode="after")
    def _validate_page_indices(self) -> "DocumentCropPlan":
        """Ensure page plans are in order and indices are sequential."""
        for i, plan in enumerate(self.page_plans):
            if plan.pdf_page_index != i:
                raise ValueError(
                    f"page_plans[{i}].pdf_page_index={plan.pdf_page_index}, "
                    f"expected {i}"
                )
        return self

    @model_validator(mode="after")
    def _validate_total_yield(self) -> "DocumentCropPlan":
        """Ensure expected_total_book_pages matches sum of per-page yields."""
        total = sum(p.expected_page_yield for p in self.page_plans)
        if self.expected_total_book_pages != total:
            raise ValueError(
                f"expected_total_book_pages ({self.expected_total_book_pages}) "
                f"does not match sum of expected_page_yield ({total})"
            )
        return self

    @model_validator(mode="after")
    def _validate_sequence_signature(self) -> "DocumentCropPlan":
        """Ensure page_sequence_signature matches page_plans layout types."""
        signature = []
        for plan in self.page_plans:
            if plan.layout_type is not None:
                signature.append(plan.layout_type.value)
            else:
                signature.append(plan.classification_status.value)
        if self.page_sequence_signature != signature:
            raise ValueError(
                f"page_sequence_signature does not match page_plans. "
                f"Expected: {signature}, Got: {self.page_sequence_signature}"
            )
        return self

    @model_validator(mode="after")
    def _validate_document_status_aggregation(self) -> "DocumentCropPlan":
        """Validate document_status is correctly aggregated from page_plans."""
        has_unknown = any(
            p.classification_status == ClassificationStatus.UNKNOWN_LAYOUT
            for p in self.page_plans
        )
        has_manual = any(
            p.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED
            for p in self.page_plans
        )

        if self.document_status.has_unknown_layout != has_unknown:
            raise ValueError(
                f"document_status.has_unknown_layout={self.document_status.has_unknown_layout} "
                f"does not match actual has_unknown={has_unknown}"
            )
        if self.document_status.has_manual_review_required != has_manual:
            raise ValueError(
                f"document_status.has_manual_review_required="
                f"{self.document_status.has_manual_review_required} "
                f"does not match actual has_manual={has_manual}"
            )
        return self

