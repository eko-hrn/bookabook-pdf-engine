"""Document management service.

Handles PDF upload validation, disk storage, page dimension extraction,
and metadata persistence.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import List, Optional
import uuid

from fastapi import HTTPException, UploadFile
import pymupdf as fitz

from app.api.config import Settings, get_settings
from app.api.schemas.documents import (
    DocumentMetadataResponse,
    DocumentUploadResponse,
    PageDimensionInfo,
)
from app.crop.models.enums import LayoutType, Orientation


def _detect_layout_type(width_pt: float, height_pt: float) -> Optional[str]:
    """Heuristic layout detection based on specification v1.3.4 dimensions."""
    # Check Cover Spread (landscape, width ~1220-1270 pt, height ~860-900 pt)
    if 1220.0 <= width_pt <= 1270.0 and 860.0 <= height_pt <= 900.0:
        return LayoutType.COVER_SPREAD.value
    # Check 4-Up Imposition (portrait, width ~860-900 pt, height ~1220-1270 pt)
    if 860.0 <= width_pt <= 900.0 and 1220.0 <= height_pt <= 1270.0:
        return LayoutType.IMPOSITION_4UP.value
    # Check Single Page (portrait, width ~415-450 pt, height ~590-640 pt)
    if 415.0 <= width_pt <= 450.0 and 590.0 <= height_pt <= 640.0:
        return LayoutType.SINGLE_PAGE.value
    return None


class DocumentService:
    """Service for managing uploaded PDF documents and metadata."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.settings.ensure_directories()

    async def save_uploaded_pdf(self, file: UploadFile) -> DocumentUploadResponse:
        """Validate and persist uploaded PDF file, generating metadata.

        Validations enforced:
        - Filename has .pdf extension
        - File is not empty
        - File does not exceed MAX_UPLOAD_SIZE_BYTES
        - Header begins with %PDF- (magic bytes check)
        - PyMuPDF can open and parse the document
        """
        filename = file.filename or "document.pdf"
        # Sanitize filename (preserve alphanumeric, dash, underscore, dot)
        clean_filename = re.sub(r"[^\w\s\.-]", "_", filename).strip()

        ext = Path(clean_filename).suffix.lower()
        if ext not in self.settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type '{ext}'. Only PDF files are accepted.",
            )

        # Read file contents with size limit enforcement
        content = await file.read()
        file_size = len(content)

        if file_size == 0:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty (0 bytes).",
            )

        if file_size > self.settings.MAX_UPLOAD_SIZE_BYTES:
            max_mb = self.settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum allowed limit of {max_mb} MB.",
            )

        # Inspect PDF magic bytes (%PDF- within initial 1024 bytes)
        initial_chunk = content[:1024]
        if b"%PDF-" not in initial_chunk:
            raise HTTPException(
                status_code=400,
                detail="Invalid PDF format: file lacks standard %PDF- header magic bytes.",
            )

        # Verify PyMuPDF can open the document
        try:
            doc = fitz.open(stream=content, filetype="pdf")
            page_count = doc.page_count
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Unable to parse PDF document structure: {str(exc)}",
            )

        if page_count < 1:
            doc.close()
            raise HTTPException(
                status_code=400,
                detail="PDF document contains 0 pages.",
            )

        # Extract per-page dimensions
        pages_info: List[PageDimensionInfo] = []
        for i in range(page_count):
            page = doc.load_page(i)
            rect = page.rect
            w = round(float(rect.width), 2)
            h = round(float(rect.height), 2)
            orientation = Orientation.LANDSCAPE.value if w > h else Orientation.PORTRAIT.value
            detected_layout = _detect_layout_type(w, h)
            pages_info.append(
                PageDimensionInfo(
                    page_number=i + 1,
                    width_pt=w,
                    height_pt=h,
                    orientation=orientation,
                    detected_layout=detected_layout,
                )
            )
        doc.close()

        # Generate unique document ID
        doc_id = f"doc_{uuid.uuid4().hex[:12]}"
        pdf_path = self.settings.UPLOAD_DIR / f"{doc_id}.pdf"
        meta_path = self.settings.UPLOAD_DIR / f"{doc_id}.json"

        # Persist PDF to disk
        pdf_path.write_bytes(content)

        # Persist metadata JSON
        now_utc = datetime.now(timezone.utc)
        meta_dict = {
            "document_id": doc_id,
            "filename": clean_filename,
            "file_size_bytes": file_size,
            "page_count": page_count,
            "created_at": now_utc.isoformat(),
            "status": "uploaded",
            "pages": [p.model_dump() for p in pages_info],
        }
        meta_path.write_text(json.dumps(meta_dict, indent=2), encoding="utf-8")

        return DocumentUploadResponse(
            document_id=doc_id,
            filename=clean_filename,
            file_size_bytes=file_size,
            page_count=page_count,
            created_at=now_utc,
            status="uploaded",
        )

    def get_document_metadata(self, document_id: str) -> Optional[DocumentMetadataResponse]:
        """Retrieve stored document metadata by ID, or None if not found."""
        meta_path = self.settings.UPLOAD_DIR / f"{document_id}.json"
        if not meta_path.is_file():
            return None

        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            pages = [PageDimensionInfo(**p) for p in data.get("pages", [])]
            return DocumentMetadataResponse(
                document_id=data["document_id"],
                filename=data["filename"],
                file_size_bytes=data["file_size_bytes"],
                page_count=data["page_count"],
                created_at=datetime.fromisoformat(data["created_at"]),
                status=data.get("status", "uploaded"),
                pages=pages,
            )
        except Exception:
            return None

    def get_pdf_path(self, document_id: str) -> Optional[Path]:
        """Return Path to stored PDF if it exists, or None."""
        pdf_path = self.settings.UPLOAD_DIR / f"{document_id}.pdf"
        return pdf_path if pdf_path.is_file() else None
