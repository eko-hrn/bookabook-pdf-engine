"""Crop Plan Validator — Phase 1.2.2.3.

Independent validation layer for CropCoordinateCalculator outputs, verifying:
- Bounding box geometry, positive area, coordinates within page boundaries, and 2D overlaps.
- Output pixel dimensions, DPI, and strict anti-stretching (aspect ratio preservation).
- Layout-specific invariants for 4-Up, Cover Spread, and Single Page.
- Document-level sequence, yield totals, and status aggregation.
"""

from app.crop.validator.bbox_validator import (
    detect_region_overlaps,
    validate_region_geometry,
    validate_spine_exclusion,
)
from app.crop.validator.crop_plan_validator import CropPlanValidator
from app.crop.validator.dimension_validator import (
    DEFAULT_MAX_ASPECT_RATIO_DISTORTION_PERCENT,
    validate_region_dimensions,
)
from app.crop.validator.document_validator import validate_document_plan_integrity
from app.crop.validator.layout_validators import (
    validate_4up_layout_plan,
    validate_cover_layout_plan,
    validate_single_page_layout_plan,
)
from app.crop.validator.report import DocumentValidationReport, PageValidationReport

__all__ = [
    # Main validator
    "CropPlanValidator",
    # Reports
    "PageValidationReport",
    "DocumentValidationReport",
    # Geometry & Bounding Box
    "validate_region_geometry",
    "detect_region_overlaps",
    "validate_spine_exclusion",
    # Dimension & Anti-Stretching
    "validate_region_dimensions",
    "DEFAULT_MAX_ASPECT_RATIO_DISTORTION_PERCENT",
    # Layout Invariants
    "validate_4up_layout_plan",
    "validate_cover_layout_plan",
    "validate_single_page_layout_plan",
    # Document Level
    "validate_document_plan_integrity",
]

