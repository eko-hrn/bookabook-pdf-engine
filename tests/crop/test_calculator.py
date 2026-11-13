"""Unit tests for Phase 1.2.2.2 — Crop Coordinate Calculator.

Tests cover:
1. Unit conversions and precision (points, pixels, millimeters)
2. Image stretching prevention and aspect ratio validation
3. CoverCropStrategy (BACKCOVER vs COVER, spine exclusion, safety hold)
4. Imposition4UpCropStrategy (midpoint tick anchors, 1.0 mm tolerance, Q1-Q4 formulas)
5. SinglePageCropStrategy (nominal validation, non-nominal hold, bleed trim)
6. Unified CropCoordinateCalculator (dispatching, document plan assembly, validation)
7. Coordinate boundary enforcement and missing coordinate safety
"""

from __future__ import annotations

import pytest

from app.crop.calculator import (
    ALL_UNRESOLVED_DECISIONS,
    CoverCropMarks,
    CoverCropStrategy,
    CropCoordinateCalculator,
    DEFAULT_COVER_BOTTOM_TRIM_PT,
    DEFAULT_COVER_LEFT_TRIM_PT,
    DEFAULT_COVER_RIGHT_TRIM_PT,
    DEFAULT_COVER_SPINE_INNER_LEFT_PT,
    DEFAULT_COVER_SPINE_INNER_RIGHT_PT,
    DEFAULT_COVER_TOP_TRIM_PT,
    Imposition4UpCropStrategy,
    NOMINAL_4UP_HALF_HEIGHT_PT,
    NOMINAL_4UP_HALF_WIDTH_PT,
    NOMINAL_4UP_SHEET_HEIGHT_PT,
    NOMINAL_4UP_SHEET_WIDTH_PT,
    NOMINAL_SINGLE_PAGE_HEIGHT_PT,
    NOMINAL_SINGLE_PAGE_WIDTH_PT,
    SinglePageCropStrategy,
    TickMarkCoordinates,
    UNRESOLVED_COVER_WIDTH_DISCREPANCY,
    UNRESOLVED_ROUNDING_1PX,
    UNRESOLVED_SINGLE_PAGE_NORMALIZATION_POLICY,
    check_tick_deviation,
    mm_to_points,
    pixels_to_points,
    points_to_mm,
    points_to_pixels,
    validate_bounding_box,
    validate_no_stretching,
)
from app.crop.models.crop_validation import CropValidationResult
from app.crop.models.enums import (
    BlankPageStatus,
    ClassificationStatus,
    CropReadinessStatus,
    CropStrategyType,
    LayoutType,
    ManualReviewFlag,
    Orientation,
)
from app.crop.profiles.profile_configs import (
    create_cover_profile,
    create_default_profile,
    create_imposition_4up_profile,
    create_single_page_profile,
)


# =============================================================================
# SECTION 1: Unit Conversion & Geometric Validation Tests
# =============================================================================

class TestUnitConversions:
    """Test point, pixel, and millimeter conversions per Spec §8, §15, §17."""

    def test_points_to_pixels_content_exact(self):
        """Spec §8.B.2: 425.52 x 609.12 pt @ 300 DPI = 1773 x 2538 px exact."""
        assert points_to_pixels(425.52, 300) == 1773
        assert points_to_pixels(609.12, 300) == 2538

    def test_points_to_pixels_cover_back_300dpi(self):
        """Spec §8.A.2: 453.60 pt @ 300 DPI = 1890 px exact."""
        assert points_to_pixels(453.60, 300) == 1890

    def test_points_to_pixels_cover_front_100dpi(self):
        """Spec §8.A.2: 453.60 pt @ 100 DPI = 630 px exact."""
        assert points_to_pixels(453.60, 100) == 630

    def test_points_to_pixels_height_renderings(self):
        """Spec §8.A.2: 637.76068 pt renders to 2657 px @ 300 DPI and 886 px @ 100 DPI."""
        assert points_to_pixels(637.76068, 300) == 2657
        assert points_to_pixels(637.76068, 100) == 886

    def test_pixels_to_points_roundtrip(self):
        """Verify pixels to points inversion."""
        assert pixels_to_points(1773, 300) == 425.52
        assert pixels_to_points(2538, 300) == 609.12
        assert pixels_to_points(1890, 300) == 453.60
        assert pixels_to_points(630, 100) == 453.60

    def test_inverse_conversion_lossless_for_content_targets(self):
        """CHECK 3: Verify bidirectional point-pixel-point conversion introduces zero material drift."""
        # Content width 425.52 pt <-> 1773 px @ 300 DPI
        px_w = points_to_pixels(425.52, 300)
        pt_w = pixels_to_points(px_w, 300)
        assert px_w == 1773
        assert pt_w == 425.52

        # Content height 609.12 pt <-> 2538 px @ 300 DPI
        px_h = points_to_pixels(609.12, 300)
        pt_h = pixels_to_points(px_h, 300)
        assert px_h == 2538
        assert pt_h == 609.12

        # Backcover width 453.60 pt <-> 1890 px @ 300 DPI
        px_bw = points_to_pixels(453.60, 300)
        pt_bw = pixels_to_points(px_bw, 300)
        assert px_bw == 1890
        assert pt_bw == 453.60

        # Cover width 453.60 pt <-> 630 px @ 100 DPI
        px_cw = points_to_pixels(453.60, 100)
        pt_cw = pixels_to_points(px_cw, 100)
        assert px_cw == 630
        assert pt_cw == 453.60

    def test_mm_to_points_tolerance(self):
        """Spec §6.B: 1.0 mm = 2.835 pt."""
        pt = mm_to_points(1.0)
        assert abs(pt - 2.8346) < 0.001

    def test_points_to_mm_reconciliation(self):
        """Spec §17: 13.85 pt ≈ 4.886 mm, 14.50 pt ≈ 5.115 mm."""
        assert abs(points_to_mm(13.85) - 4.886) < 0.002
        assert abs(points_to_mm(14.50) - 5.115) < 0.002

    def test_invalid_dpi_raises(self):
        """DPI must be positive."""
        with pytest.raises(ValueError):
            points_to_pixels(100.0, 0)
        with pytest.raises(ValueError):
            pixels_to_points(100, -10)


