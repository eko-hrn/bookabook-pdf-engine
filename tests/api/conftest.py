"""Test fixtures for FastAPI API endpoints."""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Generator

from fastapi.testclient import TestClient
import pymupdf
import pytest

from app.api.config import Settings
from app.api.dependencies import (
    get_app_settings,
    get_document_service,
    get_preview_service,
    get_review_workflow,
)
from app.api.main import app
from app.api.services.document_service import DocumentService
from app.api.services.preview_service import PreviewService
from app.crop.review.workflow import PreviewReviewWorkflow


@pytest.fixture
def temp_api_dir() -> Generator[Path, None, None]:
    """Temporary storage directory for tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def test_settings(temp_api_dir: Path) -> Settings:
    """Settings configured to use temporary storage directories."""
    settings = Settings(
        DATA_DIR=temp_api_dir / "data",
        UPLOAD_DIR=temp_api_dir / "data" / "uploads",
        PREVIEW_DIR=temp_api_dir / "data" / "previews",
        DB_PATH=temp_api_dir / "data" / "test_review.db",
        DATABASE_URL=None,
        STORAGE_BACKEND="local",
        LOCAL_STORAGE_DIR=temp_api_dir / "data" / "storage",
        MAX_UPLOAD_SIZE_BYTES=5 * 1024 * 1024,  # 5 MB for tests
        PREVIEW_DPI=72,  # Faster 72 DPI for tests
    )
    settings.ensure_directories()
    return settings


@pytest.fixture
def client(test_settings: Settings) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with dependency overrides pointing to test storage."""
    doc_service = DocumentService(settings=test_settings)
    preview_service = PreviewService(document_service=doc_service, settings=test_settings)
    workflow = PreviewReviewWorkflow(db_path=test_settings.DB_PATH)

    app.dependency_overrides[get_app_settings] = lambda: test_settings
    app.dependency_overrides[get_document_service] = lambda: doc_service
    app.dependency_overrides[get_preview_service] = lambda: preview_service
    app.dependency_overrides[get_review_workflow] = lambda: workflow

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def sample_6page_pdf_bytes() -> bytes:
    """Generate in-memory 6-page PDF (Sheet 1 Cover, Sheets 2-6 4-Up Imposition)."""
    doc = pymupdf.open()
    # Sheet 1: Cover Spread (Landscape nominal ~1247.24 x 878.74 pt)
    cover_page = doc.new_page(width=1247.24, height=878.74)
    cover_page.draw_rect(pymupdf.Rect(50, 50, 1197.24, 828.74), color=(0, 0, 1), width=1)

    # Sheets 2-6: 4-Up Imposition Grid (Portrait nominal ~878.74 x 1247.24 pt)
    for _ in range(5):
        page = doc.new_page(width=878.74, height=1247.24)
        page.draw_rect(pymupdf.Rect(50, 50, 828.74, 1197.24), color=(1, 0, 0), width=1)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
def sample_single_page_pdf_bytes() -> bytes:
    """Generate in-memory single-page PDF (Portrait 425.52 x 609.12 pt)."""
    doc = pymupdf.open()
    page = doc.new_page(width=425.52, height=609.12)
    page.draw_rect(pymupdf.Rect(20, 20, 405.52, 589.12), color=(0, 1, 0), width=1)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
def sample_unknown_layout_pdf_bytes() -> bytes:
    """Generate in-memory PDF with unrecognized non-standard dimensions."""
    doc = pymupdf.open()
    page = doc.new_page(width=300.0, height=300.0)
    page.draw_rect(pymupdf.Rect(10, 10, 290.0, 290.0), color=(0.5, 0.5, 0.5), width=1)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
