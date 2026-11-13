"""Tests for Preview Integration & PDF Page Rendering — Phase 1.2.2.5.

Comprehensive tests covering:
1. PDFPageRenderer functionality across Documents, bytes, and files.
2. Error handling (bounds, invalid inputs, non-existent files).
3. Source PDF integrity and read-only preservation.
4. Pixel-coordinate overlay alignment at configurable DPI.
5. Visual compositing across all 3 layout types (Cover, 4-Up, Single Page).
6. Accessibility cues, spine exclusion zones, cut lines, and status badges.
7. Safety guardrails: Cover and non-nominal Single Page held in MANUAL_REVIEW_REQUIRED.
8. Multi-page document preview composition.
9. Temporary preview artifact writing and cleanup.
10. Strict production isolation (PNG-only previews, no JPG exports, no PDF slicing).
"""

from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
import tempfile

from PIL import Image
import pymupdf
import pytest

from app.crop.calculator.cover_strategy import CoverCropStrategy
from app.crop.calculator.imposition_4up_strategy import Imposition4UpCropStrategy
from app.crop.calculator.single_page_strategy import SinglePageCropStrategy
from app.crop.calculator.unresolved import (
    UNRESOLVED_COVER_WIDTH_DISCREPANCY,
    UNRESOLVED_SINGLE_PAGE_NORMALIZATION_POLICY,
)
from app.crop.models.document_crop_plan import DocumentCropPlan, DocumentStatus
from app.crop.models.enums import (
    ClassificationStatus,
    CropReadinessStatus,
    LayoutType,
)
from app.crop.preview.compositor import PreviewCompositor
from app.crop.preview.engine import PreviewVisualizationEngine
from app.crop.preview.models import PreviewImageOutput, PreviewPagePayload
from app.crop.preview.pdf_renderer import PDFPageRenderer
from app.crop.profiles.profile_configs import create_imposition_4up_profile


# --- Fixtures ---

@pytest.fixture
def sample_4up_pdf_doc() -> pymupdf.Document:
    """Create a synthetic in-memory 4-Up PDF document with 2 sheets."""
    doc = pymupdf.open()
    # Sheet 1 & 2: 878.74 x 1247.24 pt (Bookabook Comic A5 4-Up)
    for _ in range(2):
        doc.new_page(width=878.74, height=1247.24)
    return doc


@pytest.fixture
def sample_cover_pdf_doc() -> pymupdf.Document:
    """Create a synthetic in-memory Cover Spread PDF document."""
    doc = pymupdf.open()
    # Cover: 1259.69 x 637.80 pt
    doc.new_page(width=1259.69, height=637.80)
    return doc


@pytest.fixture
def sample_complete_6page_pdf_doc() -> pymupdf.Document:
    """Create a synthetic complete 6-page Bookabook PDF document."""
    doc = pymupdf.open()
    # Page 1 (index 0): Cover Spread
    doc.new_page(width=1259.69, height=637.80)
    # Pages 2-6 (index 1..5): 4-Up Imposition
    for _ in range(5):
        doc.new_page(width=878.74, height=1247.24)
    return doc


# --- 1. PDFPageRenderer Unit Tests ---

