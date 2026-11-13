"""Book Processing, Adaptive JPEG Export, and Public Showcase API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class CompressionFailureItem(BaseModel):
    """Structured failure entry when an image cannot satisfy its byte limit at min quality."""

    filename: str
    page_key: str
    page_kind: str
    actual_size_bytes: int
    max_allowed_bytes: int
    min_quality_threshold: int
    quality_attempted: int
    reason: str


class ExportValidationSummary(BaseModel):
    """Automated geometry and adaptive JPEG validation metrics."""

    is_valid: bool
    auto_validated: bool = True
    compression_status: str = "PASSED"
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
    compression_failures: List[CompressionFailureItem] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class ProcessedPageItem(BaseModel):
    """One cropped 300 DPI RGB JPEG produced by Process PDF."""

    page_key: str
    filename: str
    page_kind: str
    order_index: int
    source_pdf_page: int
    quadrant: Optional[int] = None
    width_px: int
    height_px: int
    dpi: int = 300
    file_size_bytes: int
    max_allowed_bytes: int = 512_000
    quality_used: int
    subsampling_used: str
    compression_tier: str
    compression_status: str = "PASSED"
    is_blank: bool = False
    sha256: str
    preview_url: str
    download_url: str


class ProcessPdfResponse(BaseModel):
    """Response returned immediately after processing a PDF into 300 DPI JPGs."""

    job_id: str
    source_filename: str
    target_dpi: int = 300
    content_pages_count: int
    total_exported_files: int
    validation: ExportValidationSummary
    pages: List[ProcessedPageItem] = Field(default_factory=list)
    zip_download_url: str


class SaveBookRequest(BaseModel):
    """Payload submitted when clicking 'Save Book' on Create Book page."""

    job_id: str = Field(..., min_length=1, description="Staging job_id returned by process-pdf")
    title: str = Field(..., min_length=1, max_length=255)
    author: str = Field(default="", max_length=255)
    authors_all: str = Field(default="", max_length=2000)
    description: str = Field(default="", max_length=5000)
    year: Optional[int] = Field(default=None, ge=1900, le=2100)
    age_group: str = Field(default="", max_length=100)
    sponsor: str = Field(default="", max_length=255)
    content_pages: Optional[int] = Field(default=None, ge=0)
    phone: str = Field(default="", max_length=100)
    email: str = Field(default="", max_length=255)


class BookPageDetail(BaseModel):
    """Metadata and access URLs for a persisted book JPG page."""

    page_key: str
    filename: str
    page_kind: str
    order_index: int
    source_pdf_page: int
    quadrant: Optional[int] = None
    width_px: int
    height_px: int
    dpi: int
    file_size_bytes: int
    quality_used: int
    subsampling_used: str
    compression_tier: str
    sha256: str
    object_key: str
    is_blank: bool = False
    preview_url: str
    download_url: str


class BookSummary(BaseModel):
    """Catalog card metadata for Public Showcase (/books)."""

    book_id: str
    title: str
    author: str
    authors_all: str
    description: str
    year: Optional[int] = None
    age_group: str
    sponsor: str
    content_pages: int
    phone: str
    email: str
    source_filename: str
    total_exported_pages: int
    cover_filename: str
    backcover_filename: str
    cover_url: Optional[str] = None
    storage_backend: str
    created_at: datetime


class BookDetailResponse(BookSummary):
    """Full book details and ordered JPG pages for /books/:id showcase viewer."""

    validation_summary: dict = Field(default_factory=dict)
    pages: List[BookPageDetail] = Field(default_factory=list)
    zip_download_url: str


class BookListResponse(BaseModel):
    """List response for Public Books Showcase."""

    books: List[BookSummary] = Field(default_factory=list)
    total: int