class TestNoImageStretching:
    """Test requirement: Never stretch images."""

    def test_aspect_ratio_match_4up_content(self):
        """425.52 x 609.12 pt matches 1773 x 2538 px exactly."""
        is_valid, distortion = validate_no_stretching(425.52, 609.12, 1773, 2538, dpi=300)
        assert is_valid
        assert distortion < 0.001

    def test_aspect_ratio_mismatch_detected(self):
        """Stretched dimensions must be detected and flagged."""
        # 425.52 x 500 pt forced into 1773 x 2538 px
        is_valid, distortion = validate_no_stretching(425.52, 500.0, 1773, 2538, dpi=300)
        assert not is_valid
        assert distortion > 15.0

    def test_negative_dimensions_raise(self):
        """Negative or zero dimensions raise ValueError."""
        with pytest.raises(ValueError):
            validate_no_stretching(-10.0, 609.12, 1773, 2538)
        with pytest.raises(ValueError):
            validate_no_stretching(425.52, 609.12, 0, 2538)


class TestBoundingBoxValidation:
    """Test bounding box coordinate boundary rules."""

    def test_valid_box(self):
        errors = validate_bounding_box(10.0, 10.0, 100.0, 200.0, 500.0, 500.0)
        assert not errors

    def test_inverted_x_fails(self):
        errors = validate_bounding_box(100.0, 10.0, 50.0, 200.0, 500.0, 500.0)
        assert any("x_max" in e and "greater than x_min" in e for e in errors)

    def test_negative_y_fails(self):
        errors = validate_bounding_box(10.0, -5.0, 100.0, 200.0, 500.0, 500.0)
        assert any("y_min" in e and "negative" in e for e in errors)

    def test_exceeds_page_bounds_fails(self):
        errors = validate_bounding_box(10.0, 10.0, 600.0, 200.0, 500.0, 500.0)
        assert any("exceeds page width" in e for e in errors)


# =============================================================================
# SECTION 2: CoverCropStrategy Tests
# =============================================================================

