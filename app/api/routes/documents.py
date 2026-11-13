"""Document management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.dependencies import get_document_service
from app.api.schemas.documents import (
    DocumentMetadataResponse,
    DocumentUploadResponse,
)
from app.api.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=201,
    summary="Upload PDF Document",
)
async def upload_document(
    file: UploadFile = File(..., description="PDF file to upload"),
    doc_service: DocumentService = Depends(get_document_service),
) -> DocumentUploadResponse:
    """Upload a PDF file, validate headers, compute page dimensions, and store on disk."""
    return await doc_service.save_uploaded_pdf(file)


@router.get(
    "/{document_id}",
    response_model=DocumentMetadataResponse,
    summary="Get Document Metadata",
)
def get_document(
    document_id: str,
    doc_service: DocumentService = Depends(get_document_service),
) -> DocumentMetadataResponse:
    """Retrieve metadata and sheet dimensions for an uploaded document."""
    meta = doc_service.get_document_metadata(document_id)
    if meta is None:
        raise HTTPException(
            status_code=404,
            detail=f"Document with ID '{document_id}' was not found.",
        )
    return meta

