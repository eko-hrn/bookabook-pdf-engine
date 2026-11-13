"""Tests for Document upload and metadata endpoints."""

from __future__ import annotations

import io
from fastapi.testclient import TestClient


def test_upload_valid_6page_pdf(client: TestClient, sample_6page_pdf_bytes: bytes) -> None:
    """Verify uploading a valid 6-page Bookabook PDF succeeds with 201."""
    files = {
        "file": ("test_book_sample.pdf", io.BytesIO(sample_6page_pdf_bytes), "application/pdf")
    }
    response = client.post("/api/documents/upload", files=files)
    assert response.status_code == 201
    data = response.json()
    assert data["document_id"].startswith("doc_")
    assert data["filename"] == "test_book_sample.pdf"
    assert data["page_count"] == 6
    assert data["file_size_bytes"] == len(sample_6page_pdf_bytes)
    assert data["status"] == "uploaded"
    assert "created_at" in data


def test_get_document_metadata(client: TestClient, sample_6page_pdf_bytes: bytes) -> None:
    """Verify retrieving metadata for an uploaded document."""
    files = {
        "file": ("sample.pdf", io.BytesIO(sample_6page_pdf_bytes), "application/pdf")
    }
    upload_res = client.post("/api/documents/upload", files=files)
    doc_id = upload_res.json()["document_id"]

    res = client.get(f"/api/documents/{doc_id}")
    assert res.status_code == 200
    meta = res.json()
    assert meta["document_id"] == doc_id
    assert meta["page_count"] == 6
    assert len(meta["pages"]) == 6

    # Sheet 1: Cover Spread
    p1 = meta["pages"][0]
    assert p1["page_number"] == 1
    assert p1["width_pt"] == 1247.24
    assert p1["height_pt"] == 878.74
    assert p1["orientation"] == "LANDSCAPE"
    assert p1["detected_layout"] == "COVER_SPREAD"

    # Sheets 2-6: 4-Up Imposition
    for i in range(1, 6):
        pi = meta["pages"][i]
        assert pi["page_number"] == i + 1
        assert pi["width_pt"] == 878.74
        assert pi["height_pt"] == 1247.24
        assert pi["orientation"] == "PORTRAIT"
        assert pi["detected_layout"] == "IMPOSITION_4UP"


def test_get_nonexistent_document_metadata(client: TestClient) -> None:
    """Verify requesting a non-existent document returns 404."""
    res = client.get("/api/documents/doc_doesnotexist")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_upload_empty_file_fails(client: TestClient) -> None:
    """Verify uploading an empty 0-byte file is rejected with 400."""
    files = {"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}
    res = client.post("/api/documents/upload", files=files)
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()


def test_upload_non_pdf_extension_fails(client: TestClient) -> None:
    """Verify uploading a file without .pdf extension is rejected with 400."""
    files = {"file": ("test.txt", io.BytesIO(b"Hello text file"), "text/plain")}
    res = client.post("/api/documents/upload", files=files)
    assert res.status_code == 400
    assert "only pdf" in res.json()["detail"].lower()


def test_upload_corrupt_header_pdf_fails(client: TestClient) -> None:
    """Verify uploading a .pdf without %PDF- magic bytes header is rejected with 400."""
    files = {"file": ("fake.pdf", io.BytesIO(b"NOT A REAL PDF CONTENT"), "application/pdf")}
    res = client.post("/api/documents/upload", files=files)
    assert res.status_code == 400
    assert "%pdf-" in res.json()["detail"].lower()


def test_upload_oversized_file_fails(client: TestClient) -> None:
    """Verify uploading a file exceeding MAX_UPLOAD_SIZE_BYTES is rejected with 413."""
    # test_settings sets MAX_UPLOAD_SIZE_BYTES to 5 MB
    large_fake_pdf = b"%PDF-1.7\n" + b"X" * (6 * 1024 * 1024)
    files = {"file": ("large.pdf", io.BytesIO(large_fake_pdf), "application/pdf")}
    res = client.post("/api/documents/upload", files=files)
    assert res.status_code == 413
    assert "maximum allowed limit" in res.json()["detail"].lower()


def test_upload_single_page_pdf(client: TestClient, sample_single_page_pdf_bytes: bytes) -> None:
    """Verify uploading a single-page document detects SINGLE_PAGE layout."""
    files = {"file": ("single.pdf", io.BytesIO(sample_single_page_pdf_bytes), "application/pdf")}
    res = client.post("/api/documents/upload", files=files)
    assert res.status_code == 201
    doc_id = res.json()["document_id"]

    meta_res = client.get(f"/api/documents/{doc_id}")
    assert meta_res.status_code == 200
    meta = meta_res.json()
    assert meta["page_count"] == 1
    assert meta["pages"][0]["detected_layout"] == "SINGLE_PAGE"