class TestCoverCropStrategy:
    """Test CoverCropStrategy implementation per Spec §8.A, §8.B.1, §14.A.4, §17."""

    def test_default_observed_coordinates_and_dimensions(self):
        """Test calculation with default observed Bookabook Page 1 coordinates."""
        strategy = CoverCropStrategy()
        plan = strategy.calculate(
            pdf_page_index=0,
            page_width_pt=1247.24,
            page_height_pt=878.74,
            rotation=0,
        )

        assert plan.layout_type == LayoutType.COVER_SPREAD
        assert plan.crop_strategy == CropStrategyType.COVER
        assert plan.expected_page_yield == 2
        assert len(plan.crop_regions) == 2

        backcover = plan.crop_regions[0]
        cover = plan.crop_regions[1]

        # Verify region identities
        assert backcover.region_id == "BACKCOVER"
        assert cover.region_id == "COVER"

        # Verify distinct dimensions: BACKCOVER (1890x2657 @ 300 DPI) vs COVER (630x886 @ 100 DPI)
        assert backcover.target_width_px == 1890
        assert backcover.target_height_px == 2657
        assert cover.target_width_px == 630
        assert cover.target_height_px == 886

        # Verify bounding box coordinates match Spec §8.A.1, §17
        assert abs(backcover.x_min_pt - DEFAULT_COVER_LEFT_TRIM_PT) < 0.001
        assert abs(backcover.x_max_pt - DEFAULT_COVER_SPINE_INNER_LEFT_PT) < 0.001
        assert abs(backcover.y_min_pt - DEFAULT_COVER_TOP_TRIM_PT) < 0.001
        assert abs(backcover.y_max_pt - DEFAULT_COVER_BOTTOM_TRIM_PT) < 0.001

        assert abs(cover.x_min_pt - DEFAULT_COVER_SPINE_INNER_RIGHT_PT) < 0.001
        assert abs(cover.x_max_pt - DEFAULT_COVER_RIGHT_TRIM_PT) < 0.001
        assert abs(cover.y_min_pt - DEFAULT_COVER_TOP_TRIM_PT) < 0.001
        assert abs(cover.y_max_pt - DEFAULT_COVER_BOTTOM_TRIM_PT) < 0.001

    def test_spine_zone_is_strictly_excluded(self):
        """Spec §8.B.1: Spine zone (15.02 mm / 42.57 pt) must be excluded between covers."""
        strategy = CoverCropStrategy()
        plan = strategy.calculate(pdf_page_index=0)

        backcover = plan.crop_regions[0]
        cover = plan.crop_regions[1]

        # Gap between backcover right edge and frontcover left edge is the spine
        spine_gap_pt = cover.x_min_pt - backcover.x_max_pt
        assert spine_gap_pt > 0
        assert abs(spine_gap_pt - 42.592) < 0.01  # 651.109 - 608.517 pt

        # Spine zone is not inside either crop box
        assert abs(backcover.x_max_pt - DEFAULT_COVER_SPINE_INNER_LEFT_PT) < 1e-4
        assert abs(cover.x_min_pt - DEFAULT_COVER_SPINE_INNER_RIGHT_PT) < 1e-4

    def test_cover_always_manual_review_required(self):
        """Spec §8.B.1, §15.A.6: Auto-crop is NEVER permitted for cover.
        Status must always be MANUAL_REVIEW_REQUIRED.
        """
        strategy = CoverCropStrategy()
        plan = strategy.calculate(pdf_page_index=0)

        assert plan.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED
        assert ManualReviewFlag.COVER_FORMULA_UNVALIDATED in plan.manual_review_flags

    def test_cover_rotation_triggers_review_flag(self):
        """Non-zero rotation adds ROTATED_SHEET_DETECTED."""
        strategy = CoverCropStrategy()
        plan = strategy.calculate(pdf_page_index=0, rotation=90)

        assert plan.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED
        assert ManualReviewFlag.COVER_FORMULA_UNVALIDATED in plan.manual_review_flags
        assert ManualReviewFlag.ROTATED_SHEET_DETECTED in plan.manual_review_flags

    def test_cover_custom_crop_marks(self):
        """Test calculation with custom valid crop marks."""
        custom_marks = CoverCropMarks(
            x_left=150.0,
            x_spine_left=600.0,
            x_spine_right=645.0,
            x_right=1095.0,
            y_top=100.0,
            y_bottom=740.0,
        )
        strategy = CoverCropStrategy()
        plan = strategy.calculate(pdf_page_index=0, marks=custom_marks)

        assert plan.crop_regions[0].x_min_pt == 150.0
        assert plan.crop_regions[0].x_max_pt == 600.0
        assert plan.crop_regions[1].x_min_pt == 645.0
        assert plan.crop_regions[1].x_max_pt == 1095.0

    def test_cover_anchor_to_target_width_mode(self):
        """Test anchor_to_target_width=True uses exact 453.60 pt from spine creases."""
        strategy = CoverCropStrategy()
        plan = strategy.calculate(pdf_page_index=0, anchor_to_target_width=True)

        back = plan.crop_regions[0]
        front = plan.crop_regions[1]

        # Width should be exact designer target (453.60 pt)
        assert abs(back.width_pt - 453.60) < 0.001
        assert abs(front.width_pt - 453.60) < 0.001

    def test_cover_invalid_crop_marks_raise(self):
        """Inverted or negative crop mark coordinates raise ValueError."""
        # x_spine_left >= x_spine_right (no spine)
        bad_marks = CoverCropMarks(x_spine_left=650.0, x_spine_right=600.0)
        strategy = CoverCropStrategy()
        with pytest.raises(ValueError):
            strategy.calculate(pdf_page_index=0, marks=bad_marks)

    def test_cover_missing_marks_on_non_standard_sheet_raises(self):
        """Rule: Never invent missing coordinates.
        Non-standard sheet without explicit marks must raise ValueError.
        """
        strategy = CoverCropStrategy()
        with pytest.raises(ValueError, match=r"Never invent missing coordinates"):
            strategy.calculate(
                pdf_page_index=0,
                page_width_pt=1000.0,  # Non-standard
                page_height_pt=700.0,
                marks=None,
            )

    def test_cover_unresolved_decisions_accessible(self):
        """Verify unresolved decision documentation is accessible."""
        assert "COVER_HEIGHT_1PX_DISCREPANCY" in UNRESOLVED_ROUNDING_1PX
        assert "COVER_WIDTH_DISCREPANCY" in UNRESOLVED_COVER_WIDTH_DISCREPANCY
        assert "UNRESOLVED_ROUNDING_1PX" in ALL_UNRESOLVED_DECISIONS

    def test_cover_geometry_discrepancy_reconciliation(self):
        """CHECK 2: Verify exact mathematical discrepancies between observed vector marks and designer targets.

        Spec §8.A, §16 Item 1-2, §17:
        - Backcover target width: 1890 px @ 300 DPI = 453.60 pt.
          Observed vector width: 608.51709 - 155.95461 = 452.56248 pt (Δ = -1.03752 pt ≈ -1.01 pt).
        - Frontcover target width: 1890 px @ 300 DPI / 630 px @ 100 DPI = 453.60 pt.
          Observed vector width: 1105.61914 - 651.10938 = 454.50976 pt (Δ = +0.90976 pt ≈ +0.91 pt).
        - Front vs Back asymmetry: 454.50976 - 452.56248 = 1.94728 pt ≈ 1.92 pt (0.68 mm).
        - Vector height: 758.25067 - 120.48999 = 637.76068 pt.
          Renders to 2657 px @ 300 DPI (round(637.76068 * 300 / 72) = 2657 px).
          Renders to 886 px @ 100 DPI (round(637.76068 * 100 / 72) = 886 px).
          3x integer scaling of 886 px = 2658 px (1 px discrepancy, status UNRESOLVED_ROUNDING_1PX).
        - Auto-crop is ALWAYS prohibited; no implicit scaling or coordinates adjustment is applied.
        """
        marks = CoverCropMarks()
        assert abs(marks.backcover_vector_width_pt - 452.562) < 0.01
        assert abs(marks.frontcover_vector_width_pt - 454.510) < 0.01
        assert abs(marks.vector_height_pt - 637.761) < 0.01
        assert abs(marks.spine_width_pt - 42.592) < 0.01

        # Calculate with default strategy
        strategy = CoverCropStrategy()
        plan = strategy.calculate(pdf_page_index=0)

        # Ensure no implicit adjustment altered the bounding boxes
        back_reg = plan.crop_regions[0]
        front_reg = plan.crop_regions[1]

        assert abs(back_reg.width_pt - marks.backcover_vector_width_pt) < 1e-4
        assert abs(front_reg.width_pt - marks.frontcover_vector_width_pt) < 1e-4
        assert abs(back_reg.height_pt - marks.vector_height_pt) < 1e-4
        assert abs(front_reg.height_pt - marks.vector_height_pt) < 1e-4

        # Enforce auto-crop is disabled
        assert plan.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED
        assert ManualReviewFlag.COVER_FORMULA_UNVALIDATED in plan.manual_review_flags


