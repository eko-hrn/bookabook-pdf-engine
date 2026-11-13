"""Tests for Production 300 DPI RGB JPEG Exporter & Adaptive Compression."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
import random
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import pymupdf
import pytest

from app.crop.exporter import (
    BACKCOVER_MAX_BYTES,
    COVER_MAX_BYTES,
    INITIAL_HIGH_QUALITY,
    INSIDE_PAGE_MAX_BYTES,
    CompressionLimitExceededError,
    CompressionStatus,
    CompressionTier,
    PageKind,
    ProductionPDFExporter,
    build_export_zip_bytes,
    compress_single_page,
    enforce_book_compression_budget,
)

SAMPLE_REAL_PDF = Path(__file__).resolve().parents[2] / "data" / "uploads" / "doc_861c55342a0e.pdf"


def _make_dense_pattern_bytes(width: int, height: int, seed: int) -> bytes:
    """Create crisp comic-like patterned RGB PNG bytes realistic enough to compress <= 500 KB at 300 DPI."""
    rng = np.random.default_rng(seed)
    coarse = rng.integers(30, 230, size=(max(height // 6, 8), max(width // 6, 8), 3), dtype=np.uint8)
    im = (
        Image.fromarray(coarse, mode="RGB")
        .resize((width, height), Image.Resampling.BILINEAR)
        .filter(ImageFilter.GaussianBlur(radius=1.5))
    )
    draw = ImageDraw.Draw(im)
    draw.rectangle([20, 20, width - 20, 75], fill=(245, 245, 245), outline=(20, 20, 20), width=2)
    draw.rectangle([20, 95, width - 20, height - 20], outline=(30, 30, 30), width=2)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _create_synthetic_book_pdf(
    *,
    cover_w: float = 1247.24,
    cover_h: float = 878.74,
    four_up_sheets: int = 2,
    blank_last_quadrant: bool = False,
) -> bytes:
    doc = pymupdf.open()

    # Sheet 1: Cover spread (Left = Backcover, Center = Spine excluded, Right = Cover)
    p_cover = doc.new_page(width=cover_w, height=cover_h)
    y0 = 120.49 if cover_h > 800 else 0.0
    y1 = 758.25 if cover_h > 800 else cover_h
    p_cover.insert_image(
        pymupdf.Rect(156.0, y0, 608.5, y1),
        stream=_make_dense_pattern_bytes(500, 700, seed=1),
    )
    p_cover.insert_text((623, min(180, cover_h * 0.3)), "SPINE_DO_NOT_EXPORT", fontsize=10)
    p_cover.insert_image(
        pymupdf.Rect(651.2, y0, 1105.6, y1),
        stream=_make_dense_pattern_bytes(500, 700, seed=2),
    )

    # Interior 4-Up sheets
    for s in range(four_up_sheets):
        p = doc.new_page(width=878.74, height=1247.24)
        xc, yc = 439.37, 623.62
        # Add authentic midpoint ticks
        p.draw_line((xc, 0), (xc, 7.0))
        p.draw_line((xc, 1240.0), (xc, 1247.24))
        p.draw_line((0, yc), (7.0, yc))
        p.draw_line((871.7, yc), (878.74, yc))

        quads = [
            pymupdf.Rect(30, 30, xc - 20, yc - 20),
            pymupdf.Rect(xc + 20, 30, 848, yc - 20),
            pymupdf.Rect(30, yc + 20, xc - 20, 1217),
            pymupdf.Rect(xc + 20, yc + 20, 848, 1217),
        ]
        for q_idx, rect in enumerate(quads):
            if blank_last_quadrant and s == four_up_sheets - 1 and q_idx == 3:
                continue
            p.insert_image(rect, stream=_make_dense_pattern_bytes(350, 500, seed=10 + s * 4 + q_idx))

    return doc.tobytes()


def test_exporter_splits_cover_content_backcover_and_excludes_spine() -> None:
    pdf_bytes = _create_synthetic_book_pdf(four_up_sheets=2, blank_last_quadrant=True)
    exporter = ProductionPDFExporter(target_dpi=300)
    res = exporter.export_pdf(pdf_bytes, source_filename="synthetic_comic.pdf")

    assert res.validation.is_valid is True
    assert res.validation.auto_validated is True
    assert res.validation.compression_status == CompressionStatus.PASSED
    assert res.validation.cover_detected is True
    assert res.validation.backcover_detected is True
    assert res.validation.total_exported_files == 10  # COVER + 8 PAGE + BACKCOVER
    assert res.validation.content_pages_count == 7   # 1 blank quadrant detected
    assert res.validation.blank_pages_detected == 1
    assert res.validation.files_over_policy_limit == 0
    assert res.validation.compression_failures == []

    filenames = [p.filename for p in res.pages]
    assert filenames[0] == "COVER.jpg"
    assert filenames[1:9] == [f"PAGE-{i:02d}.jpg" for i in range(1, 9)]
    assert filenames[-1] == "BACKCOVER.jpg"
    assert all("SPINE" not in fn.upper() for fn in filenames)

    # Check COVER, CONTENT, BACKCOVER JPEG properties (300 DPI, RGB, exact aspect ratio, category limits)
    for page in res.pages:
        assert page.dpi == 300
        assert page.colorspace == "RGB"
        assert page.image_format == "JPEG"
        assert page.compression_status == CompressionStatus.PASSED
        limit = BACKCOVER_MAX_BYTES if page.page_kind == PageKind.BACKCOVER else COVER_MAX_BYTES
        assert page.file_size_bytes <= limit
        assert page.image_bytes is not None
        assert page.sha256 == hashlib.sha256(page.image_bytes).hexdigest()
        with Image.open(io.BytesIO(page.image_bytes)) as im:
            assert im.format == "JPEG"
            assert im.mode == "RGB"
            assert im.size == (page.width_px, page.height_px)
            assert im.info.get("dpi") == (300, 300)
            im.load()
            ar_px = im.width / im.height
            ar_pt = page.width_pt / page.height_pt
            assert abs(ar_px - ar_pt) < 0.005

    # ZIP archive roundtrip check
    zip_bytes = build_export_zip_bytes(
        [(p.filename, p.image_bytes) for p in res.pages if p.image_bytes is not None]
    )
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        assert zf.namelist() == filenames
        assert zf.read("COVER.jpg") == res.pages[0].image_bytes
        assert zf.read("BACKCOVER.jpg") == res.pages[-1].image_bytes


def test_exporter_handles_pretrimmed_synthetic_cover_dimensions() -> None:
    pdf_bytes = _create_synthetic_book_pdf(cover_w=1259.69, cover_h=637.80, four_up_sheets=1)
    res = ProductionPDFExporter(target_dpi=300).export_pdf(pdf_bytes)
    assert res.validation.is_valid is True
    assert [p.filename for p in res.pages] == [
        "COVER.jpg",
        "PAGE-01.jpg",
        "PAGE-02.jpg",
        "PAGE-03.jpg",
        "PAGE-04.jpg",
        "BACKCOVER.jpg",
    ]


def _make_dense_300dpi_image(
    width: int,
    height: int,
    seed: int,
    detail_step: int = 28,
    coarse_div: int = 16,
    blur_radius: float = 1.8,
) -> Image.Image:
    """Create a realistic 300 DPI comic/photo image whose q=95 size exceeds 400 KB / 1 MB."""
    rng = np.random.default_rng(seed)
    coarse = rng.integers(
        25,
        235,
        size=(max(height // coarse_div, 16), max(width // coarse_div, 16), 3),
        dtype=np.uint8,
    )
    base_img = (
        Image.fromarray(coarse, mode="RGB")
        .resize((width, height), Image.Resampling.BILINEAR)
        .filter(ImageFilter.GaussianBlur(radius=blur_radius))
    )
    draw = ImageDraw.Draw(base_img)
    draw.rectangle([80, 80, width - 80, 260], fill=(250, 250, 250), outline=(20, 20, 20), width=3)
    draw.text((120, 150), f"BOOKABOOK POLICY TEST {seed}", fill=(10, 10, 10))
    for y in range(300, height - 100, detail_step):
        draw.line([(60, y), (width - 60, y)], fill=((seed * 37) % 255, 45, 95), width=2)
    return base_img


def test_cover_and_inside_pages_exceeding_400kb_compress_under_500kb_with_adaptive_quality() -> None:
    """COVER and PAGE-01 exceeding 400 KB at q=95 adaptively compress <= 512,000 bytes preserving dimensions."""
    cover_img = _make_dense_300dpi_image(1894, 2657, seed=11, detail_step=28, coarse_div=16)
    inside_img = _make_dense_300dpi_image(1773, 2538, seed=12, detail_step=28, coarse_div=16)

    cover_res = compress_single_page(
        "COVER",
        PageKind.COVER,
        cover_img,
        dpi=300,
        filename="COVER.jpg",
    )
    inside_res = compress_single_page(
        "PAGE-01",
        PageKind.CONTENT,
        inside_img,
        dpi=300,
        filename="PAGE-01.jpg",
    )

    for cand, expected_size in ((cover_res, (1894, 2657)), (inside_res, (1773, 2538))):
        assert cand.baseline_complex_score > 400 * 1024
        assert cand.file_size_bytes <= COVER_MAX_BYTES
        assert cand.max_allowed_bytes == INSIDE_PAGE_MAX_BYTES == 409_600
        assert cand.quality_used < INITIAL_HIGH_QUALITY
        assert cand.compression_status == CompressionStatus.PASSED
        assert cand.image.size == expected_size
        with Image.open(io.BytesIO(cand.jpeg_bytes)) as im:
            assert im.format == "JPEG"
            assert im.mode == "RGB"
            assert im.size == expected_size
            assert im.info.get("dpi") == (300, 300)
            im.load()


def test_backcover_exceeding_1mb_compresses_under_1mb_with_higher_photo_quality() -> None:
    """BACKCOVER exceeding 1 MB at q=95 adapts <= 1,048,576 bytes and retains higher quality than 500 KB cap."""
    backcover_img = _make_dense_300dpi_image(
        1886, 2657, seed=21, detail_step=18, coarse_div=8, blur_radius=1.5
    )
    res = compress_single_page(
        "BACKCOVER",
        PageKind.BACKCOVER,
        backcover_img,
        dpi=300,
        filename="BACKCOVER.jpg",
    )

    assert res.baseline_complex_score > BACKCOVER_MAX_BYTES
    assert res.file_size_bytes <= BACKCOVER_MAX_BYTES
    assert res.max_allowed_bytes == 1_048_576
    assert res.quality_used < INITIAL_HIGH_QUALITY
    assert res.quality_used >= 65
    with Image.open(io.BytesIO(res.jpeg_bytes)) as im:
        assert im.format == "JPEG"
        assert im.mode == "RGB"
        assert im.size == (1886, 2657)
        assert im.info.get("dpi") == (300, 300)
        im.load()


def test_image_already_under_limit_keeps_initial_high_quality() -> None:
    """Clean illustration already under limit keeps initial_quality without unnecessary quality drop."""
    simple_img = Image.new("RGB", (1773, 2538), color=(248, 245, 240))
    draw = ImageDraw.Draw(simple_img)
    draw.rectangle([120, 120, 1650, 2400], outline=(30, 80, 120), width=6)
    draw.text((220, 260), "CLEAN BOOKABOOK PAGE", fill=(20, 20, 20))

    res = compress_single_page("PAGE-02", PageKind.CONTENT, simple_img, dpi=300, filename="PAGE-02.jpg")
    assert res.quality_used == INITIAL_HIGH_QUALITY
    assert res.subsampling_label == "4:4:4"
    assert res.file_size_bytes <= COVER_MAX_BYTES
    assert res.image.size == (1773, 2538)


def test_compression_failure_when_min_quality_cannot_satisfy_limit() -> None:
    """Verify strict quality protection refuses oversized output and avoids downscaling."""
    rng = np.random.default_rng(777)
    uncompressible = Image.fromarray(
        rng.integers(0, 255, size=(2538, 1773, 3), dtype=np.uint8),
        mode="RGB",
    )

    with pytest.raises(CompressionLimitExceededError) as exc_info:
        compress_single_page(
            "COVER",
            PageKind.COVER,
            uncompressible,
            dpi=300,
            filename="COVER.jpg",
            min_quality=75,
        )

    failure = exc_info.value.failure
    assert failure.filename == "COVER.jpg"
    assert failure.actual_size_bytes > COVER_MAX_BYTES
    assert failure.max_allowed_bytes == 409_600
    assert failure.min_quality_threshold == 75
    assert "COVER.jpg" in failure.reason
    assert "409,600" in failure.reason

    # Verify ProductionPDFExporter also returns structured FAILED validation without silently saving oversized files
    doc = pymupdf.open()
    page = doc.new_page(width=878.74, height=1247.24)
    buf = io.BytesIO()
    uncompressible.resize((900, 1300)).save(buf, format="PNG")
    for rx, ry in [(20, 20), (450, 20), (20, 640), (450, 640)]:
        page.insert_image(pymupdf.Rect(rx, ry, rx + 390, ry + 580), stream=buf.getvalue())

    strict_exporter = ProductionPDFExporter(target_dpi=300, min_quality=90)
    res = strict_exporter.export_pdf(doc.tobytes(), source_filename="strict_fail.pdf")

    assert res.validation.is_valid is False
    assert res.validation.compression_status == CompressionStatus.FAILED
    assert len(res.validation.compression_failures) >= 1
    first_fail = res.validation.compression_failures[0]
    assert first_fail.filename == "PAGE-01.jpg"
    assert first_fail.actual_size_bytes > INSIDE_PAGE_MAX_BYTES
    assert first_fail.max_allowed_bytes == 409_600
    assert res.pages == []


def test_enforce_book_compression_budget_validates_strict_category_caps() -> None:
    """Book-wide validation re-checks per-category binary limits on all candidates."""
    cover = compress_single_page(
        "COVER",
        PageKind.COVER,
        _make_dense_300dpi_image(1894, 2657, seed=31),
        dpi=300,
        filename="COVER.jpg",
    )
    page1 = compress_single_page(
        "PAGE-01",
        PageKind.CONTENT,
        _make_dense_300dpi_image(1773, 2538, seed=32),
        dpi=300,
        filename="PAGE-01.jpg",
    )
    backcover = compress_single_page(
        "BACKCOVER",
        PageKind.BACKCOVER,
        _make_dense_300dpi_image(1886, 2657, seed=33),
        dpi=300,
        filename="BACKCOVER.jpg",
    )
    final_items, _ = enforce_book_compression_budget([cover, page1, backcover])
    assert final_items[0].file_size_bytes <= COVER_MAX_BYTES
    assert final_items[1].file_size_bytes <= INSIDE_PAGE_MAX_BYTES
    assert final_items[2].file_size_bytes <= BACKCOVER_MAX_BYTES


def test_exporter_reports_unknown_layout_errors_without_crashing() -> None:
    doc = pymupdf.open()
    doc.new_page(width=200, height=200)
    res = ProductionPDFExporter().export_pdf(doc.tobytes(), source_filename="weird.pdf")
    assert res.validation.is_valid is False
    assert len(res.validation.errors) >= 1


@pytest.mark.skipif(not SAMPLE_REAL_PDF.is_file(), reason="Sample real comic PDF not present")
def test_real_comic_pdf_production_export_contract() -> None:
    """Verify exact 300 DPI crop geometry and final size caps on real Bookabook comic PDF."""
    exporter = ProductionPDFExporter(target_dpi=300)
    res = exporter.export_pdf(SAMPLE_REAL_PDF, source_filename="Preview COMIC COLLECTION vol 1.pdf")

    assert res.validation.is_valid is True
    assert res.validation.compression_status == CompressionStatus.PASSED
    assert res.validation.errors == []
    assert res.validation.compression_failures == []
    assert res.validation.cover_detected is True
    assert res.validation.backcover_detected is True
    assert res.validation.content_pages_count == 20
    assert res.validation.total_exported_files == 22
    assert res.validation.files_over_policy_limit == 0

    assert res.pages[0].filename == "COVER.jpg"
    assert (res.pages[0].width_px, res.pages[0].height_px) == (1894, 2657)
    assert res.pages[0].file_size_bytes <= COVER_MAX_BYTES

    assert res.pages[-1].filename == "BACKCOVER.jpg"
    assert (res.pages[-1].width_px, res.pages[-1].height_px) == (1886, 2657)
    assert res.pages[-1].file_size_bytes <= BACKCOVER_MAX_BYTES

    for page in res.pages[1:-1]:
        assert (page.width_px, page.height_px) == (1773, 2538)
        assert page.file_size_bytes <= INSIDE_PAGE_MAX_BYTES
        assert page.colorspace == "RGB"
        assert page.dpi == 300
        with Image.open(io.BytesIO(page.image_bytes or b"")) as im:
            assert im.format == "JPEG"
            assert im.mode == "RGB"
            assert im.size == (1773, 2538)
            assert im.info.get("dpi") == (300, 300)
            im.load()