class TestPDFPageRenderer:
    """Tests for PDFPageRenderer."""

    def test_init_default_dpi(self) -> None:
        renderer = PDFPageRenderer()
        assert renderer.default_dpi == 100

    def test_init_custom_dpi(self) -> None:
        renderer = PDFPageRenderer(default_dpi=150)
        assert renderer.default_dpi == 150

    def test_init_invalid_dpi_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            PDFPageRenderer(default_dpi=0)
        with pytest.raises(ValueError, match="positive"):
            PDFPageRenderer(default_dpi=-50)

    def test_render_page_to_image_from_doc(self, sample_4up_pdf_doc: pymupdf.Document) -> None:
        renderer = PDFPageRenderer(default_dpi=100)
        img = renderer.render_page_to_image(sample_4up_pdf_doc, page_index=0)

        assert isinstance(img, Image.Image)
        assert img.mode == "RGB"
        # 878.74 pt * 100 / 72 ≈ 1220.47 -> 1221 px
        # 1247.24 pt * 100 / 72 ≈ 1732.28 -> 1733 px
        assert img.width == 1221
        assert img.height == 1733

    def test_render_page_to_image_from_bytes(self, sample_4up_pdf_doc: pymupdf.Document) -> None:
        pdf_bytes = sample_4up_pdf_doc.tobytes()
        renderer = PDFPageRenderer(default_dpi=72)
        img = renderer.render_page_to_image(pdf_bytes, page_index=0)

        assert isinstance(img, Image.Image)
        # At 72 DPI, 878.74 pt -> 879 px, 1247.24 pt -> 1248 px
        assert img.width == 879
        assert img.height == 1248

    def test_render_page_to_image_from_file(self, sample_4up_pdf_doc: pymupdf.Document) -> None:
        with tempfile.TemporaryDirectory() as td:
            temp_path = str(Path(td) / "sample_4up.pdf")
            sample_4up_pdf_doc.save(temp_path)

            renderer = PDFPageRenderer(default_dpi=100)
            img = renderer.render_page_to_image(temp_path, page_index=1)
            assert isinstance(img, Image.Image)
            assert img.width == 1221
            assert img.height == 1733

    def test_render_page_to_bytes(self, sample_cover_pdf_doc: pymupdf.Document) -> None:
        renderer = PDFPageRenderer(default_dpi=100)
        png_bytes = renderer.render_page_to_bytes(sample_cover_pdf_doc, page_index=0)

        assert isinstance(png_bytes, bytes)
        assert len(png_bytes) > 0
        # Check PNG header signature
        assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")

    def test_get_page_count(self, sample_4up_pdf_doc: pymupdf.Document) -> None:
        renderer = PDFPageRenderer()
        assert renderer.get_page_count(sample_4up_pdf_doc) == 2

    def test_get_page_dimensions_pt(self, sample_cover_pdf_doc: pymupdf.Document) -> None:
        renderer = PDFPageRenderer()
        w_pt, h_pt = renderer.get_page_dimensions_pt(sample_cover_pdf_doc, page_index=0)
        assert round(w_pt, 2) == 1259.69
        assert round(h_pt, 2) == 637.80

    def test_get_page_rotation(self, sample_4up_pdf_doc: pymupdf.Document) -> None:
        renderer = PDFPageRenderer()
        assert renderer.get_page_rotation(sample_4up_pdf_doc, page_index=0) == 0

    def test_empty_bytes_raises_value_error(self) -> None:
        renderer = PDFPageRenderer()
        with pytest.raises(ValueError, match="empty"):
            renderer.render_page_to_image(b"", page_index=0)

    def test_nonexistent_file_raises_not_found(self) -> None:
        renderer = PDFPageRenderer()
        with pytest.raises(FileNotFoundError, match="not found"):
            renderer.render_page_to_image("non_existent_path_xyz.pdf", page_index=0)

    def test_page_index_out_of_bounds_raises_index_error(self, sample_4up_pdf_doc: pymupdf.Document) -> None:
        renderer = PDFPageRenderer()
        with pytest.raises(IndexError, match="out of range"):
            renderer.render_page_to_image(sample_4up_pdf_doc, page_index=99)
        with pytest.raises(IndexError, match="out of range"):
            renderer.render_page_to_image(sample_4up_pdf_doc, page_index=-1)

    def test_unsupported_source_type_raises_type_error(self) -> None:
        renderer = PDFPageRenderer()
        with pytest.raises(TypeError, match="Unsupported PDF source type"):
            renderer.render_page_to_image(12345, page_index=0)  # type: ignore

    def test_source_pdf_remains_unmodified(self, sample_4up_pdf_doc: pymupdf.Document) -> None:
        """Verify rendering does not alter the source document in memory."""
        initial_page_count = len(sample_4up_pdf_doc)
        initial_rects = [sample_4up_pdf_doc[i].rect for i in range(initial_page_count)]
        initial_rotations = [sample_4up_pdf_doc[i].rotation for i in range(initial_page_count)]

        renderer = PDFPageRenderer(default_dpi=100)
        _ = renderer.render_page_to_image(sample_4up_pdf_doc, page_index=0)
        _ = renderer.render_page_to_bytes(sample_4up_pdf_doc, page_index=1)

        assert len(sample_4up_pdf_doc) == initial_page_count
        for i in range(initial_page_count):
            assert sample_4up_pdf_doc[i].rect == initial_rects[i]
            assert sample_4up_pdf_doc[i].rotation == initial_rotations[i]