# =============================================================================
# SECTION 3: Imposition4UpCropStrategy Tests
# =============================================================================

class TestImposition4UpCropStrategy:
    """Test Imposition4UpCropStrategy per Spec §6.B, §8.B.2, §10.A, §17."""

    def test_ideal_midpoint_ticks_exact_formulas(self):
        """Spec §8.B.2, §17: On standard sheet (878.74 x 1247.24 pt),
        midpoints (439.37, 623.62 pt) produce exact quadrant bounding boxes.
        """
        strategy = Imposition4UpCropStrategy()
        plan = strategy.calculate(
            pdf_page_index=1,
            page_width_pt=NOMINAL_4UP_SHEET_WIDTH_PT,
            page_height_pt=NOMINAL_4UP_SHEET_HEIGHT_PT,
            rotation=0,
        )

        assert plan.layout_type == LayoutType.IMPOSITION_4UP
        assert plan.crop_strategy == CropStrategyType.IMPOSITION_4UP
        assert plan.crop_readiness == CropReadinessStatus.CROP_READY
        assert plan.manual_review_flags == []
        assert plan.expected_page_yield == 4
        assert len(plan.crop_regions) == 4

        q1, q2, q3, q4 = plan.crop_regions

        # Quadrant indices
        assert q1.quadrant == 1
        assert q2.quadrant == 2
        assert q3.quadrant == 3
        assert q4.quadrant == 4

        # Page numbering progression for page_index=1 (Pages 1..4)
        assert q1.region_id == "PAGE-01"
        assert q2.region_id == "PAGE-02"
        assert q3.region_id == "PAGE-03"
        assert q4.region_id == "PAGE-04"

        # Target dimensions: 1773 x 2538 px @ 300 DPI
        for q in [q1, q2, q3, q4]:
            assert q.target_width_px == 1773
            assert q.target_height_px == 2538
            assert abs(q.width_pt - 425.52) < 0.001
            assert abs(q.height_pt - 609.12) < 0.001

        # Spec §8.B.2 Exact Bounding Boxes:
        # Q1: [13.85, 14.50, 439.37, 623.62]
        assert abs(q1.x_min_pt - 13.85) < 0.01
        assert abs(q1.y_min_pt - 14.50) < 0.01
        assert abs(q1.x_max_pt - 439.37) < 0.01
        assert abs(q1.y_max_pt - 623.62) < 0.01

        # Q2: [439.37, 14.50, 864.89, 623.62]
        assert abs(q2.x_min_pt - 439.37) < 0.01
        assert abs(q2.y_min_pt - 14.50) < 0.01
        assert abs(q2.x_max_pt - 864.89) < 0.01
        assert abs(q2.y_max_pt - 623.62) < 0.01

        # Q3: [13.85, 623.62, 439.37, 1232.74]
        assert abs(q3.x_min_pt - 13.85) < 0.01
        assert abs(q3.y_min_pt - 623.62) < 0.01
        assert abs(q3.x_max_pt - 439.37) < 0.01
        assert abs(q3.y_max_pt - 1232.74) < 0.01

        # Q4: [439.37, 623.62, 864.89, 1232.74]
        assert abs(q4.x_min_pt - 439.37) < 0.01
        assert abs(q4.y_min_pt - 623.62) < 0.01
        assert abs(q4.x_max_pt - 864.89) < 0.01
        assert abs(q4.y_max_pt - 1232.74) < 0.01

    def test_tick_deviation_within_1mm_tolerance_is_crop_ready(self):
        """Spec §6.B: Deviation ≤ 1.0 mm (≈ 2.835 pt) is acceptable and CROP_READY."""
        delta_pt = mm_to_points(0.5)
        ticks = TickMarkCoordinates(
            x_top=NOMINAL_4UP_HALF_WIDTH_PT + delta_pt,
            x_bottom=NOMINAL_4UP_HALF_WIDTH_PT - delta_pt,
            y_left=NOMINAL_4UP_HALF_HEIGHT_PT,
            y_right=NOMINAL_4UP_HALF_HEIGHT_PT,
        )
        assert abs(ticks.delta_x_mm - 1.0) < 0.01

        strategy = Imposition4UpCropStrategy()
        plan = strategy.calculate(pdf_page_index=1, ticks=ticks)

        assert plan.crop_readiness == CropReadinessStatus.CROP_READY
        assert plan.manual_review_flags == []

    def test_tick_deviation_exceeding_1mm_triggers_manual_review(self):
        """Spec §6.B: Deviation > 1.0 mm MUST trigger MANUAL_REVIEW_REQUIRED with flag."""
        ticks = TickMarkCoordinates(
            x_top=NOMINAL_4UP_HALF_WIDTH_PT + mm_to_points(2.0),
            x_bottom=NOMINAL_4UP_HALF_WIDTH_PT,
            y_left=NOMINAL_4UP_HALF_HEIGHT_PT,
            y_right=NOMINAL_4UP_HALF_HEIGHT_PT,
        )
        assert ticks.delta_x_mm > 1.0

        strategy = Imposition4UpCropStrategy()
        plan = strategy.calculate(pdf_page_index=1, ticks=ticks)

        assert plan.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED
        assert ManualReviewFlag.TICK_DEVIATION_EXCEEDED in plan.manual_review_flags

    def test_vertical_tick_deviation_exceeding_1mm(self):
        """Vertical deviation > 1.0 mm also triggers hold."""
        ticks = TickMarkCoordinates(
            x_top=NOMINAL_4UP_HALF_WIDTH_PT,
            x_bottom=NOMINAL_4UP_HALF_WIDTH_PT,
            y_left=NOMINAL_4UP_HALF_HEIGHT_PT + mm_to_points(1.5),
            y_right=NOMINAL_4UP_HALF_HEIGHT_PT,
        )
        strategy = Imposition4UpCropStrategy()
        plan = strategy.calculate(pdf_page_index=1, ticks=ticks)

        assert plan.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED
        assert ManualReviewFlag.TICK_DEVIATION_EXCEEDED in plan.manual_review_flags

    def test_rotation_triggers_manual_review(self):
        """Spec §11 C-06: Non-zero rotation requires MANUAL_REVIEW_REQUIRED."""
        strategy = Imposition4UpCropStrategy()
        plan = strategy.calculate(pdf_page_index=1, rotation=270)

        assert plan.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED
        assert ManualReviewFlag.ROTATED_SHEET_DETECTED in plan.manual_review_flags

    def test_flipped_orientation_candidate(self):
        """Spec §6.A: Flipped orientation candidate triggers hold."""
        strategy = Imposition4UpCropStrategy()
        plan = strategy.calculate(pdf_page_index=1, is_flipped=True)

        assert plan.classification_status == ClassificationStatus.CANDIDATE_IMPOSITION_4UP_FLIPPED
        assert plan.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED
        assert ManualReviewFlag.FLIPPED_ORIENTATION_DETECTED in plan.manual_review_flags

    def test_page_numbering_progression_across_sheets(self):
        """Verify page numbering progression: Sheet 2 -> 1..4, Sheet 3 -> 5..8, Sheet 6 -> 17..20."""
        strategy = Imposition4UpCropStrategy()

        plan2 = strategy.calculate(pdf_page_index=1)
        assert [r.region_id for r in plan2.crop_regions] == [
            "PAGE-01", "PAGE-02", "PAGE-03", "PAGE-04"
        ]

        plan3 = strategy.calculate(pdf_page_index=2)
        assert [r.region_id for r in plan3.crop_regions] == [
            "PAGE-05", "PAGE-06", "PAGE-07", "PAGE-08"
        ]

        plan6 = strategy.calculate(pdf_page_index=5)
        assert [r.region_id for r in plan6.crop_regions] == [
            "PAGE-17", "PAGE-18", "PAGE-19", "PAGE-20"
        ]

    def test_blank_page_non_blocking_warning(self):
        """Spec §7.B, §14.B.3: Blank page status is attached to region but non-blocking."""
        blank_statuses = [
            BlankPageStatus.CONTENT_PRESENT,
            BlankPageStatus.CONTENT_PRESENT,
            BlankPageStatus.BLANK_PAGE_DETECTED,
            BlankPageStatus.CONTENT_PRESENT,
        ]
        strategy = Imposition4UpCropStrategy()
        plan = strategy.calculate(pdf_page_index=1, blank_statuses=blank_statuses)

        assert plan.crop_readiness == CropReadinessStatus.CROP_READY
        assert plan.crop_regions[2].blank_page_status == BlankPageStatus.BLANK_PAGE_DETECTED

    def test_missing_ticks_on_non_standard_sheet_raises(self):
        """Never invent missing coordinates: non-standard sheet without ticks raises."""
        strategy = Imposition4UpCropStrategy()
        with pytest.raises(ValueError, match=r"Never invent missing coordinates"):
            strategy.calculate(
                pdf_page_index=1,
                page_width_pt=900.0,
                page_height_pt=1300.0,
                ticks=None,
            )

    def test_4up_spatial_relationships_and_flush_cut_seams(self):
        """CHECK 1: Verify exact spatial alignment, PyMuPDF top-left convention, and flush interior seams.

        Spec §8.B.2:
        - PyMuPDF top-left origin: (0, 0) is top-left, +X right, +Y down.
        - Interior cut point (x_cut, y_cut) = (439.37, 623.62 pt).
        - Q1 is Top-Left (-X, -Y)
        - Q2 is Top-Right (+X, -Y)
        - Q3 is Bottom-Left (-X, +Y)
        - Q4 is Bottom-Right (+X, +Y)
        - Flush cut: zero margin between quadrants along x_cut and y_cut.
        - Discarded outer margins: exactly 13.85 pt horizontal (left & right) and 14.50 pt vertical (top & bottom).
        """
        strategy = Imposition4UpCropStrategy()
        plan = strategy.calculate(pdf_page_index=1)

        q1, q2, q3, q4 = plan.crop_regions

        # 1. Verify Top vs Bottom spatial ordering (+Y points downwards)
        assert q1.y_max_pt == q3.y_min_pt == 623.62
        assert q2.y_max_pt == q4.y_min_pt == 623.62
        assert q1.y_min_pt < q1.y_max_pt
        assert q3.y_min_pt < q3.y_max_pt

        # 2. Verify Left vs Right spatial ordering (+X points rightwards)
        assert q1.x_max_pt == q2.x_min_pt == 439.37
        assert q3.x_max_pt == q4.x_min_pt == 439.37
        assert q1.x_min_pt < q1.x_max_pt
        assert q2.x_min_pt < q2.x_max_pt

        # 3. Verify flush cut seams (zero gap between interior edges)
        h_seam_gap = q3.y_min_pt - q1.y_max_pt
        v_seam_gap = q2.x_min_pt - q1.x_max_pt
        assert h_seam_gap == 0.0
        assert v_seam_gap == 0.0

        # 4. Verify trimmed outer margins against sheet MediaBox [0, 0, 878.74, 1247.24]
        left_margin = q1.x_min_pt - 0.0
        right_margin = NOMINAL_4UP_SHEET_WIDTH_PT - q2.x_max_pt
        top_margin = q1.y_min_pt - 0.0
        bottom_margin = NOMINAL_4UP_SHEET_HEIGHT_PT - q3.y_max_pt

        assert abs(left_margin - 13.85) < 0.01
        assert abs(right_margin - 13.85) < 0.01
        assert abs(top_margin - 14.50) < 0.01
        assert abs(bottom_margin - 14.50) < 0.01


