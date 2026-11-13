"""Book processing (PDF -> 300 DPI JPGs) and Public Showcase API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status

from app.api.dependencies import get_book_service
from app.api.schemas.books import (
    BookDetailResponse,
    BookListResponse,
    ProcessPdfResponse,
    SaveBookRequest,
)
from app.api.services.book_service import BookProcessingService

router = APIRouter(prefix="/books", tags=["Books"])


@router.post(
    "/process-pdf",
    response_model=ProcessPdfResponse,
    status_code=status.HTTP_200_OK,
    summary="Process PDF into 300 DPI Cropped JPEGs",
)
async def process_pdf(
    file: UploadFile = File(..., description="Uploaded PDF file"),
    book_service: BookProcessingService = Depends(get_book_service),
) -> ProcessPdfResponse:
    """Validate and crop an uploaded PDF into COVER, PAGE-01..N, and BACKCOVER 300 DPI JPGs."""
    return await book_service.process_uploaded_pdf(file)


@router.get(
    "/jobs/{job_id}/images/{filename}",
    summary="Fetch Staged Cropped JPEG",
    responses={200: {"content": {"image/jpeg": {}}}},
)
def get_job_image(
    job_id: str,
    filename: str,
    download: bool = Query(default=False, description="Force attachment download header"),
    book_service: BookProcessingService = Depends(get_book_service),
) -> Response:
    """Stream one cropped 300 DPI JPEG from an active staging job."""
    jpeg_bytes = book_service.get_job_image_bytes(job_id, filename)
    disposition = f'attachment; filename="{filename}"' if download else f'inline; filename="{filename}"'
    return Response(
        content=jpeg_bytes,
        media_type="image/jpeg",
        headers={"Content-Disposition": disposition},
    )


@router.get(
    "/jobs/{job_id}/download.zip",
    summary="Download All Cropped JPEGs as ZIP",
    responses={200: {"content": {"application/zip": {}}}},
)
def download_job_zip(
    job_id: str,
    book_service: BookProcessingService = Depends(get_book_service),
) -> Response:
    """Download all cropped JPEGs for a processed job as a ZIP archive."""
    zip_bytes, zip_filename = book_service.build_job_zip(job_id)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )


@router.post(
    "",
    response_model=BookDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save Book and Publish to Showcase",
)
def save_book(
    payload: SaveBookRequest,
    book_service: BookProcessingService = Depends(get_book_service),
) -> BookDetailResponse:
    """Persist book metadata in PostgreSQL and promote JPGs into StorageAdapter."""
    return book_service.save_book(payload)


@router.get(
    "",
    response_model=BookListResponse,
    summary="List Published Books for Public Showcase",
)
def list_books(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    book_service: BookProcessingService = Depends(get_book_service),
) -> BookListResponse:
    """Return saved books ordered newest first for /books public showcase."""
    return book_service.list_books(limit=limit, offset=offset)


@router.get(
    "/{book_id}",
    response_model=BookDetailResponse,
    summary="Get Published Book Details and Pages",
)
def get_book_detail(
    book_id: str,
    book_service: BookProcessingService = Depends(get_book_service),
) -> BookDetailResponse:
    """Return saved book metadata and ordered JPG URLs for /books/:id showcase."""
    return book_service.get_book_detail(book_id)


@router.get(
    "/{book_id}/pages/{filename}",
    summary="Fetch Saved Book Page JPEG",
    responses={200: {"content": {"image/jpeg": {}}}},
)
def get_saved_book_page(
    book_id: str,
    filename: str,
    download: bool = Query(default=False, description="Force attachment download header"),
    book_service: BookProcessingService = Depends(get_book_service),
) -> Response:
    """Stream a persisted book page JPG from configured object storage."""
    jpeg_bytes = book_service.get_saved_page_bytes(book_id, filename)
    disposition = f'attachment; filename="{filename}"' if download else f'inline; filename="{filename}"'
    return Response(
        content=jpeg_bytes,
        media_type="image/jpeg",
        headers={"Content-Disposition": disposition},
    )


@router.get(
    "/{book_id}/download.zip",
    summary="Download Saved Book Archive (ZIP)",
    responses={200: {"content": {"application/zip": {}}}},
)
def download_saved_book_zip(
    book_id: str,
    book_service: BookProcessingService = Depends(get_book_service),
) -> Response:
    """Download all persisted 300 DPI JPG pages of a saved book as ZIP."""
    zip_bytes, zip_filename = book_service.build_saved_book_zip(book_id)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )

