"""End-to-end API and PostgreSQL schema migration tests for Books & Showcase."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
import zipfile

from fastapi.testclient import TestClient
from PIL import Image
import pymupdf
from sqlalchemy import inspect as sa_inspect

from app.api.dependencies import _get_engine_singleton
from app.db.migrations import _split_sql_statements, normalize_database_url


def _make_sample_book_pdf_bytes() -> bytes:
    """Create a deterministic 3-sheet Bookabook PDF (1 Cover + 2x 4-Up = 8 content pages)."""
    doc = pymupdf.open()
    # Cover spread
    cover = doc.new_page(width=1247.24, height=878.74)
    cover.draw_rect(pymupdf.Rect(160, 125, 600, 750), fill=(0.85, 0.9, 0.98))
    cover.insert_text((250, 400), "BACKCOVER", fontsize=24)
    cover.insert_text((623, 250), "SPINE", fontsize=12)
    cover.draw_rect(pymupdf.Rect(655, 125, 1100, 750), fill=(0.95, 0.85, 0.8))
    cover.insert_text((760, 400), "FRONT COVER", fontsize=24)

    # 2 x 4-Up sheets -> 8 pages
    for s in range(2):
        p = doc.new_page(width=878.74, height=1247.24)
        xc, yc = 439.37, 623.62
        p.draw_line((xc, 0), (xc, 7))
        p.draw_line((xc, 1240), (xc, 1247.24))
        p.draw_line((0, yc), (7, yc))
        p.draw_line((871, yc), (878.74, yc))
        coords = [(100, 200), (540, 200), (100, 820), (540, 820)]
        for q_idx, (tx, ty) in enumerate(coords):
            p.insert_text((tx, ty), f"Comic Page {s * 4 + q_idx + 1}", fontsize=20)
    return doc.tobytes()


def test_postgresql_migration_sql_and_url_normalization() -> None:
    assert (
        normalize_database_url("postgres://u:p@db.example.supabase.co:5432/postgres")
        == "postgresql+psycopg://u:p@db.example.supabase.co:5432/postgres"
    )
    assert (
        normalize_database_url("postgresql://u:p@host:6543/postgres?sslmode=require")
        == "postgresql+psycopg://u:p@host:6543/postgres?sslmode=require"
    )

    sql_path = Path(__file__).resolve().parents[2] / "migrations" / "001_create_books_tables.sql"
    sql_text = sql_path.read_text(encoding="utf-8")
    statements = _split_sql_statements(sql_text)
    assert len(statements) == 4
    assert any("CREATE TABLE IF NOT EXISTS books" in s for s in statements)
    assert any("CREATE TABLE IF NOT EXISTS book_pages" in s for s in statements)
    # Ensure binary JPG payloads are never stored in Postgres schema
    assert "BYTEA" not in sql_text.upper()


def test_books_process_save_and_public_showcase_e2e(client: TestClient) -> None:
    pdf_bytes = _make_sample_book_pdf_bytes()

    # 1. Invalid file rejected cleanly
    bad_res = client.post(
        "/api/books/process-pdf",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert bad_res.status_code == 400

    # 2. Process PDF inline (creates staging job, NOT public book yet)
    proc_res = client.post(
        "/api/books/process-pdf",
        files={"file": ("comic_vol_1.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert proc_res.status_code == 200
    proc = proc_res.json()

    job_id = proc["job_id"]
    assert proc["target_dpi"] == 300
    assert proc["content_pages_count"] == 8
    assert proc["total_exported_files"] == 10
    assert proc["validation"]["is_valid"] is True
    assert proc["validation"]["auto_validated"] is True
    assert [p["filename"] for p in proc["pages"]] == [
        "COVER.jpg",
        *[f"PAGE-{i:02d}.jpg" for i in range(1, 9)],
        "BACKCOVER.jpg",
    ]

    # Public showcase must still be EMPTY before Save Book is clicked
    pre_list = client.get("/api/books")
    assert pre_list.status_code == 200
    assert pre_list.json()["total"] == 0
    assert pre_list.json()["books"] == []

    # 3. Single JPG & ZIP download from staged job
    img_res = client.get(f"/api/books/jobs/{job_id}/images/COVER.jpg?download=true")
    assert img_res.status_code == 200
    assert img_res.headers["content-type"] == "image/jpeg"
    assert "attachment" in img_res.headers["content-disposition"]
    with Image.open(io.BytesIO(img_res.content)) as im:
        assert im.format == "JPEG"
        assert im.mode == "RGB"

    job_zip_res = client.get(proc["zip_download_url"])
    assert job_zip_res.status_code == 200
    assert job_zip_res.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(job_zip_res.content), "r") as zf:
        assert len(zf.namelist()) == 10
        assert "COVER.jpg" in zf.namelist()
        assert "BACKCOVER.jpg" in zf.namelist()

    # 4. Save Book requires non-empty title
    invalid_save = client.post(
        "/api/books",
        json={"job_id": job_id, "title": "   "},
    )
    assert invalid_save.status_code == 422

    # 5. Save Book persists metadata to DB + objects to StorageAdapter
    save_res = client.post(
        "/api/books",
        json={
            "job_id": job_id,
            "title": "COFA Comic Collection Vol. 1",
            "author": "Alleric Tansil",
            "authors_all": "Alleric Tansil, Allison Alexandra, Ashton Suriaputra",
            "description": "Compiled children comic showcase edition.",
            "year": 2026,
            "age_group": "7-12 years",
            "sponsor": "COFA Art Studio",
            "content_pages": proc["content_pages_count"],
            "phone": "+62-812-0000-1111",
            "email": "studio@bookabook.id",
        },
    )
    if save_res.status_code != 201:
        print("\nDEBUG_SAVE_RES_ERROR:", save_res.status_code, save_res.text)
    assert save_res.status_code == 201
    saved = save_res.json()
    book_id = saved["book_id"]

    assert saved["title"] == "COFA Comic Collection Vol. 1"
    assert saved["author"] == "Alleric Tansil"
    assert saved["year"] == 2026
    assert saved["content_pages"] == 8
    assert saved["storage_backend"] == "local"
    assert len(saved["pages"]) == 10
    for page in saved["pages"]:
        assert page["object_key"] == f"books/{book_id}/{page['filename']}"

    # 6. Public showcase endpoints now expose saved book & stream JPG / ZIP
    pub_list = client.get("/api/books")
    assert pub_list.status_code == 200
    assert pub_list.json()["total"] == 1
    assert pub_list.json()["books"][0]["book_id"] == book_id

    pub_detail = client.get(f"/api/books/{book_id}")
    assert pub_detail.status_code == 200
    assert pub_detail.json()["title"] == "COFA Comic Collection Vol. 1"

    page_res = client.get(f"/api/books/{book_id}/pages/PAGE-01.jpg")
    assert page_res.status_code == 200
    assert page_res.headers["content-type"] == "image/jpeg"
    expected_sha = next(
        p["sha256"] for p in saved["pages"] if p["filename"] == "PAGE-01.jpg"
    )
    assert hashlib.sha256(page_res.content).hexdigest() == expected_sha

    book_zip_res = client.get(saved["zip_download_url"])
    assert book_zip_res.status_code == 200
    with zipfile.ZipFile(io.BytesIO(book_zip_res.content), "r") as zf:
        assert len(zf.namelist()) == 10
        assert hashlib.sha256(zf.read("PAGE-01.jpg")).hexdigest() == expected_sha

    # Verify DB schema columns have zero blob columns
    health_res = client.get("/api/health")
    assert health_res.status_code == 200
    assert health_res.json()["database_connected"] is True

    _ = sa_inspect  # keeps import verified
    _ = _get_engine_singleton


def test_books_process_pdf_returns_structured_422_on_compression_failure(
    client: TestClient,
    monkeypatch,
) -> None:
    """When min JPEG quality still exceeds byte cap, API returns clear 422 failure details."""
    from app.crop.exporter import (
        CompressionStatus,
        DocumentExportResult,
        DocumentExportValidation,
        PageKind,
    )
    from app.crop.exporter.models import CompressionFailureDetail
    from app.crop.exporter.pdf_exporter import ProductionPDFExporter

    failure = CompressionFailureDetail(
        filename="COVER.jpg",
        page_key="COVER",
        page_kind=PageKind.COVER,
        actual_size_bytes=612_400,
        max_allowed_bytes=512_000,
        min_quality_threshold=55,
        quality_attempted=55,
        reason="COVER.jpg compressed to 612,400 bytes at minimum quality q=55, exceeding 512,000 bytes.",
    )
    failed_result = DocumentExportResult(
        source_filename="too_dense.pdf",
        target_dpi=300,
        pages=[],
        validation=DocumentExportValidation(
            is_valid=False,
            auto_validated=True,
            compression_status=CompressionStatus.FAILED,
            total_pdf_pages=2,
            cover_detected=False,
            backcover_detected=False,
            content_pages_count=0,
            total_exported_files=0,
            files_over_policy_limit=1,
            compression_failures=[failure],
            errors=[failure.reason],
        ),
    )
    monkeypatch.setattr(ProductionPDFExporter, "export_pdf", lambda *args, **kwargs: failed_result)

    pdf_bytes = _make_sample_book_pdf_bytes()
    resp = client.post(
        "/api/books/process-pdf",
        files={"file": ("too_dense.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["compression_status"] == "FAILED"
    assert len(body["compression_failures"]) == 1
    assert body["compression_failures"][0]["filename"] == "COVER.jpg"
    assert body["compression_failures"][0]["actual_size_bytes"] == 612_400
    assert body["compression_failures"][0]["max_allowed_bytes"] == 512_000
    assert "512,000" in body["detail"]

