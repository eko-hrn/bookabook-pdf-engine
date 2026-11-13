"""Structured validation report models for Crop Plan Validator (Phase 1.2.2.3).

Provides structured, hierarchical validation reports for pages and documents
integrating with the existing CropValidationResult model.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.crop.models.crop_validation import CropValidationResult
from app.crop.models.document_crop_plan import DocumentStatus
from app.crop.models.enums import CropReadinessStatus, LayoutType


class PageValidationReport(BaseModel):
    """Validation report for a single PageCropPlan.

    Aggregates region-level results and captures page-level rule compliance.
    """

    pdf_page_index: int = Field(
        ..., ge=0,
        description="Zero-based PDF page index",
    )
    pdf_page_number: int = Field(
        ..., ge=1,
        description="One-based PDF page number",
    )
    layout_type: Optional[LayoutType] = Field(
        default=None,
        description="Layout type of the page being validated",
    )
    crop_readiness: CropReadinessStatus = Field(
        ...,
        description="Assigned crop execution readiness status",
    )
    is_valid: bool = Field(
        ...,
        description="True if all page and region validation checks passed without errors",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Blocking validation errors on this page",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Informative non-blocking warnings on this page",
    )
    region_results: list[CropValidationResult] = Field(
        default_factory=list,
        description="Individual validation results for each crop region",
    )

    @property
    def has_errors(self) -> bool:
        """True if there are any errors on the page or in its regions."""
        return len(self.errors) > 0 or any(not r.is_valid for r in self.region_results)

    def to_summary_dict(self) -> dict:
        """Return a compact JSON-serializable dictionary summary."""
        return {
            "pdf_page_index": self.pdf_page_index,
            "pdf_page_number": self.pdf_page_number,
            "layout_type": self.layout_type.value if self.layout_type else None,
            "crop_readiness": self.crop_readiness.value if self.crop_readiness else None,
            "is_valid": self.is_valid,
            "errors_count": len(self.errors),
            "warnings_count": len(self.warnings),
            "regions_count": len(self.region_results),
            "valid_regions_count": sum(1 for r in self.region_results if r.is_valid),
        }


class DocumentValidationReport(BaseModel):
    """Validation report for a complete DocumentCropPlan.

    Verifies document-level integrity, page sequence consistency, total yield,
    and status aggregation across all sheets.
    """

    source_filename: str = Field(
        ...,
        min_length=1,
        description="Source PDF filename",
    )
    total_pdf_pages: int = Field(
        ..., ge=0,
        description="Total PDF pages inspected",
    )
    expected_total_book_pages: int = Field(
        ..., ge=0,
        description="Expected total book page yield",
    )
    document_status: DocumentStatus = Field(
        ...,
        description="Aggregated document status model",
    )
    is_valid: bool = Field(
        ...,
        description="True if document integrity and all pages are valid without errors",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Document-level blocking errors",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Document-level non-blocking warnings",
    )
    page_reports: list[PageValidationReport] = Field(
        default_factory=list,
        description="Validation reports for each page in the document",
    )
    total_regions: int = Field(
        default=0, ge=0,
        description="Total crop regions across all pages",
    )
    valid_regions_count: int = Field(
        default=0, ge=0,
        description="Number of regions that passed validation",
    )
    invalid_regions_count: int = Field(
        default=0, ge=0,
        description="Number of regions that failed validation",
    )

    def to_summary_dict(self) -> dict:
        """Return a compact JSON-serializable dictionary summary."""
        return {
            "source_filename": self.source_filename,
            "total_pdf_pages": self.total_pdf_pages,
            "expected_total_book_pages": self.expected_total_book_pages,
            "document_status": self.document_status.document_status,
            "is_valid": self.is_valid,
            "errors_count": len(self.errors),
            "warnings_count": len(self.warnings),
            "total_regions": self.total_regions,
            "valid_regions_count": self.valid_regions_count,
            "invalid_regions_count": self.invalid_regions_count,
            "failed_pages_count": sum(1 for p in self.page_reports if not p.is_valid),
        }
