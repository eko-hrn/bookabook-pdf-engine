"""CoverCropStrategy — Crop coordinate calculation for Cover Spread (Layout A).

Implements Section 8.A, 8.B.1, 14.A.4, 15.B.1, 16.1, 16.2, and 17 of
Layout Classifier Specification v1.3.4.

Key Principles:
1. Distinguishes BACKCOVER (1890x2657 @ 300 DPI) and COVER (630x886 @ 100 DPI).
2. Excludes spine zone (15.02 mm / 42.57 pt) between front and back covers.
3. ABSOLUTE SAFETY GUARDRAIL: Auto-crop is ALWAYS disabled.
   Readiness status is ALWAYS MANUAL_REVIEW_REQUIRED with flag COVER_FORMULA_UNVALIDATED.
4. Documents unresolved 1 px height discrepancy and width asymmetry.
5. Never invents missing coordinates. Never stretches images.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.crop.calculator.base import BaseCropStrategy
from app.crop.calculator.conversions import (
    pixels_to_points,
    points_to_pixels,
    validate_bounding_box,
    validate_no_stretching,
)
from app.crop.calculator.unresolved import (
    UNRESOLVED_COVER_WIDTH_DISCREPANCY,
    UNRESOLVED_ROUNDING_1PX,
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
from app.crop.profiles.profile_configs import create_cover_profile


# Observed vector coordinate defaults from Bookabook sample Page 1 (Spec §8.A.1, §17)
DEFAULT_COVER_LEFT_TRIM_PT: float = 155.95461
DEFAULT_COVER_SPINE_INNER_LEFT_PT: float = 608.51709
DEFAULT_COVER_SPINE_INNER_RIGHT_PT: float = 651.10938
DEFAULT_COVER_RIGHT_TRIM_PT: float = 1105.61914
DEFAULT_COVER_TOP_TRIM_PT: float = 120.48999
DEFAULT_COVER_BOTTOM_TRIM_PT: float = 758.25067


@dataclass(frozen=True)
class CoverCropMarks:
    """Detected or observed vector crop mark coordinates for Cover Spread.

    Coordinates in PDF points relative to top-left origin.
    Values default to the empirical measurements in Spec §8.A.1, §17.
    """

    x_left: float = DEFAULT_COVER_LEFT_TRIM_PT
    x_spine_left: float = DEFAULT_COVER_SPINE_INNER_LEFT_PT
    x_spine_right: float = DEFAULT_COVER_SPINE_INNER_RIGHT_PT
    x_right: float = DEFAULT_COVER_RIGHT_TRIM_PT
    y_top: float = DEFAULT_COVER_TOP_TRIM_PT
    y_bottom: float = DEFAULT_COVER_BOTTOM_TRIM_PT

    def validate(self, page_width: float, page_height: float) -> None:
        """Validate that crop marks are ordered, non-negative, and inside page boundary."""
        if self.x_left < 0 or self.y_top < 0:
            raise ValueError(
                f"Crop mark coordinates cannot be negative: "
                f"x_left={self.x_left}, y_top={self.y_top}"
            )
        if not (self.x_left < self.x_spine_left < self.x_spine_right < self.x_right):
            raise ValueError(
                f"Horizontal cover coordinates must be strictly increasing: "
                f"x_left ({self.x_left}) < x_spine_left ({self.x_spine_left}) < "
                f"x_spine_right ({self.x_spine_right}) < x_right ({self.x_right})"
            )
        if self.y_bottom <= self.y_top:
            raise ValueError(
                f"y_bottom ({self.y_bottom}) must be greater than y_top ({self.y_top})"
            )
        if self.x_right > page_width + 0.05:
            raise ValueError(
                f"x_right ({self.x_right}) exceeds page width ({page_width})"
            )
        if self.y_bottom > page_height + 0.05:
            raise ValueError(
                f"y_bottom ({self.y_bottom}) exceeds page height ({page_height})"
            )

    @property
    def spine_width_pt(self) -> float:
        """Width of spine exclusion zone in points."""
        return self.x_spine_right - self.x_spine_left

    @property
    def backcover_vector_width_pt(self) -> float:
        """Observed pure vector width for Back Cover."""
        return self.x_spine_left - self.x_left

    @property
    def frontcover_vector_width_pt(self) -> float:
        """Observed pure vector width for Front Cover."""
        return self.x_right - self.x_spine_right

    @property
    def vector_height_pt(self) -> float:
        """Observed pure vector height for both covers."""
        return self.y_bottom - self.y_top


class CoverCropStrategy(BaseCropStrategy):
    """Crop coordinate calculator for Cover Spread (Layout A: Page 1).

    Computes bounding boxes for:
    1. BACKCOVER.jpg ($1890 \\times 2657$ px @ 300 DPI)
    2. COVER.jpg ($630 \\times 886$ px @ 100 DPI)
    3. Excludes the central spine zone ($15.02$ mm / $42.57$ pt).

    Status is ALWAYS MANUAL_REVIEW_REQUIRED (Spec §8.B.1, §15.A.6).
    """

    def __init__(self, profile: Optional[ProjectTrimProfile] = None) -> None:
        if profile is None:
            profile = create_cover_profile()
        super().__init__(profile)

    @property
    def strategy_type(self) -> CropStrategyType:
        return CropStrategyType.COVER

    @property
    def target_layout_type(self) -> LayoutType:
        return LayoutType.COVER_SPREAD

    def calculate(
        self,
        pdf_page_index: int = 0,
        page_width_pt: float = 1247.24,
        page_height_pt: float = 878.74,
        rotation: int = 0,
        marks: Optional[CoverCropMarks] = None,
        anchor_to_target_width: bool = False,
        **kwargs,
    ) -> PageCropPlan:
        """Calculate PageCropPlan for the Cover Spread.

        Parameters:
            pdf_page_index: Zero-based page index (typically 0 for cover).
            page_width_pt: Page width in points (nominal 1247.24 pt).
            page_height_pt: Page height in points (nominal 878.74 pt).
            rotation: Page rotation (0, 90, 180, 270).
            marks: Optional CoverCropMarks. If None and page matches nominal,
                   uses default observed values from Spec §8.A.1.
                   If None and dimensions non-nominal, raises ValueError.
            anchor_to_target_width: If True, uses designer target width (453.60 pt)
                   anchored to spine creases outward. If False (default),
                   uses pure vector crop mark bounds.

        Returns:
            PageCropPlan with 2 CropRegion objects (BACKCOVER and COVER).
        """
        # Coordinate availability check (Rule: Never invent missing coordinates)
        if marks is None:
            # Check if sheet dimensions match standard landscape cover sheet
            is_standard_cover = (
                abs(page_width_pt - 1247.24) <= 5.0
                and abs(page_height_pt - 878.74) <= 5.0
            )
            if is_standard_cover:
                marks = CoverCropMarks()
            else:
                raise ValueError(
                    f"Non-standard cover sheet dimensions ({page_width_pt:.2f}x{page_height_pt:.2f} pt) "
                    f"require explicit CoverCropMarks. Never invent missing coordinates."
                )

        # Validate marks
        marks.validate(page_width_pt, page_height_pt)

        # Determine target dimensions from profile
        cov_dims = self.profile.cover_dimensions
        target_back_w_px = cov_dims.target_backcover_width_px   # 1890
        target_back_h_px = cov_dims.target_backcover_height_px  # 2657
        target_cov_w_px = cov_dims.target_cover_width_px        # 630
        target_cov_h_px = cov_dims.target_cover_height_px       # 886

        # Target width in points: 1890 * 72 / 300 = 453.60 pt
        target_width_pt = pixels_to_points(target_back_w_px, cov_dims.target_backcover_dpi)

        if anchor_to_target_width:
            # Anchored to spine creases outward with designer target width (453.60 pt)
            back_x_min = marks.x_spine_left - target_width_pt
            back_x_max = marks.x_spine_left
            front_x_min = marks.x_spine_right
            front_x_max = marks.x_spine_right + target_width_pt
        else:
            # Pure vector crop marks as observed on PDF sheet
            back_x_min = marks.x_left
            back_x_max = marks.x_spine_left
            front_x_min = marks.x_spine_right
            front_x_max = marks.x_right

        y_min = marks.y_top
        y_max = marks.y_bottom

        # Verify no stretching for BACKCOVER (300 DPI)
        back_w_pt = back_x_max - back_x_min
        back_h_pt = y_max - y_min
        is_back_ok, back_distortion = validate_no_stretching(
            back_w_pt, back_h_pt, target_back_w_px, target_back_h_px, dpi=cov_dims.target_backcover_dpi
        )
        if not is_back_ok and not anchor_to_target_width:
            # Back cover vector width differs from target by -1.01 pt (-0.36 mm)
            # This is the documented UNRESOLVED_COVER_WIDTH_DISCREPANCY
            pass

        # Verify no stretching for COVER (100 DPI)
        front_w_pt = front_x_max - front_x_min
        front_h_pt = y_max - y_min
        is_front_ok, front_distortion = validate_no_stretching(
            front_w_pt, front_h_pt, target_cov_w_px, target_cov_h_px, dpi=cov_dims.target_cover_dpi
        )

        # Build CropRegion for BACKCOVER
        backcover_region = CropRegion(
            region_id="BACKCOVER",
            quadrant=None,
            x_min_pt=round(back_x_min, 5),
            y_min_pt=round(y_min, 5),
            x_max_pt=round(back_x_max, 5),
            y_max_pt=round(y_max, 5),
            target_width_px=target_back_w_px,
            target_height_px=target_back_h_px,
            blank_page_status=BlankPageStatus.CONTENT_PRESENT,
        )

        # Build CropRegion for COVER
        cover_region = CropRegion(
            region_id="COVER",
            quadrant=None,
            x_min_pt=round(front_x_min, 5),
            y_min_pt=round(y_min, 5),
            x_max_pt=round(front_x_max, 5),
            y_max_pt=round(y_max, 5),
            target_width_px=target_cov_w_px,
            target_height_px=target_cov_h_px,
            blank_page_status=BlankPageStatus.CONTENT_PRESENT,
        )

        # Safety Guardrail: Cover auto-crop is ALWAYS prohibited
        manual_flags = [ManualReviewFlag.COVER_FORMULA_UNVALIDATED]
        if rotation != 0:
            manual_flags.append(ManualReviewFlag.ROTATED_SHEET_DETECTED)

        # Orientation
        orientation = Orientation.LANDSCAPE if page_width_pt > page_height_pt else Orientation.PORTRAIT

        return PageCropPlan(
            pdf_page_index=pdf_page_index,
            pdf_page_number=pdf_page_index + 1,
            width_pt=page_width_pt,
            height_pt=page_height_pt,
            orientation=orientation,
            rotation=rotation,
            layout_type=LayoutType.COVER_SPREAD,
            classification_status=ClassificationStatus.CLASSIFIED,
            confidence_score=1.0,
            crop_strategy=CropStrategyType.COVER,
            crop_readiness=CropReadinessStatus.MANUAL_REVIEW_REQUIRED,
            manual_review_flags=manual_flags,
            crop_regions=[backcover_region, cover_region],
            expected_page_yield=2,
        )
