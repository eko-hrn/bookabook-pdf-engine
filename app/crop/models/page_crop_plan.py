"""PageCropPlan model — crop plan for a single PDF page/sheet.

Associates a PDF page with its classification result, crop strategy,
readiness status, and the list of crop regions to extract.

All status transitions follow the Decision Table v1.3.4 (Spec §11).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.crop.models.enums import (
    ClassificationStatus,
    CropReadinessStatus,
    CropStrategyType,
    LayoutType,
    ManualReviewFlag,
    Orientation,
)
from app.crop.models.crop_region import CropRegion


class PageCropPlan(BaseModel):
    """Crop plan for a single PDF page/sheet.

    Combines classification results from TAHAP 1 (Layout Classifier)
    with crop readiness from TAHAP 2 (Safety Guardrails), and lists
    the CropRegion(s) to extract from this page.
    """

    # --- Page identity ---
    pdf_page_index: int = Field(
        ..., ge=0,
        description="Zero-based page index in the PDF document",
    )
    pdf_page_number: int = Field(
        ..., ge=1,
        description="One-based page number (pdf_page_index + 1)",
    )

    # --- Geometric measurements (Spec §3.A) ---
    width_pt: float = Field(
        ..., gt=0,
        description="Page width from page.rect in points",
    )
    height_pt: float = Field(
        ..., gt=0,
        description="Page height from page.rect in points",
    )
    orientation: Orientation = Field(
        ...,
        description="Detected page orientation (Spec §3.A.1)",
    )
    rotation: int = Field(
        default=0,
        description="PDF page rotation value (0, 90, 180, or 270 degrees)",
    )

    # --- Classification results (TAHAP 1) ---
    layout_type: Optional[LayoutType] = Field(
        default=None,
        description="Detected layout type (None if UNKNOWN_LAYOUT)",
    )
    classification_status: ClassificationStatus = Field(
        ...,
        description="Classification outcome from layout classifier (Spec §2)",
    )
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0,
        description="Classification confidence score C ∈ [0.0, 1.0] (Spec §5)",
    )

    # --- Crop readiness (TAHAP 2) ---
    crop_strategy: Optional[CropStrategyType] = Field(
        default=None,
        description="Assigned crop strategy (None if UNKNOWN_LAYOUT)",
    )
    crop_readiness: CropReadinessStatus = Field(
        ...,
        description="Crop execution readiness status (Spec §2, §11)",
    )
    manual_review_flags: list[ManualReviewFlag] = Field(
        default_factory=list,
        description="Flags indicating reasons for MANUAL_REVIEW_REQUIRED",
    )

    # --- Crop regions ---
    crop_regions: list[CropRegion] = Field(
        default_factory=list,
        description="List of crop regions to extract from this page",
    )

    # --- Yield metadata ---
    expected_page_yield: int = Field(
        ..., ge=0,
        description=(
            "Number of book pages this sheet produces "
            "(Cover=2, 4-Up=4, Single=1, Unknown=0)"
        ),
    )

    @model_validator(mode="after")
    def _validate_page_number_consistency(self) -> "PageCropPlan":
        """Ensure pdf_page_number == pdf_page_index + 1."""
        if self.pdf_page_number != self.pdf_page_index + 1:
            raise ValueError(
                f"pdf_page_number ({self.pdf_page_number}) must equal "
                f"pdf_page_index ({self.pdf_page_index}) + 1"
            )
        return self

    @model_validator(mode="after")
    def _validate_rotation_values(self) -> "PageCropPlan":
        """Rotation must be one of {0, 90, 180, 270} (Spec §3.A.1)."""
        if self.rotation not in {0, 90, 180, 270}:
            raise ValueError(
                f"rotation must be 0, 90, 180, or 270. Got: {self.rotation}"
            )
        return self

    @model_validator(mode="after")
    def _validate_unknown_layout_has_no_strategy(self) -> "PageCropPlan":
        """UNKNOWN_LAYOUT must have no crop strategy and NOT_APPLICABLE readiness."""
        if self.classification_status == ClassificationStatus.UNKNOWN_LAYOUT:
            if self.crop_strategy is not None:
                raise ValueError(
                    "UNKNOWN_LAYOUT must have crop_strategy=None"
                )
            if self.crop_readiness != CropReadinessStatus.NOT_APPLICABLE:
                raise ValueError(
                    "UNKNOWN_LAYOUT must have crop_readiness=NOT_APPLICABLE"
                )
            if self.expected_page_yield != 0:
                raise ValueError(
                    "UNKNOWN_LAYOUT must have expected_page_yield=0"
                )
        return self

    @model_validator(mode="after")
    def _validate_cover_always_manual_review(self) -> "PageCropPlan":
        """Cover sheets must always be MANUAL_REVIEW_REQUIRED (Spec §8.B.1)."""
        if self.crop_strategy == CropStrategyType.COVER:
            if self.crop_readiness != CropReadinessStatus.MANUAL_REVIEW_REQUIRED:
                raise ValueError(
                    "Cover sheets must have crop_readiness=MANUAL_REVIEW_REQUIRED. "
                    "Auto-crop is prohibited per Spec §8.B.1."
                )
        return self

    @model_validator(mode="after")
    def _validate_manual_review_has_flags(self) -> "PageCropPlan":
        """MANUAL_REVIEW_REQUIRED must have at least one flag explaining why."""
        if (
            self.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED
            and not self.manual_review_flags
        ):
            raise ValueError(
                "MANUAL_REVIEW_REQUIRED status requires at least one "
                "manual_review_flag explaining the reason for hold."
            )
        return self

    @model_validator(mode="after")
    def _validate_crop_region_count(self) -> "PageCropPlan":
        """Validate crop region count matches expected yield."""
        if self.crop_regions and len(self.crop_regions) != self.expected_page_yield:
            raise ValueError(
                f"crop_regions count ({len(self.crop_regions)}) does not match "
                f"expected_page_yield ({self.expected_page_yield})"
            )
        return self

    @model_validator(mode="after")
    def _validate_classified_has_layout_type(self) -> "PageCropPlan":
        """CLASSIFIED status must have a layout_type assigned."""
        if self.classification_status == ClassificationStatus.CLASSIFIED:
            if self.layout_type is None:
                raise ValueError(
                    "CLASSIFIED status must have a layout_type assigned"
                )
        return self

    @model_validator(mode="after")
    def _validate_rotation_triggers_manual_review(self) -> "PageCropPlan":
        """Non-zero rotation must result in MANUAL_REVIEW_REQUIRED (Spec §11 C-06, C-07)."""
        if self.rotation != 0:
            if self.crop_readiness != CropReadinessStatus.MANUAL_REVIEW_REQUIRED:
                raise ValueError(
                    "Non-zero rotation must have "
                    "crop_readiness=MANUAL_REVIEW_REQUIRED (Spec §11 C-06, C-07)"
                )
            if ManualReviewFlag.ROTATED_SHEET_DETECTED not in self.manual_review_flags:
                raise ValueError(
                    "Non-zero rotation must include "
                    "ROTATED_SHEET_DETECTED in manual_review_flags"
                )
        return self

    @model_validator(mode="after")
    def _validate_single_page_nominal_dimensions(self) -> "PageCropPlan":
        """Single Page with non-nominal dimensions must be MANUAL_REVIEW_REQUIRED.

        Nominal Bookabook Comic A5 single page dimensions are exactly 425.52 x 609.12 pt
        (Spec §4, §8.B.3, §17). The classifier accepts a detection window of
        415–450 pt (width) x 590–640 pt (height) per Spec §4 & §5 Rule 3.
        However, any dimension differing from the exact nominal 425.52 x 609.12 pt
        is non-nominal and must remain subject to MANUAL_REVIEW_REQUIRED until an
        official normalization policy is approved. No ungrounded production tolerance
        (such as ±1 pt) is permitted.
        """
        if (
            self.layout_type == LayoutType.SINGLE_PAGE
            and self.crop_readiness == CropReadinessStatus.CROP_READY
        ):
            nominal_w = 425.52
            nominal_h = 609.12
            # Compare strictly against nominal dimensions within standard 2-decimal point precision
            if round(self.width_pt, 2) != nominal_w or round(self.height_pt, 2) != nominal_h:
                raise ValueError(
                    f"Single Page with non-nominal dimensions ({self.width_pt}x{self.height_pt} pt, "
                    f"nominal: {nominal_w}x{nominal_h} pt) must have "
                    f"crop_readiness=MANUAL_REVIEW_REQUIRED until normalization policy is approved. "
                    f"Production tolerance beyond exact nominal is not supported by v1.3.4."
                )
        return self

