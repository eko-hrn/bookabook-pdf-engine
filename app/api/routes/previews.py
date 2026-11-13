"""Preview routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from app.api.dependencies import get_preview_service
from app.api.schemas.previews import DocumentPreviewResponse
from app.api.services.preview_service import PreviewService

router = APIRouter(prefix="/documents", tags=["Previews"])


@router.get(
    "/{document_id}/preview",
    response_model=DocumentPreviewResponse,
    summary="Get Structured Document Preview",
)
def get_document_preview(
    document_id: str,
    preview_service: PreviewService = Depends(get_preview_service),
) -> DocumentPreviewResponse:
    """Retrieve structured crop preview metadata and validation results for an uploaded document."""
    return preview_service.get_document_preview(document_id)


@router.get(
    "/{document_id}/pages/{page_number}/preview.png",
    summary="Get Page Preview Image",
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "PNG preview of the PDF page (composited with crop overlay by default)",
        }
    },
)
def get_page_preview_png(
    document_id: str,
    page_number: int,
    overlay: bool = Query(
        default=True,
        description="Whether to composite crop boundary overlays over the rendered PDF page",
    ),
    preview_service: PreviewService = Depends(get_preview_service),
) -> Response:
    """Render and return PNG image for a specific PDF page with optional crop overlays."""
    png_bytes = preview_service.render_page_preview_png(
        document_id,
        page_number,
        overlay=overlay,
    )
    return Response(content=png_bytes, media_type="image/png")


@router.get(
    "/{document_id}/pages/{page_number}/regions/{region_id}/preview.png",
    summary="Get Cropped Region Preview Image",
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "PNG preview of a single cropped region (page/cover/backcover)",
        }
    },
)
def get_region_preview_png(
    document_id: str,
    page_number: int,
    region_id: str,
    overlay: bool = Query(
        default=True,
        description="Whether to draw lightweight crop perimeter and label pill on the region image",
    ),
    preview_service: PreviewService = Depends(get_preview_service),
) -> Response:
    """Render and return PNG image for a specific crop region of a PDF page."""
    png_bytes = preview_service.render_region_preview_png(
        document_id,
        page_number,
        region_id,
        overlay=overlay,
    )
    return Response(content=png_bytes, media_type="image/png")