# =============================================================================
# SECTION 4: SinglePageCropStrategy Tests
# =============================================================================

class TestSinglePageCropStrategy:
    """Test SinglePageCropStrategy per Spec §8.B.3, §11 C-03..C-05, §17."""

    def test_nominal_dimensions_crop_ready(self):
        """Exact nominal 425.52 x 609.12 pt is CROP_READY."""
        strategy = SinglePageCropStrategy()
        plan = strategy.calculate(
            pdf_page_index=0,
            page_width_pt=NOMINAL_SINGLE_PAGE_WIDTH_PT,
            page_height_pt=NOMINAL_SINGLE_PAGE_HEIGHT_PT,
            rotation=0,
        )

        assert plan.layout_type == LayoutType.SINGLE_PAGE
        assert plan.crop_strategy == CropStrategyType.SINGLE_PAGE
        assert plan.crop_readiness == CropReadinessStatus.CROP_READY
        assert plan.manual_review_flags == []
        assert plan.expected_page_yield == 1
        assert len(plan.crop_regions) == 1

        reg = plan.crop_regions[0]
        assert reg.region_id == "PAGE-01"
        assert reg.quadrant is None
        assert reg.x_min_pt == 0.0
        assert reg.y_min_pt == 0.0
        assert reg.x_max_pt == NOMINAL_SINGLE_PAGE_WIDTH_PT
        assert reg.y_max_pt == NOMINAL_SINGLE_PAGE_HEIGHT_PT
        assert reg.target_width_px == 1773
        assert reg.target_height_px == 2538

    def test_non_nominal_dimensions_within_detection_window_requires_manual_review(self):
        """Spec §8.B.3, §11 C-03: Dimensions in 415-450 x 590-640 pt window
        must be MANUAL_REVIEW_REQUIRED until normalization policy is approved.
        """
        strategy = SinglePageCropStrategy()
        plan = strategy.calculate(
            pdf_page_index=0,
            page_width_pt=419.53,
            page_height_pt=595.28,
            rotation=0,
        )

        assert plan.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED
        assert ManualReviewFlag.NON_NOMINAL_DIMENSIONS_DETECTED in plan.manual_review_flags

    def test_sub_point_deviation_rejected_from_crop_ready(self):
        """No arbitrary production tolerance: 426.0 x 609.12 pt requires manual review."""
        strategy = SinglePageCropStrategy()
        plan = strategy.calculate(
            pdf_page_index=0,
            page_width_pt=426.0,
            page_height_pt=609.12,
            rotation=0,
        )

        assert plan.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED
        assert ManualReviewFlag.NON_NOMINAL_DIMENSIONS_DETECTED in plan.manual_review_flags

    def test_rotation_triggers_manual_review(self):
        """Non-zero rotation requires MANUAL_REVIEW_REQUIRED."""
        strategy = SinglePageCropStrategy()
        plan = strategy.calculate(
            pdf_page_index=0,
            page_width_pt=NOMINAL_SINGLE_PAGE_WIDTH_PT,
            page_height_pt=NOMINAL_SINGLE_PAGE_HEIGHT_PT,
            rotation=90,
        )

        assert plan.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED
        assert ManualReviewFlag.ROTATED_SHEET_DETECTED in plan.manual_review_flags

    def test_custom_crop_bbox_bleed_trim(self):
        """Test optional bleed trim with explicit crop_bbox_pt."""
        strategy = SinglePageCropStrategy()
        plan = strategy.calculate(
            pdf_page_index=0,
            page_width_pt=435.52,
            page_height_pt=619.12,
            crop_bbox_pt=(5.0, 5.0, 430.52, 614.12),
        )

        reg = plan.crop_regions[0]
        assert reg.x_min_pt == 5.0
        assert reg.y_min_pt == 5.0
        assert reg.x_max_pt == 430.52
        assert reg.y_max_pt == 614.12

    def test_invalid_bbox_raises(self):
        """Inverted or negative crop bounding box raises ValueError."""
        strategy = SinglePageCropStrategy()
        with pytest.raises(ValueError):
            strategy.calculate(
                pdf_page_index=0,
                crop_bbox_pt=(50.0, 10.0, 20.0, 200.0),
            )