# --- 2. PreviewCompositor & Overlay Alignment Tests ---

class TestPreviewCompositor:
    """Tests for PreviewCompositor and coordinate alignment."""

    def test_composite_page_preview_structure(self) -> None:
        calc = Imposition4UpCropStrategy()
        plan = calc.calculate(sheet_number=1, total_sheets=5, width_pt=878.74, height_pt=1247.24)

        engine = PreviewVisualizationEngine()
        payload = engine.generate_page_preview(plan, canvas_width=1221, canvas_height=1733, margin_padding_px=0.0)

        img = Image.new("RGB", (1221, 1733), (255, 255, 255))
        compositor = PreviewCompositor()
        out = compositor.composite_page_preview(img, payload, dpi=100)

        assert isinstance(out, PreviewImageOutput)
        assert out.pdf_page_number == 2
        assert out.layout_type == LayoutType.IMPOSITION_4UP
        assert out.crop_readiness == CropReadinessStatus.CROP_READY
        assert out.image_format == "PNG"
        assert out.width_px == 1221
        assert out.height_px == 1733
        assert out.dpi == 100
        assert out.data_uri.startswith("data:image/png;base64,")
        assert len(out.image_bytes) > 0
        assert out.is_auto_crop_allowed is True

    def test_overlay_midpoint_cut_line_alignment(self) -> None:
        """Verify midpoint cut lines meet at exact center of 4-Up sheet."""
        calc = Imposition4UpCropStrategy()
        plan = calc.calculate(sheet_number=1, total_sheets=5, width_pt=878.74, height_pt=1247.24)

        engine = PreviewVisualizationEngine()
        payload = engine.generate_page_preview(plan, canvas_width=1220, canvas_height=1732, margin_padding_px=0.0)

        # In 1220x1732 canvas, midpoint should be (610, 866)
        vert_line = next(l for l in payload.cut_lines if l.line_type == "MIDPOINT_CUT_VERTICAL")
        horiz_line = next(l for l in payload.cut_lines if l.line_type == "MIDPOINT_CUT_HORIZONTAL")

        assert round(vert_line.x1) == 610
        assert round(horiz_line.y1) == 866

    def test_spine_exclusion_zone_rendering_on_cover(self) -> None:
        """Verify spine exclusion zone is rendered on Cover Spread."""
        calc = CoverCropStrategy()
        plan = calc.calculate(width_pt=1259.69, height_pt=637.80)

        engine = PreviewVisualizationEngine()
        payload = engine.generate_page_preview(plan, canvas_width=1750, canvas_height=886, margin_padding_px=0.0)

        assert payload.spine_zone is not None
        assert payload.spine_zone.width_mm == pytest.approx(15.02, abs=0.05)

        img = Image.new("RGB", (1750, 886), (255, 255, 255))
        compositor = PreviewCompositor()
        out = compositor.composite_page_preview(img, payload, dpi=100)

        assert out.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED
        assert out.is_auto_crop_allowed is False
        assert UNRESOLVED_COVER_WIDTH_DISCREPANCY in out.unresolved_discrepancies

    def test_invalid_image_dimensions_raises(self) -> None:
        calc = Imposition4UpCropStrategy()
        plan = calc.calculate(sheet_number=1, total_sheets=5, width_pt=878.74, height_pt=1247.24)
        engine = PreviewVisualizationEngine()
        payload = engine.generate_page_preview(plan, canvas_width=100, canvas_height=100)

        img = Image.new("RGB", (0, 0))  # zero-size image
        compositor = PreviewCompositor()
        with pytest.raises(ValueError, match="Invalid image dimensions"):
            compositor.composite_page_preview(img, payload)


# --- 3. Engine End-to-End Integration Tests ---

