"""Imposition4UpCropStrategy — Crop coordinate calculation for 4-Up Imposition Grid (Layout B).

Implements Section 6.B, 8.B.2, 10.A, 11, 14.B.1, 15.A.2, 15.A.5, and 17 of
Layout Classifier Specification v1.3.4.

Key Principles:
1. Midpoint tick marks define the cut anchor:
   x_cut = (x_T + x_B) / 2 ≈ 439.37 pt
   y_cut = (y_L + y_R) / 2 ≈ 623.62 pt
2. Interior dividing lines have 0.00 pt margin (flush cut).
3. Option B net dimensions: 425.52 x 609.12 pt → exactly 1773 x 2538 px @ 300 DPI.
4. Outer margins trimmed: 13.85 pt (horizontal) / 14.50 pt (vertical).
5. Tick mark deviation tolerance: ≤ 1.0 mm (≈ 2.835 pt).
   Exceeding tolerance triggers MANUAL_REVIEW_REQUIRED with flag TICK_DEVIATION_EXCEEDED.
6. Quadrant order: Q1 (Top-Left), Q2 (Top-Right), Q3 (Bottom-Left), Q4 (Bottom-Right).
7. Yield: 4 pages per sheet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.crop.calculator.base import BaseCropStrategy
from app.crop.calculator.conversions import (
    check_tick_deviation,
    points_to_mm,
    points_to_pixels,
    validate_bounding_box,
    validate_no_stretching,
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
from app.crop.profiles.profile_configs import create_imposition_4up_profile


# Standard sheet dimensions for Bookabook 4-Up (Portrait, Spec §3.A.1, §17)
NOMINAL_4UP_SHEET_WIDTH_PT: float = 878.74
NOMINAL_4UP_SHEET_HEIGHT_PT: float = 1247.24

# Ideal midpoint coordinates on standard sheet
NOMINAL_4UP_HALF_WIDTH_PT: float = 439.37
NOMINAL_4UP_HALF_HEIGHT_PT: float = 623.62


@dataclass(frozen=True)
class TickMarkCoordinates:
    """Midpoint tick mark positions on a 4-Up sheet perimeter (Spec §5 Rule 2, §6.B).

    x_top: X coordinate of the top edge midpoint tick (x ≈ W/2, y ∈ [0, 10] pt)
    x_bottom: X coordinate of the bottom edge midpoint tick (x ≈ W/2, y ∈ [H-10, H] pt)
    y_left: Y coordinate of the left edge midpoint tick (x ∈ [0, 10] pt, y ≈ H/2)
    y_right: Y coordinate of the right edge midpoint tick (x ∈ [W-10, W] pt, y ≈ H/2)
    """

    x_top: float = NOMINAL_4UP_HALF_WIDTH_PT
    x_bottom: float = NOMINAL_4UP_HALF_WIDTH_PT
    y_left: float = NOMINAL_4UP_HALF_HEIGHT_PT
    y_right: float = NOMINAL_4UP_HALF_HEIGHT_PT

    @property
    def delta_x_pt(self) -> float:
        """Horizontal axis deviation between top and bottom ticks in points."""
        return abs(self.x_top - self.x_bottom)

    @property
    def delta_y_pt(self) -> float:
        """Vertical axis deviation between left and right ticks in points."""
        return abs(self.y_left - self.y_right)

    @property
    def delta_x_mm(self) -> float:
        """Horizontal axis deviation in millimeters."""
        return points_to_mm(self.delta_x_pt)

    @property
    def delta_y_mm(self) -> float:
        """Vertical axis deviation in millimeters."""
        return points_to_mm(self.delta_y_pt)

    @property
    def x_cut(self) -> float:
        """Computed horizontal interior cut anchor."""
        return (self.x_top + self.x_bottom) / 2.0

    @property
    def y_cut(self) -> float:
        """Computed vertical interior cut anchor."""
        return (self.y_left + self.y_right) / 2.0

    def validate(self, page_width: float, page_height: float) -> None:
        """Validate that tick coordinates fall inside the page boundary."""
        for name, val, limit in [
            ("x_top", self.x_top, page_width),
            ("x_bottom", self.x_bottom, page_width),
            ("y_left", self.y_left, page_height),
            ("y_right", self.y_right, page_height),
        ]:
            if val < 0 or val > limit:
                raise ValueError(
                    f"Tick coordinate {name}={val:.3f} is outside page range [0, {limit:.3f}]"
                )


class Imposition4UpCropStrategy(BaseCropStrategy):
    """Crop coordinate calculator for 4-Up Imposition Grid (Layout B: Pages 2–6).

    Computes 4 clean A5 book page bounding boxes (Q1–Q4) from midpoint tick anchors:
    - Q1: Top-Left  (direction -X, -Y from anchor)
    - Q2: Top-Right (direction +X, -Y from anchor)
    - Q3: Bottom-Left (direction -X, +Y from anchor)
    - Q4: Bottom-Right (direction +X, +Y from anchor)

    Enforces:
    - Target dimensions: 1773 x 2538 px @ 300 DPI (Option B).
    - Tick mark tolerance: ≤ 1.0 mm.
    - Yield: exactly 4 pages.
    """

    def __init__(self, profile: Optional[ProjectTrimProfile] = None) -> None:
        if profile is None:
            profile = create_imposition_4up_profile()
        super().__init__(profile)

    @property
    def strategy_type(self) -> CropStrategyType:
        return CropStrategyType.IMPOSITION_4UP

    @property
    def target_layout_type(self) -> LayoutType:
        return LayoutType.IMPOSITION_4UP

    def calculate(
        self,
        pdf_page_index: int = 1,
        page_width_pt: float = NOMINAL_4UP_SHEET_WIDTH_PT,
        page_height_pt: float = NOMINAL_4UP_SHEET_HEIGHT_PT,
        rotation: int = 0,
        ticks: Optional[TickMarkCoordinates] = None,
        start_page_number: Optional[int] = None,
        blank_statuses: Optional[list[BlankPageStatus]] = None,
        is_flipped: bool = False,
        **kwargs,
    ) -> PageCropPlan:
        """Calculate PageCropPlan for a 4-Up Imposition sheet.

        Parameters:
            pdf_page_index: Zero-based page index (e.g. 1 for sheet 2 / pages 1..4).
            page_width_pt: Measured page width in points.
            page_height_pt: Measured page height in points.
            rotation: PDF page rotation (0, 90, 180, 270).
            ticks: Optional TickMarkCoordinates. If None and sheet matches nominal,
                   defaults to ideal midpoint ticks. If None and non-nominal, raises ValueError.
            start_page_number: Starting book page number for naming (default: (pdf_page_index - 1) * 4 + 1).
            blank_statuses: Optional list of 4 BlankPageStatus values for Q1..Q4.
            is_flipped: Whether the sheet was classified as CANDIDATE_IMPOSITION_4UP_FLIPPED.

        Returns:
            PageCropPlan with 4 CropRegion objects.
        """
        # Coordinate availability check (Rule: Never invent missing coordinates)
        if ticks is None:
            is_standard = (
                abs(page_width_pt - NOMINAL_4UP_SHEET_WIDTH_PT) <= 5.0
                and abs(page_height_pt - NOMINAL_4UP_SHEET_HEIGHT_PT) <= 5.0
            )
            if is_standard:
                ticks = TickMarkCoordinates(
                    x_top=page_width_pt / 2.0,
                    x_bottom=page_width_pt / 2.0,
                    y_left=page_height_pt / 2.0,
                    y_right=page_height_pt / 2.0,
                )
            else:
                raise ValueError(
                    f"Non-standard 4-Up sheet dimensions ({page_width_pt:.2f}x{page_height_pt:.2f} pt) "
                    f"require explicit TickMarkCoordinates. Never invent missing coordinates."
                )

        # Validate tick coordinates within sheet
        ticks.validate(page_width_pt, page_height_pt)

        # 1. Compute cut anchor (x_cut, y_cut) per Spec §6.B, §8.B.2
        x_cut = ticks.x_cut
        y_cut = ticks.y_cut

        # 2. Check tick deviation against tolerance (1.0 mm per Spec §6.B)
        within_tolerance, dx_mm, dy_mm = check_tick_deviation(
            ticks.delta_x_pt,
            ticks.delta_y_pt,
            self.profile.tick_deviation_tolerance_mm,
        )

        # 3. Determine target dimensions from profile (Option B: 425.52 x 609.12 pt)
        w_net = self.profile.target_content_width_pt    # 425.52
        h_net = self.profile.target_content_height_pt   # 609.12
        w_px = self.profile.target_content_width_px     # 1773
        h_px = self.profile.target_content_height_px    # 2538

        # Verify no stretching (distortion must be 0.0% for exact target)
        is_no_stretch, distortion = validate_no_stretching(
            w_net, h_net, w_px, h_px, dpi=self.profile.dpi
        )
        if not is_no_stretch:
            raise ValueError(
                f"Crop dimensions ({w_net}x{h_net} pt) would cause image stretching "
                f"against target ({w_px}x{h_px} px @ {self.profile.dpi} DPI). "
                f"Distortion={distortion:.2f}%"
            )

        # 4. Compute Quadrants 1–4 Bounding Boxes (Spec §8.B.2 Opsi B Formula)
        # Q1: Top-Left (-X, -Y)
        q1_bbox = (x_cut - w_net, y_cut - h_net, x_cut, y_cut)
        # Q2: Top-Right (+X, -Y)
        q2_bbox = (x_cut, y_cut - h_net, x_cut + w_net, y_cut)
        # Q3: Bottom-Left (-X, +Y)
        q3_bbox = (x_cut - w_net, y_cut, x_cut, y_cut + h_net)
        # Q4: Bottom-Right (+X, +Y)
        q4_bbox = (x_cut, y_cut, x_cut + w_net, y_cut + h_net)

        quadrant_bboxes = [
            (1, q1_bbox),
            (2, q2_bbox),
            (3, q3_bbox),
            (4, q4_bbox),
        ]

        # Determine page numbering for region IDs (e.g. PAGE-01..PAGE-04)
        if start_page_number is None:
            if pdf_page_index > 0:
                start_page_number = (pdf_page_index - 1) * 4 + 1
            else:
                start_page_number = 1

        if blank_statuses is None or len(blank_statuses) != 4:
            blank_statuses = [BlankPageStatus.CONTENT_PRESENT] * 4

        # 5. Build CropRegion objects
        crop_regions: list[CropRegion] = []
        for i, (q_idx, (x_min, y_min, x_max, y_max)) in enumerate(quadrant_bboxes):
            page_num = start_page_number + i
            region_id = f"PAGE-{page_num:02d}"

            # Validate bbox geometry
            bbox_errors = validate_bounding_box(
                x_min, y_min, x_max, y_max, page_width_pt, page_height_pt
            )
            if bbox_errors:
                raise ValueError(
                    f"Invalid bounding box for Quadrant {q_idx} ({region_id}): {', '.join(bbox_errors)}"
                )

            crop_regions.append(
                CropRegion(
                    region_id=region_id,
                    quadrant=q_idx,
                    x_min_pt=round(x_min, 4),
                    y_min_pt=round(y_min, 4),
                    x_max_pt=round(x_max, 4),
                    y_max_pt=round(y_max, 4),
                    target_width_px=w_px,
                    target_height_px=h_px,
                    blank_page_status=blank_statuses[i],
                )
            )

        # 6. Safety Guardrails & Status Determination
        manual_flags: list[ManualReviewFlag] = []

        if not within_tolerance:
            manual_flags.append(ManualReviewFlag.TICK_DEVIATION_EXCEEDED)

        if rotation != 0:
            manual_flags.append(ManualReviewFlag.ROTATED_SHEET_DETECTED)

        if is_flipped:
            manual_flags.append(ManualReviewFlag.FLIPPED_ORIENTATION_DETECTED)

        if manual_flags:
            crop_readiness = CropReadinessStatus.MANUAL_REVIEW_REQUIRED
        else:
            crop_readiness = CropReadinessStatus.CROP_READY

        classification_status = (
            ClassificationStatus.CANDIDATE_IMPOSITION_4UP_FLIPPED
            if is_flipped
            else ClassificationStatus.CLASSIFIED
        )

        orientation = Orientation.LANDSCAPE if page_width_pt > page_height_pt else Orientation.PORTRAIT

        return PageCropPlan(
            pdf_page_index=pdf_page_index,
            pdf_page_number=pdf_page_index + 1,
            width_pt=page_width_pt,
            height_pt=page_height_pt,
            orientation=orientation,
            rotation=rotation,
            layout_type=LayoutType.IMPOSITION_4UP,
            classification_status=classification_status,
            confidence_score=1.0,
            crop_strategy=CropStrategyType.IMPOSITION_4UP,
            crop_readiness=crop_readiness,
            manual_review_flags=manual_flags,
            crop_regions=crop_regions,
            expected_page_yield=4,
        )

