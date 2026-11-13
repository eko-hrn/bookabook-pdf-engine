"""Dimension, DPI, and anti-stretching validation rules (Phase 1.2.2.3).

Validates:
1. Expected point dimensions against profile configuration.
2. Target pixel dimensions and render DPI.
3. Aspect ratio consistency (strictly prohibits image stretching/scaling).
4. Unresolved discrepancy preservation.
"""

from __future__ import annotations

from typing import Optional

from app.crop.calculator.conversions import points_to_pixels, validate_no_stretching
from app.crop.calculator.unresolved import (
    UNRESOLVED_COVER_WIDTH_DISCREPANCY,
    UNRESOLVED_ROUNDING_1PX,
)
from app.crop.models.crop_region import CropRegion
from app.crop.models.enums import LayoutType
from app.crop.models.project_profile import ProjectTrimProfile

DEFAULT_MAX_ASPECT_RATIO_DISTORTION_PERCENT: float = 0.5


def validate_region_dimensions(
    region: CropRegion,
    profile: ProjectTrimProfile,
    layout_type: Optional[LayoutType] = None,
    max_distortion_percent: float = DEFAULT_MAX_ASPECT_RATIO_DISTORTION_PERCENT,
) -> tuple[list[str], list[str]]:
    """Validate that a crop region matches profile dimension and anti-stretching rules.

    Returns:
        (errors, warnings)
    """
    errors: list[str] = []
    warnings: list[str] = []

    width_pt = region.width_pt
    height_pt = region.height_pt

    # 1. Layout-specific dimension expectations
    if layout_type == LayoutType.IMPOSITION_4UP or (layout_type is None and region.quadrant is not None):
        # 4-Up Content Page: Target is Option B (425.52 x 609.12 pt -> 1773 x 2538 px @ 300 DPI)
        expected_w_px = profile.target_content_width_px
        expected_h_px = profile.target_content_height_px
        expected_dpi = profile.dpi

        if region.target_width_px != expected_w_px:
            errors.append(
                f"Region {region.region_id}: target_width_px ({region.target_width_px}) "
                f"does not match profile target ({expected_w_px})"
            )
        if region.target_height_px != expected_h_px:
            errors.append(
                f"Region {region.region_id}: target_height_px ({region.target_height_px}) "
                f"does not match profile target ({expected_h_px})"
            )

        # Anti-stretching validation
        is_no_stretch, distortion = validate_no_stretching(
            width_pt, height_pt, expected_w_px, expected_h_px, dpi=expected_dpi,
            max_distortion_percent=max_distortion_percent,
        )
        if not is_no_stretch:
            errors.append(
                f"Region {region.region_id}: image stretching detected ({distortion:.2f}% distortion). "
                f"Crop size {width_pt:.2f}x{height_pt:.2f} pt does not match target aspect ratio."
            )

    elif layout_type == LayoutType.COVER_SPREAD or region.region_id in {"BACKCOVER", "COVER"}:
        cov_dims = profile.cover_dimensions
        if region.region_id == "BACKCOVER":
            expected_w_px = cov_dims.target_backcover_width_px  # 1890
            expected_h_px = cov_dims.target_backcover_height_px  # 2657
            expected_dpi = cov_dims.target_backcover_dpi         # 300
            warnings.append(
                f"Back cover width has unresolved vector discrepancy. Status: {UNRESOLVED_COVER_WIDTH_DISCREPANCY}"
            )
        elif region.region_id == "COVER":
            expected_w_px = cov_dims.target_cover_width_px       # 630
            expected_h_px = cov_dims.target_cover_height_px      # 886
            expected_dpi = cov_dims.target_cover_dpi            # 100
            # Informative warning about unresolved 1 px rounding artifact
            warnings.append(
                f"Front cover resolution is {expected_dpi} DPI ({expected_w_px}x{expected_h_px} px). "
                f"Note: {cov_dims.frontcover_height_discrepancy_note}. Status: {UNRESOLVED_ROUNDING_1PX}"
            )
        else:
            expected_w_px = region.target_width_px
            expected_h_px = region.target_height_px
            expected_dpi = profile.dpi

        if region.target_width_px != expected_w_px:
            errors.append(
                f"Region {region.region_id}: target_width_px ({region.target_width_px}) "
                f"does not match expected cover target ({expected_w_px})"
            )
        if region.target_height_px != expected_h_px:
            errors.append(
                f"Region {region.region_id}: target_height_px ({region.target_height_px}) "
                f"does not match expected cover target ({expected_h_px})"
            )

        # In Cover, vector marks have documented width discrepancies (-1.01 pt / +0.91 pt / empirical 436.54 pt)
        # We verify that distortion does not exceed the known discrepancy window (~4.0%).
        is_no_stretch, distortion = validate_no_stretching(
            width_pt, height_pt, expected_w_px, expected_h_px, dpi=expected_dpi,
            max_distortion_percent=4.5,
        )
        if not is_no_stretch:
            errors.append(
                f"Region {region.region_id}: severe aspect ratio distortion ({distortion:.2f}%). "
                f"Cannot stretch cover image."
            )
        elif distortion > 0.5:
            warnings.append(
                f"Region {region.region_id}: vector aspect ratio differs by {distortion:.2f}% from target pixel ratio. "
                f"Status: {UNRESOLVED_COVER_WIDTH_DISCREPANCY}"
            )

    elif layout_type == LayoutType.SINGLE_PAGE:
        expected_w_px = profile.target_content_width_px
        expected_h_px = profile.target_content_height_px
        expected_dpi = profile.dpi

        if region.target_width_px != expected_w_px:
            errors.append(
                f"Region {region.region_id}: target_width_px ({region.target_width_px}) "
                f"does not match profile target ({expected_w_px})"
            )
        if region.target_height_px != expected_h_px:
            errors.append(
                f"Region {region.region_id}: target_height_px ({region.target_height_px}) "
                f"does not match profile target ({expected_h_px})"
            )

        is_no_stretch, distortion = validate_no_stretching(
            width_pt, height_pt, expected_w_px, expected_h_px, dpi=expected_dpi,
            max_distortion_percent=max_distortion_percent,
        )
        if not is_no_stretch:
            warnings.append(
                f"Single page {region.region_id} has non-nominal aspect ratio "
                f"({distortion:.2f}% distortion against 1773x2538 px)."
            )

    return errors, warnings