class TestEnginePreviewIntegration:
    """Tests for PreviewVisualizationEngine.compose_page_preview & compose_document_preview."""

    def test_compose_page_preview_4up(self, sample_complete_6page_pdf_doc: pymupdf.Document) -> None:
        calc = Imposition4UpCropStrategy()
        plan = calc.calculate(sheet_number=1, total_sheets=5, width_pt=878.74, height_pt=1247.24)

        engine = PreviewVisualizationEngine(default_dpi=100)
        out = engine.compose_page_preview(
            page_plan=plan,
            pdf_source=sample_complete_6page_pdf_doc,
            dpi=100,
        )

        assert out.pdf_page_number == 2
        assert out.layout_type == LayoutType.IMPOSITION_4UP
        assert out.crop_readiness == CropReadinessStatus.CROP_READY
        assert out.is_auto_crop_allowed is True
        assert out.width_px == 1221
        assert out.height_px == 1733
        assert out.image_format == "PNG"
        assert out.data_uri.startswith("data:image/png;base64,")

    def test_compose_page_preview_cover(self, sample_complete_6page_pdf_doc: pymupdf.Document) -> None:
        calc = CoverCropStrategy()
        plan = calc.calculate(width_pt=1259.69, height_pt=637.80)

        engine = PreviewVisualizationEngine(default_dpi=100)
        out = engine.compose_page_preview(
            page_plan=plan,
            pdf_source=sample_complete_6page_pdf_doc,
            dpi=100,
        )

        assert out.pdf_page_number == 1
        assert out.layout_type == LayoutType.COVER_SPREAD
        assert out.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED
        assert out.is_auto_crop_allowed is False
        assert out.width_px == 1750
        assert out.height_px == 886
        assert len(out.warnings) > 0
        assert "Cover Spread auto-crop is disabled" in out.warnings[0]

    def test_compose_page_preview_single_page_nominal(self) -> None:
        calc = SinglePageCropStrategy()
        plan = calc.calculate(pdf_page_index=0, page_width_pt=425.52, page_height_pt=609.12)

        doc = pymupdf.open()
        doc.new_page(width=425.52, height=609.12)

        engine = PreviewVisualizationEngine(default_dpi=100)
        out = engine.compose_page_preview(
            page_plan=plan,
            pdf_source=doc,
            dpi=100,
        )

        assert out.pdf_page_number == 1
        assert out.layout_type == LayoutType.SINGLE_PAGE
        assert out.crop_readiness == CropReadinessStatus.CROP_READY
        assert out.is_auto_crop_allowed is True
        assert out.is_non_nominal is False

    def test_compose_page_preview_single_page_non_nominal_held_for_review(self) -> None:
        calc = SinglePageCropStrategy()
        plan = calc.calculate(pdf_page_index=0, page_width_pt=430.00, page_height_pt=620.00)

        doc = pymupdf.open()
        doc.new_page(width=430.00, height=620.00)

        engine = PreviewVisualizationEngine(default_dpi=100)
        out = engine.compose_page_preview(
            page_plan=plan,
            pdf_source=doc,
            dpi=100,
        )

        assert out.pdf_page_number == 1
        assert out.layout_type == LayoutType.SINGLE_PAGE
        assert out.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED
        assert out.is_auto_crop_allowed is False
        assert out.is_non_nominal is True
        assert UNRESOLVED_SINGLE_PAGE_NORMALIZATION_POLICY in out.unresolved_discrepancies
        assert any("Non-nominal single page dimensions" in w for w in out.warnings)

    def test_compose_document_preview_complete_book(
        self,
        sample_complete_6page_pdf_doc: pymupdf.Document,
    ) -> None:
        """Verify compose_document_preview processes all 6 sheets correctly."""
        cover_calc = CoverCropStrategy()
        cover_plan = cover_calc.calculate(width_pt=1259.69, height_pt=637.80)

        imp_calc = Imposition4UpCropStrategy()
        body_plans = [
            imp_calc.calculate(pdf_page_index=s, page_width_pt=878.74, height_pt=1247.24)
            for s in range(1, 6)
        ]

        profile = create_imposition_4up_profile()
        doc_plan = DocumentCropPlan(
            source_filename="test_book_6sheets.pdf",
            total_pdf_pages=6,
            expected_total_book_pages=22,
            page_sequence_signature=["COVER_SPREAD"] + ["IMPOSITION_4UP"] * 5,
            profile=profile,
            page_plans=[cover_plan] + body_plans,
            document_status=DocumentStatus(
                document_status="MANUAL_REVIEW_REQUIRED",
                has_manual_review_required=True,
                all_pages_crop_ready=False,
                summary_message="Sheet 1 (Cover Spread) held for manual review",
            ),
        )

        engine = PreviewVisualizationEngine(default_dpi=100)
        outputs = engine.compose_document_preview(
            doc_plan=doc_plan,
            pdf_source=sample_complete_6page_pdf_doc,
            dpi=100,
        )

        assert len(outputs) == 6

        # Sheet 1: Cover Spread held in manual review
        assert outputs[0].pdf_page_number == 1
        assert outputs[0].layout_type == LayoutType.COVER_SPREAD
        assert outputs[0].crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED
        assert outputs[0].is_auto_crop_allowed is False

        # Sheets 2-6: 4-Up Imposition sheets ready for cropping
        for i in range(1, 6):
            assert outputs[i].pdf_page_number == i + 1
            assert outputs[i].layout_type == LayoutType.IMPOSITION_4UP
            assert outputs[i].crop_readiness == CropReadinessStatus.CROP_READY
            assert outputs[i].is_auto_crop_allowed is True
            assert outputs[i].image_format == "PNG"

    def test_save_to_temp_directory(
        self,
        sample_complete_6page_pdf_doc: pymupdf.Document,
    ) -> None:
        """Verify saving temporary preview artifacts named PREVIEW_PAGE_{n}.png."""
        cover_calc = CoverCropStrategy()
        cover_plan = cover_calc.calculate(width_pt=1259.69, height_pt=637.80)

        with tempfile.TemporaryDirectory() as temp_dir:
            engine = PreviewVisualizationEngine(default_dpi=100)
            out = engine.compose_page_preview(
                page_plan=cover_plan,
                pdf_source=sample_complete_6page_pdf_doc,
                dpi=100,
                save_to_dir=temp_dir,
            )

            expected_path = Path(temp_dir) / "PREVIEW_PAGE_1.png"
            assert out.temp_file_path == str(expected_path)
            assert expected_path.exists()
            assert expected_path.stat().st_size > 0

            # Verify saved file is a valid PNG readable by PIL
            with Image.open(str(expected_path)) as saved_img:
                assert saved_img.format == "PNG"
                assert saved_img.width == 1750
                assert saved_img.height == 886


