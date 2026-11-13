"""Crop Coordinate Calculator package (Phase 1.2.2.2).

Provides mathematical coordinate calculation and safety guardrails for:
1. CoverCropStrategy (Layout A: Cover Spread)
2. Imposition4UpCropStrategy (Layout B: 4-Up Imposition Grid)
3. SinglePageCropStrategy (Layout C: Single Page 1-Up)
4. CropCoordinateCalculator (Unified coordinator)
"""

from app.crop.calculator.base import BaseCropStrategy
from app.crop.calculator.calculator import CropCoordinateCalculator
from app.crop.calculator.conversions import (
    MM_PER_INCH,
    MM_PER_PT,
    PT_PER_INCH,
    PT_PER_MM,
    check_tick_deviation,
    mm_to_points,
    pixels_to_points,
    points_to_mm,
    points_to_pixels,
    validate_bounding_box,
    validate_no_stretching,
)
from app.crop.calculator.cover_strategy import (
    DEFAULT_COVER_BOTTOM_TRIM_PT,
    DEFAULT_COVER_LEFT_TRIM_PT,
    DEFAULT_COVER_RIGHT_TRIM_PT,
    DEFAULT_COVER_SPINE_INNER_LEFT_PT,
    DEFAULT_COVER_SPINE_INNER_RIGHT_PT,
    DEFAULT_COVER_TOP_TRIM_PT,
    CoverCropMarks,
    CoverCropStrategy,
)
from app.crop.calculator.imposition_4up_strategy import (
    NOMINAL_4UP_HALF_HEIGHT_PT,
    NOMINAL_4UP_HALF_WIDTH_PT,
    NOMINAL_4UP_SHEET_HEIGHT_PT,
    NOMINAL_4UP_SHEET_WIDTH_PT,
    Imposition4UpCropStrategy,
    TickMarkCoordinates,
)
from app.crop.calculator.single_page_strategy import (
    NOMINAL_SINGLE_PAGE_HEIGHT_PT,
    NOMINAL_SINGLE_PAGE_WIDTH_PT,
    SinglePageCropStrategy,
)
from app.crop.calculator.unresolved import (
    ALL_UNRESOLVED_DECISIONS,
    UNRESOLVED_COVER_WIDTH_DISCREPANCY,
    UNRESOLVED_ROUNDING_1PX,
    UNRESOLVED_SINGLE_PAGE_NORMALIZATION_POLICY,
)

__all__ = [
    # Main calculator
    "CropCoordinateCalculator",
    # Base strategy
    "BaseCropStrategy",
    # Strategy implementations
    "CoverCropStrategy",
    "CoverCropMarks",
    "Imposition4UpCropStrategy",
    "TickMarkCoordinates",
    "SinglePageCropStrategy",
    # Conversions & checks
    "points_to_pixels",
    "pixels_to_points",
    "mm_to_points",
    "points_to_mm",
    "check_tick_deviation",
    "validate_no_stretching",
    "validate_bounding_box",
    "PT_PER_INCH",
    "MM_PER_INCH",
    "PT_PER_MM",
    "MM_PER_PT",
    # Constants
    "DEFAULT_COVER_LEFT_TRIM_PT",
    "DEFAULT_COVER_SPINE_INNER_LEFT_PT",
    "DEFAULT_COVER_SPINE_INNER_RIGHT_PT",
    "DEFAULT_COVER_RIGHT_TRIM_PT",
    "DEFAULT_COVER_TOP_TRIM_PT",
    "DEFAULT_COVER_BOTTOM_TRIM_PT",
    "NOMINAL_4UP_SHEET_WIDTH_PT",
    "NOMINAL_4UP_SHEET_HEIGHT_PT",
    "NOMINAL_4UP_HALF_WIDTH_PT",
    "NOMINAL_4UP_HALF_HEIGHT_PT",
    "NOMINAL_SINGLE_PAGE_WIDTH_PT",
    "NOMINAL_SINGLE_PAGE_HEIGHT_PT",
    # Unresolved decisions
    "UNRESOLVED_ROUNDING_1PX",
    "UNRESOLVED_COVER_WIDTH_DISCREPANCY",
    "UNRESOLVED_SINGLE_PAGE_NORMALIZATION_POLICY",
    "ALL_UNRESOLVED_DECISIONS",
]

