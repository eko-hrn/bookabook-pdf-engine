"""Structured Preview Payload Models (Phase 1.2.2.4).

Defines Pydantic models for the preview visualization layer.
Keeps preview metadata strictly separate from production rendering.

Incorporates:
- Precise point & preview coordinate geometry
- Accessible visual style descriptors and text badges
- Cut lines, trim margins, and spine exclusion zones
- Preservation of unresolved discrepancies and safety guardrails
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field

from app.crop.models.enums import ClassificationStatus, CropReadinessStatus, LayoutType
from app.crop.preview.theme import PreviewVisualStyle, get_status_style


class PreviewBox(BaseModel):
    """Bounding box coordinates in preview canvas space."""

    x: float = Field(..., description="Left edge in preview coordinates")
    y: float = Field(..., description="Top edge in preview coordinates")
    width: float = Field(..., gt=0, description="Width in preview coordinates")
    height: float = Field(..., gt=0, description="Height in preview coordinates")
    x_min: float = Field(..., description="Minimum X in preview coordinates")
    y_min: float = Field(..., description="Minimum Y in preview coordinates")
    x_max: float = Field(..., description="Maximum X in preview coordinates")
    y_max: float = Field(..., description="Maximum Y in preview coordinates")


class PreviewLine(BaseModel):
    """A guide or cut line in preview canvas space."""

    line_type: str = Field(..., description="Type of line: MIDPOINT_CUT_HORIZONTAL, MIDPOINT_CUT_VERTICAL, OUTER_TRIM")
    label: str = Field(..., description="Human-readable text label for accessibility")
    x1: float = Field(..., description="Start X in preview coordinates")
    y1: float = Field(..., description="Start Y in preview coordinates")
    x2: float = Field(..., description="End X in preview coordinates")
    y2: float = Field(..., description="End Y in preview coordinates")
    stroke_color: str = Field(default="#2563EB", description="Stroke hex color")
    stroke_dasharray: str = Field(default="5,3", description="SVG stroke dasharray pattern")
    stroke_width: float = Field(default=1.5, description="Stroke width in preview units")


class PreviewSpineZone(BaseModel):
    """Spine exclusion zone geometry and label for Cover Spread."""

    left_boundary_pt: float = Field(..., description="Left spine boundary in points (e.g. 608.52 pt)")
    right_boundary_pt: float = Field(..., description="Right spine boundary in points (e.g. 651.11 pt)")
    width_pt: float = Field(..., description="Spine width in points (≈ 42.57 pt)")
    width_mm: float = Field(..., description="Spine width in millimeters (15.02 mm)")
    box_preview: PreviewBox = Field(..., description="Spine zone box in preview coordinates")
    label: str = Field(
        default="PROTECTED SPINE ZONE (15.02 mm / 42.57 pt)",
        description="Text label warning that no crop region may enter spine zone",
    )
    visual_style: PreviewVisualStyle = Field(..., description="Visual styling for the spine zone")


class PreviewStatusBadge(BaseModel):
    """Text-and-color badge ensuring status is never communicated by color alone."""

    status: str = Field(..., description="Status string: CROP_READY, MANUAL_REVIEW_REQUIRED, etc.")
    badge_text: str = Field(..., description="Human-readable badge text: e.g. [READY] CROP_READY")
    accessibility_label: str = Field(..., description="Comprehensive accessibility description")
    color: str = Field(..., description="Badge text color hex")
    background_color: str = Field(..., description="Badge background fill hex/rgba")
    pattern_type: str = Field(default="solid", description="Pattern type: solid, dashed, dotted")


class PreviewRegion(BaseModel):
    """A single crop region mapped to preview coordinate space."""

    region_id: str = Field(..., description="Output page identifier (e.g. 'PAGE-01', 'COVER', 'BACKCOVER')")
    quadrant: Optional[int] = Field(default=None, ge=1, le=4, description="Quadrant index (1=TL, 2=TR, 3=BL, 4=BR)")
    bbox_pt: list[float] = Field(..., description="Physical coordinates [x_min, y_min, x_max, y_max] in PDF points")
    bbox_preview: PreviewBox = Field(..., description="Transformed bounding box in preview canvas space")
    target_width_px: int = Field(..., gt=0, description="Target raster width in pixels")
    target_height_px: int = Field(..., gt=0, description="Target raster height in pixels")
    dpi: int = Field(..., gt=0, description="Render resolution in DPI")
    aspect_ratio_pt: float = Field(..., gt=0, description="Physical vector aspect ratio (width_pt / height_pt)")
    aspect_ratio_target_px: float = Field(..., gt=0, description="Target raster aspect ratio (width_px / height_px)")
    aspect_ratio_distortion_percent: float = Field(
        default=0.0,
        description="Aspect ratio distortion percent between vector and raster targets",
    )
    visual_style: PreviewVisualStyle = Field(..., description="Element visual style (color, stroke, pattern)")
    label: str = Field(..., description="Display label overlaid on the region")
    is_blank: bool = Field(default=False, description="Whether this region is flagged as blank")


class PreviewPagePayload(BaseModel):
    """Structured preview payload for a single PDF page."""

    pdf_page_index: int = Field(..., ge=0, description="Zero-based PDF page index")
    pdf_page_number: int = Field(..., ge=1, description="One-based PDF page number")
    layout_type: Optional[LayoutType] = Field(default=None, description="Classified layout type")
    classification_status: ClassificationStatus = Field(..., description="Layout classification result")
    crop_readiness: CropReadinessStatus = Field(..., description="Crop readiness state")
    width_pt: float = Field(..., gt=0, description="PDF page width in points")
    height_pt: float = Field(..., gt=0, description="PDF page height in points")
    orientation: str = Field(..., description="Page orientation: PORTRAIT or LANDSCAPE")
    rotation: int = Field(default=0, description="PDF page rotation in degrees")

    # Canvas & Viewport Mapping
    canvas_width: float = Field(..., gt=0, description="Preview canvas width in units")
    canvas_height: float = Field(..., gt=0, description="Preview canvas height in units")
    scale_factor: float = Field(..., gt=0, description="Uniform scaling factor from points to canvas")
    offset_x: float = Field(..., ge=0, description="Centering X offset in preview canvas")
    offset_y: float = Field(..., ge=0, description="Centering Y offset in preview canvas")
    rendered_page_box: PreviewBox = Field(..., description="Full PDF page boundary in preview space")

    # Visual Elements
    regions: list[PreviewRegion] = Field(default_factory=list, description="Calculated crop regions")
    cut_lines: list[PreviewLine] = Field(default_factory=list, description="Midpoint cut and dividing lines")
    outer_trim_box: Optional[PreviewBox] = Field(default=None, description="Outer sheet trim box for 4-Up")
    spine_zone: Optional[PreviewSpineZone] = Field(default=None, description="Spine exclusion zone for Cover Spread")
    status_badge: PreviewStatusBadge = Field(..., description="Visual status badge with text and pattern")

    # Safety Guardrails & Metadata
    is_auto_crop_allowed: bool = Field(default=False, description="True ONLY when page is CROP_READY")
    is_non_nominal: bool = Field(default=False, description="True for Single Page non-nominal dimensions")
    review_flags: list[str] = Field(default_factory=list, description="Reason flags if MANUAL_REVIEW_REQUIRED")
    warnings: list[str] = Field(default_factory=list, description="Informative warnings (unresolved gaps, etc.)")
    unresolved_discrepancies: list[str] = Field(
        default_factory=list,
        description="Preserved unresolved discrepancies (e.g. UNRESOLVED_COVER_WIDTH_DISCREPANCY)",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional debug/audit metadata")


class PreviewDocumentPayload(BaseModel):
    """Aggregate preview payload for an entire multi-page document."""

    source_filename: str = Field(..., description="Source PDF filename")
    total_pdf_pages: int = Field(..., gt=0, description="Total PDF pages")
    expected_total_book_pages: int = Field(..., ge=0, description="Expected total book pages yield")
    document_status: str = Field(..., description="Document status: AUTO_READY_FOR_PREVIEW, MANUAL_REVIEW_REQUIRED, etc.")
    status_badge: PreviewStatusBadge = Field(..., description="Document-level status badge")
    pages: list[PreviewPagePayload] = Field(default_factory=list, description="Ordered page preview payloads")
    page_sequence_signature: list[str] = Field(default_factory=list, description="Layout type signature per page")
    total_crop_regions: int = Field(default=0, ge=0, description="Total crop regions across all pages")
    has_manual_review_required: bool = Field(default=False, description="Whether document contains held sheets")
    has_unknown_layout: bool = Field(default=False, description="Whether document contains unknown layouts")
    summary: dict[str, Any] = Field(default_factory=dict, description="Summary statistics for UI display")


class PreviewImageOutput(BaseModel):
    """Complete visual preview output for a single PDF page with overlaid crop plan.

    Strictly separates preview visualization from production raster outputs.
    Previews are rendered as PNG (never final production JPGs).
    """

    pdf_page_index: int = Field(..., ge=0, description="Zero-based PDF page index")
    pdf_page_number: int = Field(..., ge=1, description="One-based PDF page number")
    layout_type: Optional[LayoutType] = Field(default=None, description="Classified layout type")
    crop_readiness: CropReadinessStatus = Field(..., description="Crop readiness state")
    image_bytes: bytes = Field(..., description="Rendered PNG bytes with visual overlay")
    image_format: str = Field(default="PNG", description="Image format: strictly PNG for previews")
    width_px: int = Field(..., gt=0, description="Preview image width in pixels")
    height_px: int = Field(..., gt=0, description="Preview image height in pixels")
    dpi: int = Field(..., gt=0, description="Preview render DPI (e.g. 100 DPI)")
    data_uri: str = Field(..., description="Base64 data URI for inline embedding: data:image/png;base64,...")
    temp_file_path: Optional[str] = Field(default=None, description="Optional path to written preview file")
    is_auto_crop_allowed: bool = Field(default=False, description="True ONLY when page is CROP_READY")
    is_non_nominal: bool = Field(default=False, description="True for non-nominal single page dimensions")
    review_flags: list[str] = Field(default_factory=list, description="Reason flags if MANUAL_REVIEW_REQUIRED")
    warnings: list[str] = Field(default_factory=list, description="Informative warnings")
    unresolved_discrepancies: list[str] = Field(
        default_factory=list,
        description="Preserved unresolved discrepancies (e.g. UNRESOLVED_COVER_WIDTH_DISCREPANCY)",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional debug/audit metadata")


