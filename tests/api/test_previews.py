"""Tests for Preview endpoints."""

from __future__ import annotations

import io
from fastapi.testclient import TestClient
from PIL import Image


def test_get_preview_for_6page_document(
    client: TestClient, sample_6page_pdf_bytes: bytes
) -> None:
    """Verify structured preview generation for a 6-page Bookabook PDF."""
    files = {"file": ("book.pdf", io.BytesIO(sample_6page_pdf_bytes), "application/pdf")}
    upload_res = client.post("/api/documents/upload", files=files)
    doc_id = upload_res.json()["document_id"]

    res = client.get(f"/api/documents/{doc_id}/preview")
    assert res.status_code == 200
    data = res.json()

    assert data["document_id"] == doc_id
    assert data["total_pages"] == 6
    assert data["expected_book_pages"] == 22  # 2 (Cover) + 5*4 (Imposition) = 22
    assert data["document_status"] == "MANUAL_REVIEW_REQUIRED"
    assert data["has_manual_review_required"] is True
    assert data["has_unknown_layout"] is False

    pages = data["pages"]
    assert len(pages) == 6

    # Sheet 1: Cover Spread
    cover_page = pages[0]
    assert cover_page["page_number"] == 1
    assert cover_page["layout_type"] == "COVER_SPREAD"
    assert cover_page["crop_readiness"] == "MANUAL_REVIEW_REQUIRED"
    assert cover_page["expected_page_yield"] == 2
    assert f"/api/documents/{doc_id}/pages/1/preview.png" in cover_page["preview_image_url"]
    assert len(cover_page["unresolved_discrepancies"]) > 0

    # Sheets 2-6: 4-Up Imposition
    for i in range(1, 6):
        imp_page = pages[i]
        assert imp_page["page_number"] == i + 1
        assert imp_page["layout_type"] == "IMPOSITION_4UP"
        assert imp_page["expected_page_yield"] == 4
        assert f"/api/documents/{doc_id}/pages/{i + 1}/preview.png" in imp_page["preview_image_url"]

    # Validation summary
    val_summary = data["validation_summary"]
    assert val_summary["total_regions"] == 22


def test_get_preview_page_png_image(
    client: TestClient, sample_6page_pdf_bytes: bytes
) -> None:
    """Verify rendering and retrieving composite PNG preview image."""
    files = {"file": ("book.pdf", io.BytesIO(sample_6page_pdf_bytes), "application/pdf")}
    upload_res = client.post("/api/documents/upload", files=files)
    doc_id = upload_res.json()["document_id"]

    # Page 1 preview PNG
    img_res = client.get(f"/api/documents/{doc_id}/pages/1/preview.png")
    assert img_res.status_code == 200
    assert img_res.headers["content-type"] == "image/png"
    assert len(img_res.content) > 0
    # PNG signature: 89 50 4E 47 0D 0A 1A 0A
    assert img_res.content[:8] == b"\x89PNG\r\n\x1a\n"

    # Page 2 preview PNG
    img_res2 = client.get(f"/api/documents/{doc_id}/pages/2/preview.png")
    assert img_res2.status_code == 200
    assert img_res2.headers["content-type"] == "image/png"
    assert img_res2.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_get_preview_page_out_of_range_fails(
    client: TestClient, sample_6page_pdf_bytes: bytes
) -> None:
    """Verify requesting an out-of-bounds page returns 404."""
    files = {"file": ("book.pdf", io.BytesIO(sample_6page_pdf_bytes), "application/pdf")}
    upload_res = client.post("/api/documents/upload", files=files)
    doc_id = upload_res.json()["document_id"]

    # Page 0 (out of bounds)
    res_zero = client.get(f"/api/documents/{doc_id}/pages/0/preview.png")
    assert res_zero.status_code == 404

    # Page 99 (out of bounds)
    res_high = client.get(f"/api/documents/{doc_id}/pages/99/preview.png")
    assert res_high.status_code == 404


