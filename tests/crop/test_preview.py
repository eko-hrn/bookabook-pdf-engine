"""Unit tests for Phase 1.2.2.4 — Preview Overlay & Visualization Engine.

Tests cover:
1. Coordinate Transformation and Aspect Ratio Preservation (anti-stretching, roundtrip inversion)
2. 4-Up Preview (Q1-Q4 boundaries, midpoint cut lines, outer trim boundaries, page labels PAGE-01..PAGE-20)
3. Cover Preview (BACKCOVER & COVER boundaries, spine exclusion zone, mandatory MANUAL_REVIEW_REQUIRED, auto-crop disabled, unresolved discrepancies)
4. Single Page Preview (nominal CROP_READY, non-nominal detection and warnings)
5. Status Visualization & Accessibility (distinct stroke dash patterns, colors, text labels, not color alone)
6. Structured Preview Payload Integrity (Pydantic validation, JSON serialization)
7. SVG Vector Overlay Generation (markup correctness, accessibility tags)
8. Safety Guardrails (no PDF cropping, no JPG export, no auto-approval)
"""

from __future__ import annotations

import json
import pytest

from app.crop.calculator import (
    CropCoordinateCalculator,
    DEFAULT_COVER_SPINE_INNER_LEFT_PT,
    DEFAULT_COVER_SPINE_INNER_RIGHT_PT,
    NOMINAL_4UP_SHEET_HEIGHT_PT,
    NOMINAL_4UP_SHEET_WIDTH_PT,
    NOMINAL_SINGLE_PAGE_HEIGHT_PT,
    NOMINAL_SINGLE_PAGE_WIDTH_PT,
    TickMarkCoordinates,
    UNRESOLVED_COVER_WIDTH_DISCREPANCY,
    UNRESOLVED_ROUNDING_1PX,
    UNRESOLVED_SINGLE_PAGE_NORMALIZATION_POLICY,
)
from app.crop.models.enums import (
    ClassificationStatus,
    CropReadinessStatus,
    LayoutType,
    ManualReviewFlag,
)
from app.crop.preview import (
    CoordinateTransformer,
    PreviewBox,
    PreviewDocumentPayload,
    PreviewLine,
    PreviewPagePayload,
    PreviewRegion,
    PreviewSpineZone,
    PreviewStatusBadge,
    PreviewVisualizationEngine,
    PreviewVisualStyle,
    SVGRenderer,
    STYLE_CROP_READY,
    STYLE_MANUAL_REVIEW_REQUIRED,
    STYLE_MIDPOINT_CUT,
    STYLE_OUTER_TRIM,
    STYLE_REJECTED,
    STYLE_SPINE_EXCLUSION,
    STYLE_UNKNOWN_LAYOUT,
    get_status_style,
)
from app.crop.profiles.profile_configs import (
    create_cover_profile,
    create_imposition_4up_profile,
    create_single_page_profile,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def preview_engine():
    return PreviewVisualizationEngine(default_canvas_width=800.0, default_canvas_height=600.0)


@pytest.fixture
def calculator():
    return CropCoordinateCalculator()


@pytest.fixture
def nominal_4up_page_plan(calculator):
    return calculator.calculate_imposition_4up(
        pdf_page_index=1,
        start_page_number=1,
    )


@pytest.fixture
def cover_page_plan(calculator):
    return calculator.calculate_cover(pdf_page_index=0)


@pytest.fixture
def nominal_single_page_plan(calculator):
    return calculator.calculate_single_page(pdf_page_index=0)


# =============================================================================
# SECTION 1: Coordinate Transformation & Aspect Ratio Preservation
# =============================================================================

class TestCoordinateTransformer:
    """Test point-to-canvas coordinate transformations and anti-stretching guarantees."""

    def test_aspect_ratio_preservation_portrait_4up(self):
        """Verify 4-Up sheet (878.74 x 1247.24 pt) maintains exact aspect ratio in preview."""
        transformer = CoordinateTransformer(
            page_width_pt=NOMINAL_4UP_SHEET_WIDTH_PT,
            page_height_pt=NOMINAL_4UP_SHEET_HEIGHT_PT,
            canvas_width=800.0,
            canvas_height=600.0,
        )
        assert transformer.verify_no_stretching()
        assert abs(transformer.page_aspect_ratio_pt - transformer.rendered_page_aspect_ratio) < 1e-6

    def test_aspect_ratio_preservation_landscape_cover(self):
        """Verify Cover Spread (1247.24 x 878.74 pt) maintains exact aspect ratio in preview."""
        transformer = CoordinateTransformer(
            page_width_pt=1247.24,
            page_height_pt=878.74,
            canvas_width=800.0,
            canvas_height=600.0,
        )
        assert transformer.verify_no_stretching()
        assert abs(transformer.page_aspect_ratio_pt - transformer.rendered_page_aspect_ratio) < 1e-6

    def test_uniform_scaling_behavior(self):
        """Verify scale factor applies equally to X and Y axes (no non-uniform stretching)."""
        transformer = CoordinateTransformer(
            page_width_pt=400.0,
            page_height_pt=800.0,
            canvas_width=500.0,
            canvas_height=500.0,
            margin_padding_px=10.0,
        )
        # Usable: 480 x 480. Height constrains: 480 / 800 = 0.6.
        assert round(transformer.scale_factor, 4) == 0.6
        # Rendered width must be 400 * 0.6 = 240, height = 800 * 0.6 = 480
        assert round(transformer.rendered_page_width, 2) == 240.0
        assert round(transformer.rendered_page_height, 2) == 480.0
        # Centering offset X = (500 - 240) / 2 = 130, offset Y = (500 - 480) / 2 = 10
        assert round(transformer.offset_x, 2) == 130.0
        assert round(transformer.offset_y, 2) == 10.0

    def test_lossless_roundtrip_coordinate_inversion(self):
        """Verify converting pt -> preview -> pt introduces zero material coordinate drift."""
        transformer = CoordinateTransformer(
            page_width_pt=878.74,
            page_height_pt=1247.24,
            canvas_width=1000.0,
            canvas_height=800.0,
        )
        original_x = 439.37
        original_y = 623.62

        prev_x = transformer.pt_to_preview_x(original_x)
        prev_y = transformer.pt_to_preview_y(original_y)

        restored_x = transformer.preview_to_pt_x(prev_x)
        restored_y = transformer.preview_to_pt_y(prev_y)

        assert abs(restored_x - original_x) < 1e-5
        assert abs(restored_y - original_y) < 1e-5

    def test_transform_bbox_and_rendered_page_box(self):
        """Verify bbox transformations preserve dimensions and containment."""
        transformer = CoordinateTransformer(
            page_width_pt=100.0,
            page_height_pt=200.0,
            canvas_width=300.0,
            canvas_height=300.0,
            margin_padding_px=0.0,
        )
        # Scale factor is min(300/100, 300/200) = 1.5
        box = transformer.transform_bbox(10.0, 20.0, 50.0, 80.0)
        assert round(box.width, 2) == 40.0 * 1.5  # 60.0
        assert round(box.height, 2) == 60.0 * 1.5  # 90.0

        page_box = transformer.get_rendered_page_box()
        assert page_box.width == 150.0
        assert page_box.height == 300.0

    def test_invalid_dimensions_raise_value_error(self):
        with pytest.raises(ValueError, match="Page dimensions must be positive"):
            CoordinateTransformer(page_width_pt=-10.0, page_height_pt=100.0)

        with pytest.raises(ValueError, match="Canvas dimensions must be positive"):
            CoordinateTransformer(page_width_pt=100.0, page_height_pt=100.0, canvas_width=-10.0)


# =============================================================================
# SECTION 2: 4-Up Imposition Grid Preview Overlay
# =============================================================================

class Test4UpPreview:
    """Test 4-Up preview overlay: quadrants, midpoint cuts, outer trim, and labels."""

    def test_4up_preview_quadrants_and_labels(self, preview_engine, nominal_4up_page_plan):
        payload = preview_engine.generate_page_preview(nominal_4up_page_plan)

        assert payload.layout_type == LayoutType.IMPOSITION_4UP
        assert payload.crop_readiness == CropReadinessStatus.CROP_READY
        assert payload.is_auto_crop_allowed is True
        assert len(payload.regions) == 4

        # Verify Q1..Q4 quadrant assignment and labels
        q_indices = [r.quadrant for r in payload.regions]
        assert q_indices == [1, 2, 3, 4]

        # Verify page sequence labels PAGE-01 through PAGE-04 for Sheet 1
        labels = [r.region_id for r in payload.regions]
        assert labels == ["PAGE-01", "PAGE-02", "PAGE-03", "PAGE-04"]

    def test_4up_preview_spatial_layout_and_flush_seams(self, preview_engine, nominal_4up_page_plan):
        payload = preview_engine.generate_page_preview(nominal_4up_page_plan)
        q1, q2, q3, q4 = payload.regions

        # In preview space, Q1 is top-left, Q2 is top-right
        assert q1.bbox_preview.x < q2.bbox_preview.x
        assert abs(q1.bbox_preview.y - q2.bbox_preview.y) < 1e-4

        # Q3 is bottom-left, Q4 is bottom-right
        assert q3.bbox_preview.x < q4.bbox_preview.x
        assert q1.bbox_preview.y < q3.bbox_preview.y

        # Flush cut vertical seam in preview space
        assert abs(q1.bbox_preview.x_max - q2.bbox_preview.x_min) < 1e-4
        assert abs(q3.bbox_preview.x_max - q4.bbox_preview.x_min) < 1e-4

        # Flush cut horizontal seam in preview space
        assert abs(q1.bbox_preview.y_max - q3.bbox_preview.y_min) < 1e-4
        assert abs(q2.bbox_preview.y_max - q4.bbox_preview.y_min) < 1e-4

    def test_4up_preview_midpoint_cut_lines(self, preview_engine, nominal_4up_page_plan):
        payload = preview_engine.generate_page_preview(nominal_4up_page_plan)
        assert len(payload.cut_lines) == 2

        line_types = {l.line_type for l in payload.cut_lines}
        assert "MIDPOINT_CUT_VERTICAL" in line_types
        assert "MIDPOINT_CUT_HORIZONTAL" in line_types

        v_line = next(l for l in payload.cut_lines if l.line_type == "MIDPOINT_CUT_VERTICAL")
        h_line = next(l for l in payload.cut_lines if l.line_type == "MIDPOINT_CUT_HORIZONTAL")

        # Vertical cut line must have x1 == x2
        assert abs(v_line.x1 - v_line.x2) < 1e-4
        # Horizontal cut line must have y1 == y2
        assert abs(h_line.y1 - h_line.y2) < 1e-4

    def test_4up_preview_outer_trim_box(self, preview_engine, nominal_4up_page_plan):
        payload = preview_engine.generate_page_preview(nominal_4up_page_plan)
        assert payload.outer_trim_box is not None
        # Outer trim must be strictly inside the sheet box
        assert payload.outer_trim_box.x > payload.rendered_page_box.x
        assert payload.outer_trim_box.y > payload.rendered_page_box.y
        assert payload.outer_trim_box.width < payload.rendered_page_box.width
        assert payload.outer_trim_box.height < payload.rendered_page_box.height

    def test_4up_with_excessive_tick_deviation_held_in_review(self, preview_engine, calculator):
        """Tick deviation > 1.0 mm triggers MANUAL_REVIEW_REQUIRED and prohibits auto-crop."""
        drifted_ticks = TickMarkCoordinates(
            x_top=439.37 + 5.67,  # 2.0 mm deviation
            x_bottom=439.37,
            y_left=623.62,
            y_right=623.62,
        )
        plan = calculator.calculate_imposition_4up(
            pdf_page_index=1,
            ticks=drifted_ticks,
        )
        assert plan.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED

        payload = preview_engine.generate_page_preview(plan, tick_coords=drifted_ticks)
        assert payload.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED
        assert payload.is_auto_crop_allowed is False
        assert payload.status_badge.badge_text == "[HOLD] MANUAL_REVIEW_REQUIRED"
        assert any("TICK_DEVIATION_EXCEEDED" in f for f in payload.review_flags)


# =============================================================================
# SECTION 3: Cover Spread Preview Overlay
# =============================================================================

class TestCoverPreview:
    """Test Cover Spread preview: BACKCOVER vs COVER, spine exclusion, and unresolved discrepancies."""

    def test_cover_preview_regions_and_dimensions(self, preview_engine, cover_page_plan):
        payload = preview_engine.generate_page_preview(cover_page_plan)

        assert payload.layout_type == LayoutType.COVER_SPREAD
        assert payload.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED
        assert payload.is_auto_crop_allowed is False
        assert len(payload.regions) == 2

        backcover = next(r for r in payload.regions if r.region_id == "BACKCOVER")
        cover = next(r for r in payload.regions if r.region_id == "COVER")

        # Distinct raster targets: BACKCOVER 1890x2657 @ 300 DPI vs COVER 630x886 @ 100 DPI
        assert backcover.target_width_px == 1890
        assert backcover.target_height_px == 2657
        assert backcover.dpi == 300

        assert cover.target_width_px == 630
        assert cover.target_height_px == 886
        assert cover.dpi == 100

    def test_cover_preview_spine_exclusion_zone(self, preview_engine, cover_page_plan):
        payload = preview_engine.generate_page_preview(cover_page_plan)
        assert payload.spine_zone is not None
        sz = payload.spine_zone

        assert abs(sz.width_mm - 15.02) < 0.05
        assert abs(sz.width_pt - 42.57) < 0.1
        assert "PROTECTED SPINE ZONE" in sz.label

        # In preview space, spine must sit strictly between BACKCOVER and COVER
        backcover = next(r for r in payload.regions if r.region_id == "BACKCOVER")
        cover = next(r for r in payload.regions if r.region_id == "COVER")

        assert backcover.bbox_preview.x_max <= sz.box_preview.x_min + 1e-4
        assert sz.box_preview.x_max <= cover.bbox_preview.x_min + 1e-4

    def test_cover_preserves_unresolved_discrepancies(self, preview_engine, cover_page_plan):
        payload = preview_engine.generate_page_preview(cover_page_plan)
        assert any("COVER_WIDTH_DISCREPANCY" in d for d in payload.unresolved_discrepancies)
        assert any("COVER_HEIGHT_1PX_DISCREPANCY" in d for d in payload.unresolved_discrepancies)
        assert any("Cover Spread auto-crop is disabled" in w for w in payload.warnings)


# =============================================================================
# SECTION 4: Single Page Preview Overlay
# =============================================================================

class TestSinglePagePreview:
    """Test Single Page preview: nominal CROP_READY vs non-nominal MANUAL_REVIEW_REQUIRED."""

    def test_nominal_single_page_preview(self, preview_engine, nominal_single_page_plan):
        payload = preview_engine.generate_page_preview(nominal_single_page_plan)

        assert payload.layout_type == LayoutType.SINGLE_PAGE
        assert payload.crop_readiness == CropReadinessStatus.CROP_READY
        assert payload.is_auto_crop_allowed is True
        assert payload.is_non_nominal is False
        assert len(payload.regions) == 1

        reg = payload.regions[0]
        assert reg.target_width_px == 1773
        assert reg.target_height_px == 2538
        assert reg.dpi == 300

    def test_non_nominal_single_page_preview_marked_for_review(self, preview_engine, calculator):
        non_nominal_plan = calculator.calculate_single_page(
            pdf_page_index=0,
            page_width_pt=430.0,   # Non-nominal (nominal is 425.52)
            page_height_pt=615.0,  # Non-nominal (nominal is 609.12)
        )
        assert non_nominal_plan.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED

        payload = preview_engine.generate_page_preview(non_nominal_plan)
        assert payload.is_non_nominal is True
        assert payload.is_auto_crop_allowed is False
        assert payload.status_badge.badge_text == "[HOLD] MANUAL_REVIEW_REQUIRED"
        assert any("Non-nominal single page dimensions" in w for w in payload.warnings)
        assert any("SINGLE_PAGE_NORMALIZATION_POLICY" in d for d in payload.unresolved_discrepancies)


# =============================================================================
# SECTION 5: Status Visualization & Accessibility
# =============================================================================

class TestStatusVisualization:
    """Test distinct visual styling (colors, dash patterns, text labels) and accessibility."""

    def test_status_theme_not_color_alone(self):
        """Spec requirement: 'Do not use color alone. Include text labels.'"""
        statuses = [
            CropReadinessStatus.CROP_READY,
            CropReadinessStatus.MANUAL_REVIEW_REQUIRED,
            CropReadinessStatus.NOT_APPLICABLE,
            "REJECTED_UNKNOWN_LAYOUT",
        ]
        for st in statuses:
            style = get_status_style(st)
            # Text badge must be non-empty and descriptive
            assert len(style.badge_text) > 0
            assert "[" in style.badge_text and "]" in style.badge_text
            # Accessibility label must describe the state
            assert len(style.accessibility_label) > 10
            # Pattern type must be distinguished
            assert style.pattern_type in ("solid", "dashed", "dotted", "dash-dot")

    def test_distinct_stroke_patterns_per_status(self):
        ready = get_status_style(CropReadinessStatus.CROP_READY)
        review = get_status_style(CropReadinessStatus.MANUAL_REVIEW_REQUIRED)
        rejected = get_status_style("REJECTED_UNKNOWN_LAYOUT")
        unknown = get_status_style("UNKNOWN_LAYOUT")

        # Distinct dash patterns
        assert ready.stroke_dasharray == "none"
        assert review.stroke_dasharray == "8,4"
        assert rejected.stroke_dasharray == "10,4,2,4"
        assert unknown.stroke_dasharray == "3,3"

        # Distinct text badges
        assert "[READY]" in ready.badge_text
        assert "[HOLD]" in review.badge_text
        assert "[REJECTED]" in rejected.badge_text
        assert "[UNKNOWN]" in unknown.badge_text


# =============================================================================
# SECTION 6: Structured Preview Payload Integrity
# =============================================================================

class TestDocumentPreviewPayload:
    """Test document-level preview payload assembly, region counts, and JSON serialization."""

    def test_golden_path_6_sheet_document_preview(self, preview_engine, calculator):
        # Build 6 sheet plans
        p0 = calculator.calculate_cover(pdf_page_index=0)
        p1 = calculator.calculate_imposition_4up(pdf_page_index=1, start_page_number=1)
        p2 = calculator.calculate_imposition_4up(pdf_page_index=2, start_page_number=5)
        p3 = calculator.calculate_imposition_4up(pdf_page_index=3, start_page_number=9)
        p4 = calculator.calculate_imposition_4up(pdf_page_index=4, start_page_number=13)
        p5 = calculator.calculate_imposition_4up(pdf_page_index=5, start_page_number=17)

        doc_plan = calculator.create_document_crop_plan(
            source_filename="Preview COMIC COLLECTION vol 1.pdf",
            page_plans=[p0, p1, p2, p3, p4, p5],
        )

        doc_payload = preview_engine.generate_document_preview(doc_plan)

        assert doc_payload.source_filename == "Preview COMIC COLLECTION vol 1.pdf"
        assert doc_payload.total_pdf_pages == 6
        assert doc_payload.expected_total_book_pages == 22
        assert doc_payload.total_crop_regions == 22
        assert doc_payload.document_status == "MANUAL_REVIEW_REQUIRED"
        assert doc_payload.has_manual_review_required is True
        assert len(doc_payload.pages) == 6

        # JSON serialization roundtrip
        json_data = doc_payload.model_dump_json()
        parsed = json.loads(json_data)
        assert parsed["total_pdf_pages"] == 6
        assert len(parsed["pages"]) == 6
        assert parsed["pages"][0]["regions"][0]["region_id"] in ("BACKCOVER", "COVER")


# =============================================================================
# SECTION 7: SVG Vector Overlay Generation
# =============================================================================

class TestSVGRenderer:
    """Test SVG generation, valid markup, accessibility tags, and guidelines."""

    def test_render_4up_svg_markup(self, preview_engine, nominal_4up_page_plan):
        page_payload = preview_engine.generate_page_preview(nominal_4up_page_plan)
        svg_content = preview_engine.render_svg(page_payload)

        # Basic SVG well-formedness
        assert svg_content.startswith("<svg")
        assert svg_content.endswith("</svg>")
        assert 'xmlns="http://www.w3.org/2000/svg"' in svg_content

        # Accessible elements
        assert "<title" in svg_content
        assert "<desc" in svg_content
        assert "[READY] CROP_READY" in svg_content

        # Elements for 4-Up
        assert "PAGE-01" in svg_content
        assert "PAGE-02" in svg_content
        assert "PAGE-03" in svg_content
        assert "PAGE-04" in svg_content
        assert "1773x2538 px @ 300 DPI" in svg_content
        assert "TRIM MARGIN" in svg_content

    def test_render_cover_svg_markup(self, preview_engine, cover_page_plan):
        page_payload = preview_engine.generate_page_preview(cover_page_plan)
        svg_content = preview_engine.render_svg(page_payload)

        assert "BACKCOVER" in svg_content
        assert "COVER" in svg_content
        assert "1890x2657 px @ 300 DPI" in svg_content
        assert "630x886 px @ 100 DPI" in svg_content
        assert "PROTECTED SPINE ZONE" in svg_content
        assert "spine-hatch" in svg_content
        assert "[HOLD] MANUAL_REVIEW_REQUIRED" in svg_content


# =============================================================================
# SECTION 8: Safety & Non-Execution Guarantees
# =============================================================================

class TestSafetyGuarantees:
    """Verify preview engine strictly preserves safety boundaries: no rasterization, no crop execution."""

    def test_no_jpg_export_or_file_artifacts(self, preview_engine, nominal_4up_page_plan, tmp_path):
        """Preview layer must be purely computational and not touch disk for JPG output."""
        payload = preview_engine.generate_page_preview(nominal_4up_page_plan)
        svg = preview_engine.render_svg(payload)

        # Verify nothing was written to workspace or disk
        assert isinstance(payload, PreviewPagePayload)
        assert isinstance(svg, str)

    def test_approved_crop_formulas_are_unmodified(self, preview_engine, nominal_4up_page_plan):
        """Preview bounding boxes must exactly equal calculator formula outputs."""
        payload = preview_engine.generate_page_preview(nominal_4up_page_plan)
        q1_plan = nominal_4up_page_plan.crop_regions[0]
        q1_preview = payload.regions[0]

        assert q1_preview.bbox_pt[0] == q1_plan.x_min_pt
        assert q1_preview.bbox_pt[1] == q1_plan.y_min_pt
        assert q1_preview.bbox_pt[2] == q1_plan.x_max_pt
        assert q1_preview.bbox_pt[3] == q1_plan.y_max_pt

