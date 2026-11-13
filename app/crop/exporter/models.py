"""Data models for Bookabook 300 DPI JPEG production export pipeline."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PageKind(str, Enum):
    """Logical role of an exported JPG page in a finished Bookabook book."""

    COVER = "COVER"
    CONTENT = "CONTENT"
    BACKCOVER = "BACKCOVER"


class CompressionStatus(str, Enum):
    """Per-page or document-level JPEG compression outcome."""

    PASSED = "PASSED"
    FAILED = "FAILED"


class CompressionTier(str, Enum):
    """Classification of resulting JPEG byte-size budget tier."""

    COMPACT_HIGH_QUALITY = "COMPACT_HIGH_QUALITY"      # < 300 KB (307,200 B)
    WITHIN_400KB_LIMIT = "WITHIN_400KB_LIMIT"          # 300 KB .. <= 400 KB (409,600 B)
    WITHIN_500KB_LIMIT = "WITHIN_500KB_LIMIT"          # 300 KB .. <= 500 KB (512,000 B) - backward compat
    BACKCOVER_WITHIN_1MB = "BACKCOVER_WITHIN_1MB"      # > 400 KB .. <= 1 MB (1,048,576 B)
    # Retained for backward compatibility with existing payloads/tests
    TARGET_300_700KB = "TARGET_300_700KB"
    MEDIUM_700KB_1MB = "MEDIUM_700KB_1MB"
    COMPLEX_1_2MB = "COMPLEX_1_2MB"


class CompressionFailureDetail(BaseModel):
    """Structured failure payload when minimum JPEG quality still exceeds size cap."""

    filename: str
    page_key: str
    page_kind: PageKind
    actual_size_bytes: int = Field(..., gt=0)
    max_allowed_bytes: int = Field(..., gt=0)
    min_quality_threshold: int = Field(..., ge=1, le=100)
    quality_attempted: int = Field(..., ge=1, le=100)
    reason: str


class ExportedPageArtifact(BaseModel):
    """Metadata (and optional in-memory bytes) for one cropped 300 DPI RGB JPEG."""

    page_key: str = Field(..., description="Logical key: COVER, PAGE-01..PAGE-N, BACKCOVER")
    filename: str = Field(..., description="Deterministic output filename ending with .jpg")
    page_kind: PageKind = Field(..., description="Page role: COVER, CONTENT, or BACKCOVER")
    order_index: int = Field(..., ge=0, description="Display/reading order: 0=COVER, 1..N=CONTENT, N+1=BACKCOVER")
    source_pdf_page: int = Field(..., ge=1, description="1-based sheet number in source PDF")
    quadrant: Optional[int] = Field(default=None, ge=1, le=4, description="4-Up quadrant (1..4) when applicable")

    width_pt: float = Field(..., gt=0, description="Cropped physical width in PDF points")
    height_pt: float = Field(..., gt=0, description="Cropped physical height in PDF points")
    width_px: int = Field(..., gt=0, description="Pixel width at render DPI")
    height_px: int = Field(..., gt=0, description="Pixel height at render DPI")
    dpi: int = Field(default=300, gt=0, description="Render resolution in DPI")
    colorspace: str = Field(default="RGB", description="Output color mode")
    image_format: str = Field(default="JPEG", description="Output image container format")

    file_size_bytes: int = Field(..., gt=0, description="Encoded JPEG byte size")
    max_allowed_bytes: int = Field(default=409_600, gt=0, description="Category byte limit")
    quality_used: int = Field(..., ge=1, le=100, description="Pillow JPEG quality parameter used")
    subsampling_used: str = Field(..., description="Chroma subsampling label: 4:4:4, 4:2:2, or 4:2:0")
    compression_tier: CompressionTier = Field(..., description="Resulting file-size tier")
    compression_status: CompressionStatus = Field(
        default=CompressionStatus.PASSED,
        description="PASSED if JPEG meets size/readability policy without downscaling",
    )
    is_blank: bool = Field(default=False, description="Whether region was flagged nearly blank")
    sha256: str = Field(..., description="Hex SHA-256 checksum of exported JPEG bytes")

    image_bytes: Optional[bytes] = Field(
        default=None,
        exclude=True,
        description="Raw JPEG payload (omitted from JSON serialization)",
    )


class DocumentExportValidation(BaseModel):
    """Automated geometry & compression validation summary for an export batch."""

    is_valid: bool
    auto_validated: bool = True
    compression_status: CompressionStatus = CompressionStatus.PASSED
    total_pdf_pages: int
    cover_detected: bool
    backcover_detected: bool
    content_pages_count: int
    blank_pages_detected: int = 0
    total_exported_files: int
    files_under_300kb: int = 0
    files_300_to_700kb: int = 0
    files_700kb_to_1mb: int = 0
    files_1mb_to_2mb: int = 0
    files_over_2mb: int = 0
    files_within_400kb: int = 0
    files_within_500kb: int = 0
    files_over_400kb_within_1mb: int = 0
    files_over_500kb_within_1mb: int = 0
    files_over_policy_limit: int = 0
    compression_failures: list[CompressionFailureDetail] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class DocumentExportResult(BaseModel):
    """Complete ordered result of exporting a Bookabook PDF into production JPGs."""

    source_filename: str
    target_dpi: int = 300
    pages: list[ExportedPageArtifact]
    validation: DocumentExportValidation