def test_preview_for_nonexistent_document_fails(client: TestClient) -> None:
    """Verify requesting preview for non-existent document returns 404."""
    res = client.get("/api/documents/doc_missing123/preview")
    assert res.status_code == 404

    img_res = client.get("/api/documents/doc_missing123/pages/1/preview.png")
    assert img_res.status_code == 404


def test_preview_for_unknown_layout(
    client: TestClient, sample_unknown_layout_pdf_bytes: bytes
) -> None:
    """Verify unknown layout is correctly classified and flagged as REJECTED_UNKNOWN_LAYOUT."""
    files = {"file": ("unknown.pdf", io.BytesIO(sample_unknown_layout_pdf_bytes), "application/pdf")}
    upload_res = client.post("/api/documents/upload", files=files)
    doc_id = upload_res.json()["document_id"]

    res = client.get(f"/api/documents/{doc_id}/preview")
    assert res.status_code == 200
    data = res.json()
    assert data["has_unknown_layout"] is True
    assert data["document_status"] == "REJECTED_UNKNOWN_LAYOUT"
    assert data["pages"][0]["crop_readiness"] == "NOT_APPLICABLE"
    assert data["pages"][0]["regions"] == []


def test_preview_overlay_toggle_and_region_pngs(
    client: TestClient, sample_6page_pdf_bytes: bytes
) -> None:
    """Verify ?overlay=true|false and cropped region PNG endpoints preserve aspect ratio."""
    files = {"file": ("book.pdf", io.BytesIO(sample_6page_pdf_bytes), "application/pdf")}
    upload_res = client.post("/api/documents/upload", files=files)
    doc_id = upload_res.json()["document_id"]

    meta = client.get(f"/api/documents/{doc_id}/preview").json()
    cover_regions = meta["pages"][0]["regions"]
    assert [r["region_id"] for r in cover_regions] == ["BACKCOVER", "COVER"]
    assert all(r["quadrant"] is None for r in cover_regions)

    sheet2_regions = meta["pages"][1]["regions"]
    assert [(r["region_id"], r["quadrant"]) for r in sheet2_regions] == [
        ("PAGE-01", 1),
        ("PAGE-02", 2),
        ("PAGE-03", 3),
        ("PAGE-04", 4),
    ]

    # Sheet PNG overlay=true vs overlay=false
    default_png = client.get(f"/api/documents/{doc_id}/pages/2/preview.png")
    overlay_true_png = client.get(f"/api/documents/{doc_id}/pages/2/preview.png?overlay=true")
    overlay_false_png = client.get(f"/api/documents/{doc_id}/pages/2/preview.png?overlay=false")
    assert default_png.status_code == 200
    assert overlay_true_png.status_code == 200
    assert overlay_false_png.status_code == 200
    assert default_png.content == overlay_true_png.content
    assert overlay_false_png.content != overlay_true_png.content

    with Image.open(io.BytesIO(overlay_true_png.content)) as im_on, Image.open(
        io.BytesIO(overlay_false_png.content)
    ) as im_off:
        assert im_on.size == im_off.size

    # Cropped region PNG for Q1 (PAGE-01) preserves physical aspect ratio
    reg = sheet2_regions[0]
    reg_clean = client.get(f"{reg['preview_image_url']}?overlay=false")
    reg_over = client.get(f"{reg['preview_image_url']}?overlay=true")
    assert reg_clean.status_code == 200
    assert reg_over.status_code == 200
    assert reg_clean.headers["content-type"] == "image/png"
    assert reg_clean.content != reg_over.content

    with Image.open(io.BytesIO(reg_clean.content)) as reg_im:
        rendered_ar = reg_im.width / reg_im.height
        physical_ar = reg["width_pt"] / reg["height_pt"]
        assert abs(rendered_ar - physical_ar) < 0.02

    # Missing region returns 404
    missing_reg = client.get(
        f"/api/documents/{doc_id}/pages/2/regions/DOES-NOT-EXIST/preview.png"
    )
    assert missing_reg.status_code == 404

