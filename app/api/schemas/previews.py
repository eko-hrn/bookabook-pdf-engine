"""Preview API schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PreviewRegionInfo(BaseModel):
    """Structured metadata and preview URL for a single cropped output region."""

    region_id: str = Field(..., description="Region identifier (e.g. BACKCOVER, COVER, PAGE-01)")
    quadrant: Optional[int] = Field(None, description="4-Up quadrant index (1=TL, 2=TR, 3=BL, 4=BR)")
    width_pt: float = Field(..., description="Crop region width in points")
    height_pt: float = Field(..., description="Crop region height in points")
    target_width_px: int = Field(..., description="Expected cropped output width in pixels")
    target_height_px: int = Field(..., description="Expected cropped output height in pixels")
    blank_page_status: str = Field(..., description="Blank page detection result")
    preview_image_url: str = Field(..., description="API endpoint URL to fetch cropped region PNG preview")


class PagePreviewInfo(BaseModel):
    """Structured preview metadata for a single sheet/page."""

    page_number: int = Field(..., description="1-based PDF page number")
    pdf_page_index: int = Field(..., description="0-based PDF page index")
    width_pt: float = Field(..., description="Sheet width in points")
    height_pt: float = Field(..., description="Sheet height in points")
    orientation: str = Field(..., description="Sheet orientation")
    layout_type: Optional[str] = Field(None, description="Layout classification")
    crop_readiness: str = Field(..., description="Crop readiness status")
    expected_page_yield: int = Field(..., description="Expected cropped output count")
    preview_image_url: str = Field(..., description="API endpoint URL to fetch PNG preview image")
    status_badge: Dict[str, Any] = Field(..., description="Visual badge status and style")
    warnings: List[str] = Field(default_factory=list, description="Warnings associated with sheet")
    unresolved_discrepancies: List[str] = Field(default_factory=list, description="Unresolved specification discrepancies")
    regions: List[PreviewRegionInfo] = Field(
        default_factory=list,
        description="Structured crop regions belonging to this PDF sheet",
    )


class DocumentPreviewResponse(BaseModel):
    """Structured preview summary for an entire document."""

    document_id: str = Field(..., description="Document identifier")
    source_filename: str = Field(..., description="Original filename")
    total_pages: int = Field(..., description="Total PDF sheets")
    expected_book_pages: int = Field(..., description="Expected final book page yield")
    document_status: str = Field(..., description="Document readiness status")
    has_unknown_layout: bool = Field(..., description="Whether any unknown layout was encountered")
    has_manual_review_required: bool = Field(..., description="Whether manual review is required")
    pages: List[PagePreviewInfo] = Field(default_factory=list, description="Page preview metadata list")
    validation_summary: Dict[str, Any] = Field(default_factory=dict, description="Summary of validation checks")

