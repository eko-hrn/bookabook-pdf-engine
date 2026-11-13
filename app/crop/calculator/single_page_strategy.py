
"""SinglePageCropStrategy — Crop coordinate calculation for Single Page Layout (Layout C).

Implements Section 8.B.3, 11 (C-03 to C-05), 16 Item 8, and 17 of
Layout Classifier Specification v1.3.4.

Key Principles:
1. No interior grid dividing lines (1-Up).
2. Clean single page exports full MediaBox/CropBox [0, 0, W, H], or trims
   to bleed L-marks if provided.
3. Nominal target: 425.52 x 609.12 pt → exactly 1773 x 2538 px @ 300 DPI.
4. STRICT NORMALIZATION SAFETY GUARDRAIL:
   - Pages with non-nominal dimensions (e.g. 415-450 x 590-640 pt window)
     MUST remain MANUAL_REVIEW_REQUIRED with flag NON_NOMINAL_DIMENSIONS_DETECTED
     until an official normalization policy is approved.
   - Non-zero rotation triggers MANUAL_REVIEW_REQUIRED with flag ROTATED_SHEET_DETECTED.
5. Yield: exactly 1 page.
"""

from __future__ import annotations

from typing import Optional

from app.crop.calculator.base import BaseCropStrategy
from app.crop.calculator.conversions import (
    validate_bounding_box,
    validate_no_stretching,
)
from app.crop.calculator.unresolved import (
    UNRESOLVED_SINGLE_PAGE_NORMALIZATION_POLICY,
)
from app.crop.models.crop_region import CropRegion
from app.crop.models.enums import (
    BlankPageStatus,
    ClassificationStatus,
    CropReadinessStatus,
    CropStrategyType,
    LayoutType,
    ManualReviewFlag,
    Orientation,
)
from app.crop.models.page_crop_plan import PageCropPlan
from app.crop.models.project_profile import ProjectTrimProfile
from app.crop.profiles.profile_configs import create_single_page_profile

# Nominal single page dimensions (Bookabook Comic A5, Spec §4, §8.B.3, §17)
NOMINAL_SINGLE_PAGE_WIDTH_PT: float = 425.52
NOMINAL_SINGLE_PAGE_HEIGHT_PT: float = 609.12


class SinglePageCropStrategy(BaseCropStrategy):
    """Crop coordinate calculator for Single Page 1-Up (Layout C).

    Handles direct export / bleed trim for single page sheets.
    """

    def __init__(self, profile: Optional[ProjectTrimProfile] = None) -> None:
        if profile is None:
            profile = create_single_page_profile()
        super().__init__(profile)

    @property
    def strategy_type(self) -> CropStrategyType:
        return CropStrategyType.SINGLE_PAGE

    @property
    def target_layout_type(self) -> LayoutType:
        return LayoutType.SINGLE_PAGE

    def calculate(
        self,
        pdf_page_index: int = 0,
        page_width_pt: float = NOMINAL_SINGLE_PAGE_WIDTH_PT,
        page_height_pt: float = NOMINAL_SINGLE_PAGE_HEIGHT_PT,
        rotation: int = 0,
        crop_bbox_pt: Optional[tuple[float, float, float, float]] = None,
        page_number: Optional[int] = None,
        blank_status: BlankPageStatus = BlankPageStatus.CONTENT_PRESENT,
        **kwargs,
    ) -> PageCropPlan:
        """Calculate PageCropPlan for a Single Page sheet.

        Parameters:
            pdf_page_index: Zero-based page index.
            page_width_pt: Measured page width in points.
            page_height_pt: Measured page height in points.
            rotation: PDF page rotation (0, 90, 180, 270).
            crop_bbox_pt: Optional (x_min, y_min, x_max, y_max) if bleed marks exist.
                          If None, full page [0, 0, page_width_pt, page_height_pt] is used.
            page_number: Book page number for region ID (defaults to pdf_page_index + 1).
            blank_status: Blank page status (default CONTENT_PRESENT).

        Returns:
            PageCropPlan with 1 CropRegion object.
        """
        # Determine crop bounding box
        if crop_bbox_pt is not None:
            x_min, y_min, x_max, y_max = crop_bbox_pt
        else:
            x_min, y_min = 0.0, 0.0
            x_max, y_max = page_width_pt, page_height_pt

        # Validate bounding box geometry
        bbox_errors = validate_bounding_box(
            x_min, y_min, x_max, y_max, page_width_pt, page_height_pt
        )
        if bbox_errors:
            raise ValueError(
                f"Invalid single page bounding box [{x_min}, {y_min}, {x_max}, {y_max}]: "
                f"{', '.join(bbox_errors)}"
            )

        # Region identification
        if page_number is None:
            page_number = pdf_page_index + 1
        region_id = f"PAGE-{page_number:02d}"

        # Target pixel dimensions (Spec §8.B.3: 1773 x 2538 px @ 300 DPI)
        target_w_px = self.profile.target_content_width_px
        target_h_px = self.profile.target_content_height_px

        # Build CropRegion
        region = CropRegion(
            region_id=region_id,
            quadrant=None,
            x_min_pt=round(x_min, 4),
            y_min_pt=round(y_min, 4),
            x_max_pt=round(x_max, 4),
            y_max_pt=round(y_max, 4),
            target_width_px=target_w_px,
            target_height_px=target_h_px,
            blank_page_status=blank_status,
        )

        # Safety Guardrails: Nominal dimension verification (Spec §8.B.3, §11 C-03)
        manual_flags: list[ManualReviewFlag] = []

        is_nominal = (
            round(page_width_pt, 2) == NOMINAL_SINGLE_PAGE_WIDTH_PT
            and round(page_height_pt, 2) == NOMINAL_SINGLE_PAGE_HEIGHT_PT
        )
        if not is_nominal:
            manual_flags.append(ManualReviewFlag.NON_NOMINAL_DIMENSIONS_DETECTED)

        if rotation != 0:
            manual_flags.append(ManualReviewFlag.ROTATED_SHEET_DETECTED)

        if manual_flags:
            crop_readiness = CropReadinessStatus.MANUAL_REVIEW_REQUIRED
        else:
            crop_readiness = CropReadinessStatus.CROP_READY

        orientation = Orientation.LANDSCAPE if page_width_pt > page_height_pt else Orientation.PORTRAIT

        return PageCropPlan(
            pdf_page_index=pdf_page_index,
            pdf_page_number=pdf_page_index + 1,
            width_pt=page_width_pt,
            height_pt=page_height_pt,
            orientation=orientation,
            rotation=rotation,
            layout_type=LayoutType.SINGLE_PAGE,
            classification_status=ClassificationStatus.CLASSIFIED,
            confidence_score=1.0,
            crop_strategy=CropStrategyType.SINGLE_PAGE,
            crop_readiness=crop_readiness,
            manual_review_flags=manual_flags,
            crop_regions=[region],
            expected_page_yield=1,
        )