# =============================================================================
# SECTION 5: Unified CropCoordinateCalculator & Document Plan Tests
# =============================================================================

class TestUnifiedCropCoordinateCalculator:
    """Test unified CropCoordinateCalculator coordinator."""

    def test_initialization_with_default_profile(self):
        calc = CropCoordinateCalculator()
        assert calc.profile.profile_id == "bookabook_comic_a5_default"

    def test_dispatch_cover(self):
        calc = CropCoordinateCalculator()
        plan = calc.calculate_for_layout(
            layout_type=LayoutType.COVER_SPREAD,
            pdf_page_index=0,
            page_width_pt=1247.24,
            page_height_pt=878.74,
        )
        assert plan.layout_type == LayoutType.COVER_SPREAD
        assert plan.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED

    def test_dispatch_imposition_4up(self):
        calc = CropCoordinateCalculator()
        plan = calc.calculate_for_layout(
            layout_type=LayoutType.IMPOSITION_4UP,
            pdf_page_index=1,
            page_width_pt=878.74,
            page_height_pt=1247.24,
        )
        assert plan.layout_type == LayoutType.IMPOSITION_4UP
        assert plan.crop_readiness == CropReadinessStatus.CROP_READY

    def test_dispatch_single_page(self):
        calc = CropCoordinateCalculator()
        plan = calc.calculate_for_layout(
            layout_type=LayoutType.SINGLE_PAGE,
            pdf_page_index=0,
            page_width_pt=NOMINAL_SINGLE_PAGE_WIDTH_PT,
            page_height_pt=NOMINAL_SINGLE_PAGE_HEIGHT_PT,
        )
        assert plan.layout_type == LayoutType.SINGLE_PAGE
        assert plan.crop_readiness == CropReadinessStatus.CROP_READY

    def test_dispatch_unknown_layout(self):
        calc = CropCoordinateCalculator()
        plan = calc.calculate_for_layout(
            layout_type=None,
            pdf_page_index=0,
            page_width_pt=500.0,
            page_height_pt=500.0,
        )
        assert plan.classification_status == ClassificationStatus.UNKNOWN_LAYOUT
        assert plan.crop_readiness == CropReadinessStatus.NOT_APPLICABLE
        assert plan.crop_strategy is None
        assert plan.expected_page_yield == 0
        assert plan.crop_regions == []

    def test_validate_plan_with_validation_results(self):
        """Test validate_plan generates valid CropValidationResult objects."""
        calc = CropCoordinateCalculator()
        plan = calc.calculate_imposition_4up(pdf_page_index=1)
        results = calc.validate_plan(plan, tick_deviation_x_mm=0.2, tick_deviation_y_mm=0.3)

        assert len(results) == 4
        for res in results:
            assert isinstance(res, CropValidationResult)
            assert res.is_valid
            assert res.dimension_match is True
            assert res.tick_within_tolerance is True
            assert res.errors == []

    def test_golden_path_6_sheet_document_crop_plan(self):
        """Spec §14.A.1, §14.B: Assemble full 6-sheet document plan:
        - Sheet 1: Cover Spread (yield 2)
        - Sheets 2–6: 4-Up Imposition (yield 4 each)
        Total Yield: 22 pages (COVER, PAGE-01..PAGE-20, BACKCOVER).
        Document Status: MANUAL_REVIEW_REQUIRED (because cover auto-crop is disabled).
        """
        calc = CropCoordinateCalculator()

        # Build 6 page plans
        p0 = calc.calculate_cover(pdf_page_index=0)
        p1 = calc.calculate_imposition_4up(pdf_page_index=1)
        p2 = calc.calculate_imposition_4up(pdf_page_index=2)
        p3 = calc.calculate_imposition_4up(pdf_page_index=3)
        p4 = calc.calculate_imposition_4up(pdf_page_index=4)
        p5 = calc.calculate_imposition_4up(pdf_page_index=5)

        doc_plan = calc.create_document_crop_plan(
            source_filename="Preview COMIC COLLECTION vol 1.pdf",
            page_plans=[p0, p1, p2, p3, p4, p5],
        )

        assert doc_plan.total_pdf_pages == 6
        assert doc_plan.expected_total_book_pages == 22
        assert doc_plan.document_status.document_status == "MANUAL_REVIEW_REQUIRED"
        assert doc_plan.document_status.has_manual_review_required is True

        # Verify page sequence signature
        assert doc_plan.page_sequence_signature == [
            LayoutType.COVER_SPREAD.value,
            LayoutType.IMPOSITION_4UP.value,
            LayoutType.IMPOSITION_4UP.value,
            LayoutType.IMPOSITION_4UP.value,
            LayoutType.IMPOSITION_4UP.value,
            LayoutType.IMPOSITION_4UP.value,
        ]

        # Verify all 22 page region names
        all_region_ids = [
            r.region_id
            for p in doc_plan.page_plans
            for r in p.crop_regions
        ]
        assert len(all_region_ids) == 22
        assert all_region_ids[0] == "BACKCOVER"
        assert all_region_ids[1] == "COVER"
        expected_pages = [f"PAGE-{i:02d}" for i in range(1, 21)]
        assert all_region_ids[2:] == expected_pages

    def test_all_crop_strategies_bounding_boxes_within_mediabox(self):
        """CHECK 1: Verify all bounding boxes for Cover, 4-Up, and Single Page remain strictly within MediaBox."""
        calc = CropCoordinateCalculator()

        # 1. Cover
        p_cover = calc.calculate_cover(pdf_page_index=0)
        for r in p_cover.crop_regions:
            assert r.x_min_pt >= 0.0
            assert r.y_min_pt >= 0.0
            assert r.x_max_pt <= p_cover.width_pt
            assert r.y_max_pt <= p_cover.height_pt
            assert r.x_min_pt < r.x_max_pt
            assert r.y_min_pt < r.y_max_pt

        # 2. 4-Up
        p_4up = calc.calculate_imposition_4up(pdf_page_index=1)
        for r in p_4up.crop_regions:
            assert r.x_min_pt >= 0.0
            assert r.y_min_pt >= 0.0
            assert r.x_max_pt <= p_4up.width_pt
            assert r.y_max_pt <= p_4up.height_pt
            assert r.x_min_pt < r.x_max_pt
            assert r.y_min_pt < r.y_max_pt

        # 3. Single Page
        p_single = calc.calculate_single_page(pdf_page_index=0)
        for r in p_single.crop_regions:
            assert r.x_min_pt >= 0.0
            assert r.y_min_pt >= 0.0
            assert r.x_max_pt <= p_single.width_pt
            assert r.y_max_pt <= p_single.height_pt
            assert r.x_min_pt < r.x_max_pt
            assert r.y_min_pt < r.y_max_pt
