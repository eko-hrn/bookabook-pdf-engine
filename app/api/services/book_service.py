"""Service orchestrating PDF -> 300 DPI JPG processing, staging, and book publication."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import re
import shutil
from typing import Optional
import uuid

from fastapi import HTTPException, UploadFile
import pymupdf

from app.api.config import Settings
from app.api.schemas.books import (
    BookDetailResponse,
    BookListResponse,
    BookPageDetail,
    BookSummary,
    ExportValidationSummary,
    ProcessedPageItem,
    ProcessPdfResponse,
    SaveBookRequest,
)
from app.crop.exporter import ProductionPDFExporter, build_export_zip_bytes
from app.db.repository import BookRepository, StoredBookPageRecord, StoredBookRecord
from app.storage.base import StorageAdapter
from app.storage.local import LocalStorageAdapter


def _safe_slug(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip()).strip("_")
    return cleaned[:60] or "bookabook_book"


def _validate_safe_filename(filename: str) -> str:
    clean = Path(filename).name
    if clean != filename or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")
    if not clean.lower().endswith(".jpg"):
        raise HTTPException(status_code=400, detail="Only .jpg filenames are permitted.")
    return clean


class BookProcessingValidationError(Exception):
    """Raised when PDF layout or compression policy fails validation."""

    def __init__(
        self,
        *,
        message: str,
        compression_status: str,
        errors: list[str],
        compression_failures: list[dict],
    ) -> None:
        super().__init__(message)
        self.message = message
        self.compression_status = compression_status
        self.errors = errors
        self.compression_failures = compression_failures


class BookProcessingService:
    """Handles unified PDF processing, local/R2 JPG storage, and Supabase metadata."""

    def __init__(
        self,
        *,
        settings: Settings,
        storage: StorageAdapter,
        repository: BookRepository,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.local_storage = LocalStorageAdapter(self.settings.LOCAL_STORAGE_DIR)
        self.repository = repository
        self.staging_root = self.settings.LOCAL_STORAGE_DIR / "_staging_jobs"
        self.staging_root.mkdir(parents=True, exist_ok=True)
        self.exporter = ProductionPDFExporter(
            target_dpi=settings.PRODUCTION_EXPORT_DPI,
            cover_max_bytes=settings.COVER_MAX_BYTES,
            inside_page_max_bytes=settings.INSIDE_PAGE_MAX_BYTES,
            backcover_max_bytes=settings.BACKCOVER_MAX_BYTES,
            min_quality_cover=settings.MIN_JPEG_QUALITY_COVER,
            min_quality_inside=settings.MIN_JPEG_QUALITY_INSIDE,
            min_quality_backcover=settings.MIN_JPEG_QUALITY_BACKCOVER,
            initial_quality=settings.INITIAL_JPEG_QUALITY,
        )

    def _job_dir(self, job_id: str) -> Path:
        if not re.fullmatch(r"job_[a-f0-9]{12}", job_id):
            raise HTTPException(status_code=400, detail="Invalid job identifier.")
        root = self.staging_root.resolve()
        job_dir = (root / job_id).resolve()
        try:
            job_dir.relative_to(root)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid job directory.")
        return job_dir

    async def process_uploaded_pdf(self, file: UploadFile) -> ProcessPdfResponse:
        """Validate uploaded PDF and export 300 DPI RGB JPEGs to staging (not yet public)."""
        raw_name = file.filename or "book.pdf"
        clean_filename = re.sub(r"[^\w\s\.-]", "_", raw_name).strip() or "book.pdf"
        if Path(clean_filename).suffix.lower() not in self.settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only .pdf files are accepted.",
            )

        temp_upload_path = self.staging_root / f"temp_{uuid.uuid4().hex}.pdf"
        total_bytes = 0
        header_check = b""
        try:
            with temp_upload_path.open("wb") as out_f:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    if not header_check:
                        header_check = chunk[:1024]
                    total_bytes += len(chunk)
                    if total_bytes > self.settings.MAX_UPLOAD_SIZE_BYTES:
                        max_mb = self.settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
                        raise HTTPException(
                            status_code=413,
                            detail=f"File exceeds maximum upload size limit of {max_mb} MB.",
                        )
                    out_f.write(chunk)

            if total_bytes == 0:
                raise HTTPException(status_code=400, detail="Uploaded PDF file is empty (0 bytes).")
            if b"%PDF-" not in header_check:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid PDF format: missing %PDF- header.",
                )

            try:
                doc = pymupdf.open(str(temp_upload_path))
                if doc.page_count < 1:
                    doc.close()
                    raise HTTPException(status_code=400, detail="PDF contains 0 pages.")
                doc.close()
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unable to open PDF document: {exc}",
                ) from exc

            export_res = self.exporter.export_pdf(temp_upload_path, source_filename=clean_filename)
        finally:
            if temp_upload_path.exists():
                try:
                    temp_upload_path.unlink()
                except OSError:
                    pass

        if not export_res.validation.is_valid:
            failure_dicts = [f.model_dump() for f in export_res.validation.compression_failures]
            message = "; ".join(export_res.validation.errors) or (
                "PDF layout or JPEG compression failed automated validation."
            )
            raise BookProcessingValidationError(
                message=message,
                compression_status=export_res.validation.compression_status.value,
                errors=list(export_res.validation.errors),
                compression_failures=failure_dicts,
            )

        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job_dir = self.staging_root / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        pages_meta: list[ProcessedPageItem] = []
        manifest_pages: list[dict] = []

        for artifact in export_res.pages:
            if artifact.image_bytes is None:
                continue
            (job_dir / artifact.filename).write_bytes(artifact.image_bytes)
            preview_url = f"/api/books/jobs/{job_id}/images/{artifact.filename}"
            download_url = f"/api/books/jobs/{job_id}/images/{artifact.filename}?download=true"
            item = ProcessedPageItem(
                page_key=artifact.page_key,
                filename=artifact.filename,
                page_kind=artifact.page_kind.value,
                order_index=artifact.order_index,
                source_pdf_page=artifact.source_pdf_page,
                quadrant=artifact.quadrant,
                width_px=artifact.width_px,
                height_px=artifact.height_px,
                dpi=artifact.dpi,
                file_size_bytes=artifact.file_size_bytes,
                max_allowed_bytes=artifact.max_allowed_bytes,
                quality_used=artifact.quality_used,
                subsampling_used=artifact.subsampling_used,
                compression_tier=artifact.compression_tier.value,
                compression_status=artifact.compression_status.value,
                is_blank=artifact.is_blank,
                sha256=artifact.sha256,
                preview_url=preview_url,
                download_url=download_url,
            )
            pages_meta.append(item)
            manifest_pages.append(item.model_dump())

        validation_summary = ExportValidationSummary(**export_res.validation.model_dump())
        manifest = {
            "job_id": job_id,
            "source_filename": clean_filename,
            "target_dpi": export_res.target_dpi,
            "content_pages_count": validation_summary.content_pages_count,
            "total_exported_files": validation_summary.total_exported_files,
            "validation": validation_summary.model_dump(),
            "pages": manifest_pages,
        }
        (job_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        return ProcessPdfResponse(
            job_id=job_id,
            source_filename=clean_filename,
            target_dpi=export_res.target_dpi,
            content_pages_count=validation_summary.content_pages_count,
            total_exported_files=validation_summary.total_exported_files,
            validation=validation_summary,
            pages=pages_meta,
            zip_download_url=f"/api/books/jobs/{job_id}/download.zip",
        )

    def _load_job_manifest(self, job_id: str) -> tuple[Path, dict]:
        job_dir = self._job_dir(job_id)
        manifest_path = job_dir / "manifest.json"
        if not manifest_path.is_file():
            raise HTTPException(
                status_code=404,
                detail=f"Processed PDF job '{job_id}' was not found or expired.",
            )
        return job_dir, json.loads(manifest_path.read_text(encoding="utf-8"))

    def get_job_image_bytes(self, job_id: str, filename: str) -> bytes:
        clean_name = _validate_safe_filename(filename)
        job_dir, _manifest = self._load_job_manifest(job_id)
        file_path = (job_dir / clean_name).resolve()
        if job_dir.resolve() not in file_path.parents or not file_path.is_file():
            raise HTTPException(status_code=404, detail=f"Image '{clean_name}' not found in job.")
        return file_path.read_bytes()

    def build_job_zip(self, job_id: str) -> tuple[bytes, str]:
        job_dir, manifest = self._load_job_manifest(job_id)
        files: list[tuple[str, bytes]] = []
        for p in sorted(manifest["pages"], key=lambda item: int(item["order_index"])):
            fname = p["filename"]
            fpath = job_dir / fname
            if fpath.is_file():
                files.append((fname, fpath.read_bytes()))
        if not files:
            raise HTTPException(status_code=404, detail="No exported images found for job.")
        zip_bytes = build_export_zip_bytes(files)
        slug = _safe_slug(Path(manifest["source_filename"]).stem)
        return zip_bytes, f"{slug}_cropped_pages.zip"

    def save_book(self, payload: SaveBookRequest) -> BookDetailResponse:
        """Promote staged JPG outputs into StorageAdapter and persist book metadata in DB."""
        job_dir, manifest = self._load_job_manifest(payload.job_id)
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=422, detail="Title is required to save a book.")

        book_id = f"book_{uuid.uuid4().hex[:12]}"
        uploaded_keys: list[str] = []
        db_pages: list[dict] = []

        def _upload_page(p: dict) -> tuple[str, dict]:
            fname = p["filename"]
            fpath = job_dir / fname
            if not fpath.is_file():
                raise HTTPException(
                    status_code=500,
                    detail=f"Staged image '{fname}' missing before save.",
                )
            object_key = f"books/{book_id}/{fname}"
            stored_key = self.storage.put_bytes(
                object_key,
                fpath.read_bytes(),
                content_type="image/jpeg",
            )
            page_meta = {
                "page_key": p["page_key"],
                "filename": fname,
                "page_kind": p["page_kind"],
                "order_index": p["order_index"],
                "source_pdf_page": p["source_pdf_page"],
                "quadrant": p.get("quadrant"),
                "width_px": p["width_px"],
                "height_px": p["height_px"],
                "dpi": p["dpi"],
                "file_size_bytes": p["file_size_bytes"],
                "quality_used": p["quality_used"],
                "subsampling_used": p["subsampling_used"],
                "compression_tier": p["compression_tier"],
                "sha256": p["sha256"],
                "object_key": stored_key,
                "is_blank": p.get("is_blank", False),
            }
            return stored_key, page_meta

        try:
            with ThreadPoolExecutor(max_workers=8) as executor:
                future_to_page = {
                    executor.submit(_upload_page, p): p for p in manifest["pages"]
                }
                for future in as_completed(future_to_page):
                    stored_key, page_meta = future.result()
                    uploaded_keys.append(stored_key)
                    db_pages.append(page_meta)

            # Sort pages strictly by order_index to preserve authoritative sequential order
            db_pages.sort(key=lambda item: int(item["order_index"]))

            cover_page = next((p for p in db_pages if p["page_kind"] == "COVER"), db_pages[0])
            backcover_page = next(
                (p for p in db_pages if p["page_kind"] == "BACKCOVER"),
                db_pages[-1],
            )
            content_count = (
                payload.content_pages
                if payload.content_pages is not None
                else int(manifest["content_pages_count"])
            )

            stored_book = self.repository.create_book_with_pages(
                book_id=book_id,
                title=title,
                author=payload.author.strip(),
                authors_all=payload.authors_all.strip(),
                description=payload.description.strip(),
                year=payload.year,
                age_group=payload.age_group.strip(),
                sponsor=payload.sponsor.strip(),
                content_pages=content_count,
                phone=payload.phone.strip(),
                email=payload.email.strip(),
                source_filename=manifest["source_filename"],
                total_exported_pages=len(db_pages),
                cover_filename=cover_page["filename"],
                backcover_filename=backcover_page["filename"],
                storage_backend=self.storage.backend_name,
                validation_summary=manifest["validation"],
                pages=db_pages,
            )
        except Exception:
            for key in uploaded_keys:
                try:
                    self.storage.delete(key)
                except Exception:
                    pass
            raise

        # Clean up staging folder now that images are safely persisted in storage
        shutil.rmtree(job_dir, ignore_errors=True)
        return self._to_detail_response(stored_book)

    def list_books(self, limit: int = 50, offset: int = 0) -> BookListResponse:
        records = self.repository.list_books(limit=limit, offset=offset)
        return BookListResponse(
            books=[self._to_summary(rec) for rec in records],
            total=len(records),
        )

    def get_book_detail(self, book_id: str) -> BookDetailResponse:
        rec = self.repository.get_book(book_id)
        if rec is None:
            raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found.")
        return self._to_detail_response(rec)

    def _storage_for_record(self, rec: StoredBookRecord) -> StorageAdapter:
        """Route to LocalStorageAdapter if a previously saved record used local storage."""
        if rec.storage_backend == "local" and self.storage.backend_name != "local":
            return self.local_storage
        return self.storage

    def get_saved_page_bytes(self, book_id: str, filename: str) -> bytes:
        clean_name = _validate_safe_filename(filename)
        rec = self.repository.get_book(book_id)
        if rec is None:
            raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found.")
        page = next((p for p in rec.pages if p.filename == clean_name), None)
        if page is None:
            raise HTTPException(
                status_code=404,
                detail=f"Page '{clean_name}' not found for book '{book_id}'.",
            )
        storage = self._storage_for_record(rec)
        try:
            return storage.get_bytes(page.object_key)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail=f"Stored image object missing for '{clean_name}'.",
            ) from exc

    def build_saved_book_zip(self, book_id: str) -> tuple[bytes, str]:
        rec = self.repository.get_book(book_id)
        if rec is None:
            raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found.")
        storage = self._storage_for_record(rec)
        files: list[tuple[str, bytes]] = []
        for page in sorted(rec.pages, key=lambda p: p.order_index):
            files.append((page.filename, storage.get_bytes(page.object_key)))
        if not files:
            raise HTTPException(status_code=404, detail="Book has no stored pages.")
        slug = _safe_slug(rec.title)
        return build_export_zip_bytes(files), f"{slug}_{rec.book_id}.zip"

    def _page_urls(self, rec: StoredBookRecord, page: StoredBookPageRecord) -> tuple[str, str]:
        storage = self._storage_for_record(rec)
        external = storage.get_public_or_signed_url(page.object_key)
        api_preview = f"/api/books/{rec.book_id}/pages/{page.filename}"
        api_download = f"/api/books/{rec.book_id}/pages/{page.filename}?download=true"
        # Direct public URL for Supabase/CDN storage, or proxy fallback for local
        preview_url = external if external else api_preview
        download_url = external if external else api_download
        return preview_url, download_url

    def _to_summary(self, rec: StoredBookRecord) -> BookSummary:
        cover_page = next((p for p in rec.pages if p.filename == rec.cover_filename), None)
        if cover_page is None and rec.pages:
            cover_page = rec.pages[0]
        cover_url = self._page_urls(rec, cover_page)[0] if cover_page else None
        return BookSummary(
            book_id=rec.book_id,
            title=rec.title,
            author=rec.author,
            authors_all=rec.authors_all,
            description=rec.description,
            year=rec.year,
            age_group=rec.age_group,
            sponsor=rec.sponsor,
            content_pages=rec.content_pages,
            phone=rec.phone,
            email=rec.email,
            source_filename=rec.source_filename,
            total_exported_pages=rec.total_exported_pages,
            cover_filename=rec.cover_filename,
            backcover_filename=rec.backcover_filename,
            cover_url=cover_url,
            storage_backend=rec.storage_backend,
            created_at=rec.created_at,
        )

    def _to_detail_response(self, rec: StoredBookRecord) -> BookDetailResponse:
        summary = self._to_summary(rec)
        pages = [
            BookPageDetail(
                page_key=p.page_key,
                filename=p.filename,
                page_kind=p.page_kind,
                order_index=p.order_index,
                source_pdf_page=p.source_pdf_page,
                quadrant=p.quadrant,
                width_px=p.width_px,
                height_px=p.height_px,
                dpi=p.dpi,
                file_size_bytes=p.file_size_bytes,
                quality_used=p.quality_used,
                subsampling_used=p.subsampling_used,
                compression_tier=p.compression_tier,
                sha256=p.sha256,
                object_key=p.object_key,
                is_blank=p.is_blank,
                preview_url=self._page_urls(rec, p)[0],
                download_url=self._page_urls(rec, p)[1],
            )
            for p in sorted(rec.pages, key=lambda item: item.order_index)
        ]
        return BookDetailResponse(
            **summary.model_dump(),
            validation_summary=rec.validation_summary,
            pages=pages,
            zip_download_url=f"/api/books/{rec.book_id}/download.zip",
        )

