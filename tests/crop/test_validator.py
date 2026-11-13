"""Unit tests for Phase 1.2.2.3 — Crop Plan Validator.

Tests cover:
1. Bounding Box & Geometric Invariants (ordered coordinates, positive area, MediaBox containment, 2D overlaps vs 1D flush seams, spine exclusion)
2. Dimension & Anti-Stretching Invariants (target pixels, DPI, aspect ratio preservation <= 0.5%, unresolved discrepancy preservation)
3. 4-Up Imposition Invariants (4 quadrants, ordering, interior seams, outer margins, tick deviation <= 1mm, rotation, flipped sheet)
4. Cover Spread Invariants (mandatory MANUAL_REVIEW_REQUIRED, auto-crop disabled, spine exclusion, distinct BACKCOVER/COVER)
5. Single Page Invariants (nominal CROP_READY, non-nominal MANUAL_REVIEW_REQUIRED, rotation)
6. Document-Level Integrity (page sequence continuity, total yield sum, status aggregation)
7. Unified CropPlanValidator API (polymorphic validate, strict mode, detailed reports)
"""

from __future__ import annotations

import pytest

from app.crop.calculator import (
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
    NOMINAL_4UP_SHEET_HEIGHT_PT,
    NOMINAL_4UP_SHEET_WIDTH_PT,
    NOMINAL_SINGLE_PAGE_HEIGHT_PT,
    NOMINAL_SINGLE_PAGE_WIDTH_PT,
    SinglePageCropStrategy,
    TickMarkCoordinates,
)
from app.crop.models.crop_region import CropRegion
from app.crop.models.crop_validation import CropValidationResult
from app.crop.models.document_crop_plan import DocumentCropPlan, DocumentStatus
from app.crop.models.enums import (
    BlankPageStatus,
    ClassificationStatus,
    CropReadinessStatus,
    CropStrategyType,
    LayoutType,
    ManualReviewFlag,
    Orientation,
)
from app.crop.models.page_crop_plan import PageCropPlan
from app.crop.profiles.profile_configs import (
    create_cover_profile,
    create_imposition_4up_profile,
    create_single_page_profile,
)
from app.crop.validator import (
    CropPlanValidator,
    DocumentValidationReport,
    PageValidationReport,
    detect_region_overlaps,
    validate_4up_layout_plan,
    validate_cover_layout_plan,
    validate_document_plan_integrity,
    validate_region_dimensions,
    validate_region_geometry,
    validate_single_page_layout_plan,
    validate_spine_exclusion,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def cover_profile():
    return create_cover_profile()


@pytest.fixture
def imposition_profile():
    return create_imposition_4up_profile()


@pytest.fixture
def single_page_profile():
    return create_single_page_profile()


@pytest.fixture
def standard_validator():
    return CropPlanValidator(strict_aspect_ratio_threshold=0.5, strict_tick_tolerance_mm=1.0)


@pytest.fixture
def sample_tick_marks():
    return TickMarkCoordinates(
        x_top=439.37,
        x_bottom=439.37,
        y_left=623.62,
        y_right=623.62,
    )


@pytest.fixture
def sample_cover_marks():
    return CoverCropMarks()


@pytest.fixture
def valid_nominal_4up_page_plan(imposition_profile, sample_tick_marks):
    strategy = Imposition4UpCropStrategy(profile=imposition_profile)
    return strategy.calculate(
        sheet_width_pt=NOMINAL_4UP_SHEET_WIDTH_PT,
        sheet_height_pt=NOMINAL_4UP_SHEET_HEIGHT_PT,
        page_index=1,
        page_number=2,
        tick_marks=sample_tick_marks,
    )


@pytest.fixture
def valid_cover_page_plan(cover_profile, sample_cover_marks):
    strategy = CoverCropStrategy(profile=cover_profile)
    return strategy.calculate(
        sheet_width_pt=1275.59055,
        sheet_height_pt=666.14173,
        page_index=0,
        page_number=1,
        crop_marks=sample_cover_marks,
    )


@pytest.fixture
def valid_single_page_plan(single_page_profile):
    strategy = SinglePageCropStrategy(profile=single_page_profile)
    return strategy.calculate(
        page_width_pt=NOMINAL_SINGLE_PAGE_WIDTH_PT,
        page_height_pt=NOMINAL_SINGLE_PAGE_HEIGHT_PT,
        page_index=0,
        page_number=1,
    )


# =============================================================================
# SECTION 1: Bounding Box & Geometry Validation Tests
# =============================================================================

class TestBoundingBoxValidation:
    """Test geometry, bounds checking, zero/inverted area, and overlap detection."""

    def test_valid_region_geometry_passes(self):
        region = CropRegion(
            region_id="test_reg",
            x_min_pt=10.0,
            y_min_pt=10.0,
            x_max_pt=110.0,
            y_max_pt=110.0,
            target_width_px=417,
            target_height_px=417,
            dpi=300,
        )
        errors = validate_region_geometry(region, page_width_pt=200.0, page_height_pt=200.0)
        assert len(errors) == 0

    def test_inverted_x_coordinates_fail(self):
        # Use model_construct to bypass Pydantic model validation and test validator's own check
        region = CropRegion.model_construct(
            region_id="inv_x",
            x_min_pt=100.0,
            y_min_pt=10.0,
            x_max_pt=50.0,  # x_max < x_min
            y_max_pt=110.0,
            target_width_px=200,
            target_height_px=417,
            dpi=300,
        )
        errors = validate_region_geometry(region, page_width_pt=200.0, page_height_pt=200.0)
        assert len(errors) > 0
        assert any("inverted or zero width" in e for e in errors)

    def test_inverted_y_coordinates_fail(self):
        region = CropRegion.model_construct(
            region_id="inv_y",
            x_min_pt=10.0,
            y_min_pt=100.0,
            x_max_pt=60.0,
            y_max_pt=80.0,  # y_max < y_min
            target_width_px=200,
            target_height_px=200,
            dpi=300,
        )
        errors = validate_region_geometry(region, page_width_pt=200.0, page_height_pt=200.0)
        assert len(errors) > 0
        assert any("inverted or zero height" in e for e in errors)

    def test_negative_coordinates_fail(self):
        region = CropRegion.model_construct(
            region_id="neg_coord",
            x_min_pt=-5.0,
            y_min_pt=10.0,
            x_max_pt=50.0,
            y_max_pt=50.0,
            target_width_px=200,
            target_height_px=200,
            dpi=300,
        )
        errors = validate_region_geometry(region, page_width_pt=200.0, page_height_pt=200.0)
        assert len(errors) > 0
        assert any("is negative" in e for e in errors)

    def test_zero_area_fails(self):
        region = CropRegion.model_construct(
            region_id="zero_area",
            x_min_pt=10.0,
            y_min_pt=10.0,
            x_max_pt=10.0,  # width = 0
            y_max_pt=50.0,
            target_width_px=0,
            target_height_px=200,
            dpi=300,
        )
        errors = validate_region_geometry(region, page_width_pt=200.0, page_height_pt=200.0)
        assert len(errors) > 0
        assert any("non-positive area" in e or "inverted or zero width" in e for e in errors)

    def test_exceeding_mediabox_width_fails(self):
        region = CropRegion(
            region_id="oob_x",
            x_min_pt=150.0,
            y_min_pt=10.0,
            x_max_pt=210.0,  # 210 > 200
            y_max_pt=50.0,
            target_width_px=200,
            target_height_px=200,
            dpi=300,
        )
        errors = validate_region_geometry(region, page_width_pt=200.0, page_height_pt=200.0)
        assert len(errors) > 0
        assert any("exceeds page width" in e for e in errors)

    def test_exceeding_mediabox_height_fails(self):
        region = CropRegion(
            region_id="oob_y",
            x_min_pt=10.0,
            y_min_pt=180.0,
            x_max_pt=60.0,
            y_max_pt=210.0,  # 210 > 200
            target_width_px=200,
            target_height_px=200,
            dpi=300,
        )
        errors = validate_region_geometry(region, page_width_pt=200.0, page_height_pt=200.0)
        assert len(errors) > 0
        assert any("exceeds page height" in e for e in errors)

    def test_detect_overlapping_regions_fails(self):
        """Two regions that significantly overlap in both X and Y must trigger an error."""
        r1 = CropRegion(
            region_id="reg_1",
            x_min_pt=10.0,
            y_min_pt=10.0,
            x_max_pt=110.0,
            y_max_pt=110.0,
            target_width_px=400,
            target_height_px=400,
            dpi=300,
        )
        r2 = CropRegion(
            region_id="reg_2",
            x_min_pt=50.0,  # Overlaps r1 in [50, 110]
            y_min_pt=50.0,  # Overlaps r1 in [50, 110]
            x_max_pt=150.0,
            y_max_pt=150.0,
            target_width_px=400,
            target_height_px=400,
            dpi=300,
        )
        overlap_errors = detect_region_overlaps([r1, r2])
        assert len(overlap_errors) > 0
        assert any("Overlapping crop regions detected" in e for e in overlap_errors)

    def test_flush_cut_seam_does_not_trigger_overlap(self):
        """Adjacent 4-Up quadrants share an edge (1D seam, area = 0). Must NOT be flagged as overlap."""
        q1 = CropRegion(
            region_id="Q1",
            quadrant=1,
            x_min_pt=13.85,
            y_min_pt=623.62,
            x_max_pt=439.37,
            y_max_pt=1232.74,
            target_width_px=1773,
            target_height_px=2538,
            dpi=300,
        )
        # Q2 starts at x=439.37 (13.85 + 425.52 = 439.37 exact)
        q2 = CropRegion(
            region_id="Q2",
            quadrant=2,
            x_min_pt=439.37,
            y_min_pt=623.62,
            x_max_pt=864.89,
            y_max_pt=1232.74,
            target_width_px=1773,
            target_height_px=2538,
            dpi=300,
        )
        overlap_errors = detect_region_overlaps([q1, q2])
        assert len(overlap_errors) == 0

    def test_spine_exclusion_validation(self):
        """Spine zone (608.52 - 651.08 pt) must not be encroached by any region."""
        backcover = CropRegion(
            region_id="BACKCOVER",
            x_min_pt=171.97,
            y_min_pt=14.19,
            x_max_pt=608.51,  # <= 608.51709
            y_max_pt=651.95,
            target_width_px=1890,
            target_height_px=2657,
            dpi=300,
        )
        # Frontcover encroaching into spine
        encroaching_cover = CropRegion(
            region_id="COVER",
            x_min_pt=630.0,  # 630 < 651.10938 enters spine!
            y_min_pt=14.19,
            x_max_pt=1083.60,
            y_max_pt=651.95,
            target_width_px=630,
            target_height_px=886,
            dpi=100,
        )
        errors = validate_spine_exclusion(
            backcover=backcover,
            frontcover=encroaching_cover,
            expected_spine_left_pt=DEFAULT_COVER_SPINE_INNER_LEFT_PT,
            expected_spine_right_pt=DEFAULT_COVER_SPINE_INNER_RIGHT_PT,
        )
        assert len(errors) > 0
        assert any("extends into the spine zone" in e for e in errors)


# =============================================================================
# SECTION 2: Dimension & Anti-Stretching Validation Tests
# =============================================================================

class TestDimensionValidation:
    """Test pixel dimensions, DPI, and strict anti-stretching (aspect ratio preservation)."""

    def test_nominal_content_dimensions_pass(self, imposition_profile):
        region = CropRegion(
            region_id="p1_q1",
            quadrant=1,
            x_min_pt=13.85,
            y_min_pt=623.62,
            x_max_pt=439.37,
            y_max_pt=1232.74,
            target_width_px=1773,
            target_height_px=2538,
            dpi=300,
        )
        errors, warnings = validate_region_dimensions(region, imposition_profile, layout_type=LayoutType.IMPOSITION_4UP)
        assert len(errors) == 0
        assert len(warnings) == 0

    def test_pixel_width_mismatch_fails(self, imposition_profile):
        region = CropRegion(
            region_id="p1_q1_wrong_w",
            quadrant=1,
            x_min_pt=13.85,
            y_min_pt=623.62,
            x_max_pt=439.37,
            y_max_pt=1232.74,
            target_width_px=1800,  # Expected 1773
            target_height_px=2538,
            dpi=300,
        )
        errors, warnings = validate_region_dimensions(region, imposition_profile, layout_type=LayoutType.IMPOSITION_4UP)
        assert len(errors) > 0
        assert any("target_width_px" in e for e in errors)

    def test_pixel_height_mismatch_fails(self, imposition_profile):
        region = CropRegion(
            region_id="p1_q1_wrong_h",
            quadrant=1,
            x_min_pt=13.85,
            y_min_pt=623.62,
            x_max_pt=439.37,
            y_max_pt=1232.74,
            target_width_px=1773,
            target_height_px=2500,  # Expected 2538
            dpi=300,
        )
        errors, warnings = validate_region_dimensions(region, imposition_profile, layout_type=LayoutType.IMPOSITION_4UP)
        assert len(errors) > 0
        assert any("target_height_px" in e for e in errors)

    def test_aspect_ratio_stretching_fails(self, imposition_profile):
        """If vector bounding box is stretched relative to pixel targets, must fail."""
        region = CropRegion(
            region_id="stretched",
            quadrant=1,
            x_min_pt=13.85,
            y_min_pt=623.62,
            x_max_pt=413.85,  # width=400 pt instead of 425.52 pt (~6% distortion)
            y_max_pt=1232.74,
            target_width_px=1773,
            target_height_px=2538,
            dpi=300,
        )
        errors, warnings = validate_region_dimensions(
            region, imposition_profile, layout_type=LayoutType.IMPOSITION_4UP, max_distortion_percent=0.5
        )
        assert len(errors) > 0
        assert any("image stretching detected" in e for e in errors)

    def test_cover_unresolved_dimensions_warning_behavior(self, cover_profile):
        """Cover vector width (436.54 pt) != target pixel width (453.60 pt). Produces documented warnings, not errors."""
        backcover_region = CropRegion(
            region_id="BACKCOVER",
            x_min_pt=171.97,
            y_min_pt=14.19,
            x_max_pt=608.51,  # width=436.54 pt
            y_max_pt=651.95,
            target_width_px=1890,
            target_height_px=2657,
            dpi=300,
        )
        errors, warnings = validate_region_dimensions(backcover_region, cover_profile, layout_type=LayoutType.COVER_SPREAD)
        assert len(errors) == 0
        # Should record COVER_WIDTH_DISCREPANCY warning
        assert any("COVER_WIDTH_DISCREPANCY" in w for w in warnings)


# =============================================================================
# SECTION 3: 4-Up Imposition Invariant Tests
# =============================================================================

class Test4UpLayoutValidation:
    """Test 4-Up quadrants, seam alignment, tick deviation <= 1mm, and outer margins."""

    def test_valid_nominal_4up_plan_passes(self, valid_nominal_4up_page_plan, imposition_profile):
        errors, warnings = validate_4up_layout_plan(valid_nominal_4up_page_plan, imposition_profile)
        assert len(errors) == 0

    def test_missing_quadrant_fails(self, valid_nominal_4up_page_plan, imposition_profile):
        incomplete_plan = valid_nominal_4up_page_plan.model_copy(deep=True)
        incomplete_plan.crop_regions = incomplete_plan.crop_regions[:3]
        incomplete_plan.expected_page_yield = 3

        errors, warnings = validate_4up_layout_plan(incomplete_plan, imposition_profile)
        assert len(errors) > 0
        assert any("expected_page_yield must be 4" in e or "Exactly 4 crop regions required" in e for e in errors)

    def test_extra_quadrant_fails(self, valid_nominal_4up_page_plan, imposition_profile):
        extra_plan = valid_nominal_4up_page_plan.model_copy(deep=True)
        extra_region = extra_plan.crop_regions[0].model_copy(update={"region_id": "p2_extra"})
        extra_plan.crop_regions.append(extra_region)

        errors, warnings = validate_4up_layout_plan(extra_plan, imposition_profile)
        assert len(errors) > 0
        assert any("must have exactly 4 crop regions" in e for e in errors)

    def test_invalid_quadrant_sequence_fails(self, valid_nominal_4up_page_plan, imposition_profile):
        scrambled_plan = valid_nominal_4up_page_plan.model_copy(deep=True)
        # Swap Q1 and Q2
        scrambled_plan.crop_regions = [
            scrambled_plan.crop_regions[1],
            scrambled_plan.crop_regions[0],
            scrambled_plan.crop_regions[2],
            scrambled_plan.crop_regions[3],
        ]

        errors, warnings = validate_4up_layout_plan(scrambled_plan, imposition_profile)
        assert len(errors) > 0
        assert any("expected 1" in e for e in errors)

    def test_vertical_seam_mismatch_fails(self, valid_nominal_4up_page_plan, imposition_profile):
        seam_plan = valid_nominal_4up_page_plan.model_copy(deep=True)
        # Shift Q2 x_min_pt by 2 pt, creating a gap
        seam_plan.crop_regions[1].x_min_pt += 2.0

        errors, warnings = validate_4up_layout_plan(seam_plan, imposition_profile)
        assert len(errors) > 0
        assert any("Vertical interior seam gap" in e for e in errors)

    def test_horizontal_seam_mismatch_fails(self, valid_nominal_4up_page_plan, imposition_profile):
        seam_plan = valid_nominal_4up_page_plan.model_copy(deep=True)
        # Shift Q3 y_min_pt by 2 pt, creating a gap
        seam_plan.crop_regions[2].y_min_pt -= 2.0

        errors, warnings = validate_4up_layout_plan(seam_plan, imposition_profile)
        assert len(errors) > 0
        assert any("Horizontal interior seam gap" in e for e in errors)

    def test_excessive_tick_deviation_marked_crop_ready_fails(self, imposition_profile):
        """Tick deviation > 1.0 mm cannot be CROP_READY."""
        strategy = Imposition4UpCropStrategy(profile=imposition_profile)
        drifted_ticks = TickMarkCoordinates(
            x_top=439.37 + 5.67,  # 2.0 mm deviation
            x_bottom=439.37,
            y_left=623.62,
            y_right=623.62,
        )
        plan = strategy.calculate(
            sheet_width_pt=NOMINAL_4UP_SHEET_WIDTH_PT,
            sheet_height_pt=NOMINAL_4UP_SHEET_HEIGHT_PT,
            page_index=1,
            page_number=2,
            tick_marks=drifted_ticks,
        )
        # Force plan status to CROP_READY to test validator rejection
        bad_plan = plan.model_copy(update={"crop_readiness": CropReadinessStatus.CROP_READY})
        errors, warnings = validate_4up_layout_plan(bad_plan, imposition_profile, tick_coords=drifted_ticks)
        assert len(errors) > 0
        assert any("exceeding tolerance" in e for e in errors)

    def test_non_zero_rotation_marked_crop_ready_fails(self, valid_nominal_4up_page_plan, imposition_profile):
        """Rotation != 0 marked CROP_READY must fail."""
        rotated_plan = valid_nominal_4up_page_plan.model_copy(
            update={"rotation": 90, "crop_readiness": CropReadinessStatus.CROP_READY}
        )
        errors, warnings = validate_4up_layout_plan(rotated_plan, imposition_profile)
        assert len(errors) > 0
        assert any("must be MANUAL_REVIEW_REQUIRED" in e for e in errors)


# =============================================================================
# SECTION 4: Cover Spread Invariant Tests
# =============================================================================

class TestCoverLayoutValidation:
    """Test Cover Spread invariants: mandatory MANUAL_REVIEW_REQUIRED, auto-crop disabled, spine exclusion."""

    def test_valid_cover_plan_passes(self, valid_cover_page_plan, cover_profile):
        errors, warnings = validate_cover_layout_plan(valid_cover_page_plan, cover_profile)
        assert len(errors) == 0
        # Warnings for unresolved decisions are expected and recorded
        assert any("COVER_WIDTH_DISCREPANCY" in w for w in warnings)

    def test_cover_marked_crop_ready_fails(self, valid_cover_page_plan, cover_profile):
        """Cover can NEVER be CROP_READY per Spec §12.3."""
        illegal_plan = valid_cover_page_plan.model_copy(update={"crop_readiness": CropReadinessStatus.CROP_READY})
        errors, warnings = validate_cover_layout_plan(illegal_plan, cover_profile)
        assert len(errors) > 0
        assert any("MUST ALWAYS be MANUAL_REVIEW_REQUIRED" in e for e in errors)

    def test_cover_auto_crop_enabled_fails(self, valid_cover_page_plan, cover_profile):
        """cover_auto_crop_enabled must remain False."""
        profile_enabled = cover_profile.model_copy(update={"cover_auto_crop_enabled": True})
        errors, warnings = validate_cover_layout_plan(valid_cover_page_plan, profile_enabled)
        assert len(errors) > 0
        assert any("strictly prohibited" in e for e in errors)

    def test_cover_identical_back_and_front_dimensions_fails(self, valid_cover_page_plan, cover_profile):
        """BACKCOVER (1890x2657 @ 300) and COVER (630x886 @ 100) must remain distinct."""
        identical_plan = valid_cover_page_plan.model_copy(deep=True)
        # Force FRONTCOVER to identical 1890x2657 @ 300 DPI
        identical_plan.crop_regions[1].target_width_px = 1890
        identical_plan.crop_regions[1].target_height_px = 2657

        errors, warnings = validate_cover_layout_plan(identical_plan, cover_profile)
        assert len(errors) > 0
        assert any("identical output dimensions" in e for e in errors)

    def test_cover_missing_review_flag_fails(self, valid_cover_page_plan, cover_profile):
        """Cover plan must have COVER_FORMULA_UNVALIDATED flag."""
        unflagged_plan = valid_cover_page_plan.model_copy(update={"manual_review_flags": []})
        errors, warnings = validate_cover_layout_plan(unflagged_plan, cover_profile)
        assert len(errors) > 0
        assert any("COVER_FORMULA_UNVALIDATED in manual_review_flags" in e for e in errors)

    def test_cover_region_count_not_two_fails(self, valid_cover_page_plan, cover_profile):
        """Cover layout must have exactly 2 regions."""
        one_region_plan = valid_cover_page_plan.model_copy(deep=True)
        one_region_plan.crop_regions = [one_region_plan.crop_regions[0]]
        one_region_plan.expected_page_yield = 1

        errors, warnings = validate_cover_layout_plan(one_region_plan, cover_profile)
        assert len(errors) > 0
        assert any("expected_page_yield must be 2" in e or "must have exactly 2 crop regions" in e for e in errors)


# =============================================================================
# SECTION 5: Single Page Invariant Tests
# =============================================================================

class TestSinglePageLayoutValidation:
    """Test Single Page invariants: nominal CROP_READY, non-nominal MANUAL_REVIEW_REQUIRED, rotation."""

    def test_valid_nominal_single_page_passes(self, valid_single_page_plan, single_page_profile):
        errors, warnings = validate_single_page_layout_plan(valid_single_page_plan, single_page_profile)
        assert len(errors) == 0

    def test_non_nominal_single_page_marked_crop_ready_fails(self, single_page_profile):
        """Non-nominal single page can NEVER be CROP_READY until normalization policy is approved."""
        strategy = SinglePageCropStrategy(profile=single_page_profile)
        plan = strategy.calculate(
            page_width_pt=430.0,  # Non-nominal (nominal is 425.52)
            page_height_pt=615.0,  # Non-nominal (nominal is 609.12)
            page_index=0,
            page_number=1,
        )
        assert plan.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED

        # Force status to CROP_READY to test validator rejection
        illegal_plan = plan.model_copy(update={"crop_readiness": CropReadinessStatus.CROP_READY})
        errors, warnings = validate_single_page_layout_plan(illegal_plan, single_page_profile)
        assert len(errors) > 0
        assert any("cannot be CROP_READY" in e for e in errors)

    def test_non_nominal_single_page_marked_manual_review_passes(self, single_page_profile):
        """Non-nominal single page in MANUAL_REVIEW_REQUIRED is valid."""
        strategy = SinglePageCropStrategy(profile=single_page_profile)
        plan = strategy.calculate(
            page_width_pt=430.0,
            page_height_pt=615.0,
            page_index=0,
            page_number=1,
        )
        errors, warnings = validate_single_page_layout_plan(plan, single_page_profile)
        assert len(errors) == 0
        assert any("non-nominal" in w.lower() for w in warnings)

    def test_single_page_non_zero_rotation_marked_crop_ready_fails(self, valid_single_page_plan, single_page_profile):
        rotated_plan = valid_single_page_plan.model_copy(
            update={"rotation": 270, "crop_readiness": CropReadinessStatus.CROP_READY}
        )
        errors, warnings = validate_single_page_layout_plan(rotated_plan, single_page_profile)
        assert len(errors) > 0
        assert any("must be MANUAL_REVIEW_REQUIRED" in e for e in errors)

    def test_single_page_region_count_not_one_fails(self, valid_single_page_plan, single_page_profile):
        empty_plan = valid_single_page_plan.model_copy(deep=True)
        empty_plan.crop_regions = []
        empty_plan.expected_page_yield = 0

        errors, warnings = validate_single_page_layout_plan(empty_plan, single_page_profile)
        assert len(errors) > 0
        assert any("expected_page_yield must be 1" in e or "Exactly 1 crop region required" in e for e in errors)


# =============================================================================
# SECTION 6: Document-Level Integrity Tests
# =============================================================================

class TestDocumentValidation:
    """Test document sequence continuity, total yield sum, and document status aggregation per Spec §12."""

    def test_valid_golden_document_passes(self, cover_profile, imposition_profile):
        """A complete 6-sheet document (1 cover + 5 4-up sheets) passes validation."""
        calc = CropCoordinateCalculator()
        p0 = calc.calculate_cover(pdf_page_index=0)
        p1 = calc.calculate_imposition_4up(pdf_page_index=1)
        p2 = calc.calculate_imposition_4up(pdf_page_index=2)
        p3 = calc.calculate_imposition_4up(pdf_page_index=3)
        p4 = calc.calculate_imposition_4up(pdf_page_index=4)
        p5 = calc.calculate_imposition_4up(pdf_page_index=5)

        doc_plan = calc.create_document_crop_plan(
            source_filename="test_golden.pdf",
            page_plans=[p0, p1, p2, p3, p4, p5],
        )
        assert doc_plan.total_pdf_pages == 6
        assert doc_plan.expected_total_book_pages == 22  # 2 + 5*4 = 22

        errors, warnings = validate_document_plan_integrity(doc_plan)
        assert len(errors) == 0

    def test_document_page_index_gap_fails(self, valid_nominal_4up_page_plan, imposition_profile):
        """Skipping a page index must fail document validation."""
        p0 = valid_nominal_4up_page_plan.model_copy(update={"pdf_page_index": 0, "pdf_page_number": 1})
        p2 = valid_nominal_4up_page_plan.model_copy(update={"pdf_page_index": 2, "pdf_page_number": 3})  # Gap at index 1

        doc_plan = DocumentCropPlan.model_construct(
            source_filename="gap.pdf",
            total_pdf_pages=2,
            profile=imposition_profile,
            page_plans=[p0, p2],
            document_status=DocumentStatus(
                has_unknown_layout=False,
                has_manual_review_required=False,
                all_pages_crop_ready=True,
                document_status="AUTO_READY_FOR_PREVIEW",
            ),
            expected_total_book_pages=8,
            page_sequence_signature=["IMPOSITION_4UP", "IMPOSITION_4UP"],
        )
        errors, warnings = validate_document_plan_integrity(doc_plan)
        assert len(errors) > 0
        assert any("pdf_page_index" in e and "expected" in e for e in errors)

    def test_document_yield_sum_mismatch_fails(self, valid_nominal_4up_page_plan, imposition_profile):
        p0 = valid_nominal_4up_page_plan.model_copy(update={"pdf_page_index": 0, "pdf_page_number": 1})

        doc_plan = DocumentCropPlan.model_construct(
            source_filename="yield_mismatch.pdf",
            total_pdf_pages=1,
            profile=imposition_profile,
            page_plans=[p0],
            document_status=DocumentStatus(
                has_unknown_layout=False,
                has_manual_review_required=False,
                all_pages_crop_ready=True,
                document_status="AUTO_READY_FOR_PREVIEW",
            ),
            expected_total_book_pages=10,  # Expected 10 but page produces 4
            page_sequence_signature=["IMPOSITION_4UP"],
        )
        errors, warnings = validate_document_plan_integrity(doc_plan)
        assert len(errors) > 0
        assert any("sum of page yields" in e for e in errors)


# =============================================================================
# SECTION 7: CropPlanValidator Unified API & Polymorphism Tests
# =============================================================================

class TestCropPlanValidatorAPI:
    """Test CropPlanValidator class methods, polymorphic dispatch, and reporting."""

    def test_polymorphic_validate_region(self, standard_validator):
        region = CropRegion(
            region_id="r1",
            quadrant=1,
            x_min_pt=13.85,
            y_min_pt=623.62,
            x_max_pt=439.37,
            y_max_pt=1232.74,
            target_width_px=1773,
            target_height_px=2538,
            dpi=300,
        )
        report = standard_validator.validate(region, page_width_pt=878.74, page_height_pt=1247.24)
        assert isinstance(report, CropValidationResult)
        assert report.is_valid is True

    def test_polymorphic_validate_page(self, standard_validator, valid_nominal_4up_page_plan):
        report = standard_validator.validate(valid_nominal_4up_page_plan)
        assert isinstance(report, PageValidationReport)
        assert report.is_valid is True
        assert report.layout_type == LayoutType.IMPOSITION_4UP
        assert len(report.region_results) == 4

    def test_polymorphic_validate_document(self, standard_validator):
        calc = CropCoordinateCalculator()
        p0 = calc.calculate_cover(pdf_page_index=0)
        doc_plan = calc.create_document_crop_plan(
            source_filename="poly.pdf",
            page_plans=[p0],
        )
        report = standard_validator.validate(doc_plan)
        assert isinstance(report, DocumentValidationReport)
        assert report.is_valid is True
        assert report.total_pdf_pages == 1
        assert report.total_regions == 2

    def test_unsupported_type_raises_type_error(self, standard_validator):
        with pytest.raises(TypeError, match="Unsupported validation target type"):
            standard_validator.validate("some_string_target")

    def test_strict_mode_promotes_warnings_to_errors(self, cover_profile, sample_cover_marks):
        """In strict mode, warnings (like Cover unresolved width) cause is_valid to become False."""
        strict_validator = CropPlanValidator(strict_mode=True)
        strategy = CoverCropStrategy(profile=cover_profile)
        plan = strategy.calculate(
            sheet_width_pt=1275.59055,
            sheet_height_pt=666.14173,
            page_index=0,
            page_number=1,
            crop_marks=sample_cover_marks,
        )
        report = strict_validator.validate_page(plan, profile=cover_profile)
        # Because cover plan has warnings (e.g. UNRESOLVED_COVER_WIDTH_DISCREPANCY), strict mode marks is_valid=False
        assert report.is_valid is False
        assert any("[STRICT]" in e for e in report.errors)

    def test_page_validation_report_to_summary_dict(self, standard_validator, valid_nominal_4up_page_plan):
        report = standard_validator.validate_page(valid_nominal_4up_page_plan)
        summary = report.to_summary_dict()
        assert summary["pdf_page_index"] == 1
        assert summary["layout_type"] == LayoutType.IMPOSITION_4UP.value
        assert summary["is_valid"] is True
        assert summary["regions_count"] == 4

    def test_document_validation_report_to_summary_dict(self, standard_validator, valid_nominal_4up_page_plan, imposition_profile):
        doc_plan = DocumentCropPlan(
            source_filename="summary.pdf",
            total_pdf_pages=1,
            profile=imposition_profile,
            page_plans=[valid_nominal_4up_page_plan.model_copy(update={"pdf_page_index": 0, "pdf_page_number": 1})],
            document_status=DocumentStatus(
                has_unknown_layout=False,
                has_manual_review_required=False,
                all_pages_crop_ready=True,
                document_status="AUTO_READY_FOR_PREVIEW",
            ),
            expected_total_book_pages=4,
            page_sequence_signature=["IMPOSITION_4UP"],
        )
        report = standard_validator.validate_document(doc_plan)
        summary = report.to_summary_dict()
        assert summary["source_filename"] == "summary.pdf"
        assert summary["is_valid"] is True
        assert summary["total_pdf_pages"] == 1
        assert summary["total_regions"] == 4