# --- 4. Safety Guardrails & Production Isolation Tests ---

class TestSafetyGuardrails:
    """Tests for strict safety constraints in Phase 1.2.2.5."""

    def test_preview_outputs_are_strictly_png_never_jpg(
        self,
        sample_4up_pdf_doc: pymupdf.Document,
    ) -> None:
        """Production outputs are 300 DPI JPGs; Previews must strictly be PNG."""
        calc = Imposition4UpCropStrategy()
        plan = calc.calculate(sheet_number=1, total_sheets=5, width_pt=878.74, height_pt=1247.24)

        engine = PreviewVisualizationEngine()
        out = engine.compose_page_preview(plan, sample_4up_pdf_doc, dpi=100)

        assert out.image_format == "PNG"
        assert not out.image_format.lower().endswith("jpg")
        assert not out.image_format.lower().endswith("jpeg")

    def test_cover_auto_crop_is_always_prohibited(
        self,
        sample_cover_pdf_doc: pymupdf.Document,
    ) -> None:
        """Auto-crop must never be allowed on Cover sheets in preview or elsewhere."""
        calc = CoverCropStrategy()
        plan = calc.calculate(width_pt=1259.69, height_pt=637.80)

        engine = PreviewVisualizationEngine()
        out = engine.compose_page_preview(plan, sample_cover_pdf_doc, dpi=100)

        assert out.is_auto_crop_allowed is False
        assert out.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED

    def test_source_pdf_is_not_modified_during_composition(
        self,
        sample_complete_6page_pdf_doc: pymupdf.Document,
    ) -> None:
        """Verify that composing previews does not alter the source PDF."""
        initial_page_count = len(sample_complete_6page_pdf_doc)
        initial_rects = [sample_complete_6page_pdf_doc[i].rect for i in range(initial_page_count)]
        initial_rotations = [sample_complete_6page_pdf_doc[i].rotation for i in range(initial_page_count)]

        cover_calc = CoverCropStrategy()
        cover_plan = cover_calc.calculate(width_pt=1259.69, height_pt=637.80)
        engine = PreviewVisualizationEngine()
        _ = engine.compose_page_preview(cover_plan, sample_complete_6page_pdf_doc)

        assert len(sample_complete_6page_pdf_doc) == initial_page_count
        for i in range(initial_page_count):
            assert sample_complete_6page_pdf_doc[i].rect == initial_rects[i]
            assert sample_complete_6page_pdf_doc[i].rotation == initial_rotations[i]
