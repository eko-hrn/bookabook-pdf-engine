"""Document management API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class PageDimensionInfo(BaseModel):
    """Metadata and dimensions for a single PDF page."""

    page_number: int = Field(..., description="1-based page number")
    width_pt: float = Field(..., description="Width in PDF points")
    height_pt: float = Field(..., description="Height in PDF points")
    orientation: str = Field(..., description="Orientation: PORTRAIT or LANDSCAPE")
    detected_layout: Optional[str] = Field(None, description="Detected layout type if classified")


class DocumentUploadResponse(BaseModel):
    """Response returned upon successful PDF upload."""

    document_id: str = Field(..., description="Unique generated document identifier")
    filename: str = Field(..., description="Sanitized original filename")
    file_size_bytes: int = Field(..., description="File size in bytes")
    page_count: int = Field(..., description="Total number of pages in the PDF")
    created_at: datetime = Field(..., description="UTC creation timestamp")
    status: str = Field("uploaded", description="Processing status of the document")


class DocumentMetadataResponse(BaseModel):
    """Complete document metadata response."""

    document_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Sanitized original filename")
    file_size_bytes: int = Field(..., description="File size in bytes")
    page_count: int = Field(..., description="Total number of pages in the PDF")
    created_at: datetime = Field(..., description="UTC creation timestamp")
    status: str = Field(..., description="Processing status of the document")
    pages: List[PageDimensionInfo] = Field(default_factory=list, description="Per-page dimension details")

