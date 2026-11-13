"""Unit tests for Phase 1.2.2.1 — Pydantic models & profile validation.

Tests cover:
1. Valid model instantiation from specification values
2. Invalid data rejection (all validation rules)
3. Profile factory functions
4. JSON Schema generation
5. Serialization round-trip
6. Business rule enforcement per Spec v1.3.4
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.crop.models.enums import (
    BlankPageStatus,
    ClassificationStatus,
    CropReadinessStatus,
    CropStrategyType,
    LayoutType,
    ManualReviewFlag,
    Orientation,
    ProductionBasis,
)
from app.crop.models.project_profile import (
    CoverDimensions,
    CoverReferenceDimensions,
    OuterMarginConfig,
    ProjectTrimProfile,
)
from app.crop.models.crop_region import CropRegion
from app.crop.models.page_crop_plan import PageCropPlan
from app.crop.models.crop_validation import CropValidationResult
from app.crop.models.document_crop_plan import DocumentCropPlan, DocumentStatus
from app.crop.profiles.profile_configs import (
    create_default_profile,
    create_cover_profile,
    create_imposition_4up_profile,
    create_single_page_profile,
    write_profile_configs_to_directory,
)
from app.crop.schemas.valid_examples import (
    get_valid_profile_json,
    get_valid_crop_region_4up_q1_json,
    get_valid_page_crop_plan_cover_json,
    get_valid_page_crop_plan_4up_json,
    get_valid_page_crop_plan_single_json,
    get_valid_document_crop_plan_json,
    get_valid_crop_validation_result_json,
    get_valid_crop_validation_result_failed_json,
    write_valid_examples,
)
from app.crop.schemas.invalid_examples import (
    get_invalid_profile_cover_auto_crop_enabled,
    get_invalid_profile_pixel_mismatch,
    get_invalid_profile_id_uppercase,
    get_invalid_profile_identical_cover_dimensions,
    get_invalid_crop_region_inverted_bbox,
    get_invalid_crop_region_zero_area,
    get_invalid_crop_region_negative_coords,
    get_invalid_page_plan_cover_crop_ready,
    get_invalid_page_plan_rotated_crop_ready,
    get_invalid_page_plan_unknown_with_strategy,
    get_invalid_page_plan_manual_review_no_flags,
    get_invalid_page_plan_page_number_mismatch,
    get_invalid_page_plan_bad_rotation,
    get_invalid_page_plan_classified_no_layout,
    get_invalid_page_plan_single_non_nominal_crop_ready,
    get_invalid_validation_valid_with_errors,
    get_invalid_validation_invalid_no_errors,
    get_invalid_validation_dimension_mismatch_flag,
    get_all_invalid_examples,
    write_invalid_examples,
)
from app.crop.schemas.generate_schemas import generate_all_schemas


# =============================================================================
# SECTION 1: Enum Tests
# =============================================================================

class TestEnums:
    """Test enum definitions match Spec v1.3.4."""

    def test_layout_types(self):
        assert LayoutType.COVER_SPREAD.value == "COVER_SPREAD"
        assert LayoutType.IMPOSITION_4UP.value == "IMPOSITION_4UP"
        assert LayoutType.SINGLE_PAGE.value == "SINGLE_PAGE"
        assert len(LayoutType) == 3

    def test_crop_strategy_types(self):
        assert CropStrategyType.COVER.value == "CoverCropStrategy"
        assert CropStrategyType.IMPOSITION_4UP.value == "Imposition4UpCropStrategy"
        assert CropStrategyType.SINGLE_PAGE.value == "SinglePageCropStrategy"
        assert len(CropStrategyType) == 3

    def test_classification_status(self):
        assert ClassificationStatus.CLASSIFIED.value == "CLASSIFIED"
        assert ClassificationStatus.UNKNOWN_LAYOUT.value == "UNKNOWN_LAYOUT"
        assert (
            ClassificationStatus.CANDIDATE_IMPOSITION_4UP_FLIPPED.value
            == "CANDIDATE_IMPOSITION_4UP_FLIPPED"
        )

    def test_crop_readiness_status(self):
        assert CropReadinessStatus.CROP_READY.value == "CROP_READY"
        assert CropReadinessStatus.MANUAL_REVIEW_REQUIRED.value == "MANUAL_REVIEW_REQUIRED"
        assert CropReadinessStatus.NOT_APPLICABLE.value == "NOT_APPLICABLE"

    def test_orientation(self):
        assert Orientation.LANDSCAPE.value == "LANDSCAPE"
        assert Orientation.PORTRAIT.value == "PORTRAIT"
        assert Orientation.SQUARE.value == "SQUARE"

    def test_manual_review_flags_complete(self):
        """All manual review flags from Spec §2, §6, §8, §11 are present."""
        expected = {
            "COVER_FORMULA_UNVALIDATED",
            "TICK_DEVIATION_EXCEEDED",
            "TICK_ASYMMETRY_DETECTED",
            "FLIPPED_ORIENTATION_DETECTED",
            "ROTATED_SHEET_DETECTED",
            "OPENCV_FALLBACK_USED",
            "NON_NOMINAL_DIMENSIONS_DETECTED",
        }
        actual = {f.value for f in ManualReviewFlag}
        assert actual == expected

    def test_blank_page_status(self):
        assert BlankPageStatus.CONTENT_PRESENT.value == "CONTENT_PRESENT"
        assert BlankPageStatus.LOW_CONTRAST_BLANK_SUSPECTED.value == "LOW_CONTRAST_BLANK_SUSPECTED"
        assert BlankPageStatus.BLANK_PAGE_DETECTED.value == "BLANK_PAGE_DETECTED"


# =============================================================================
# SECTION 2: ProjectTrimProfile Tests
# =============================================================================

class TestProjectTrimProfile:
    """Test ProjectTrimProfile model validation."""

    def test_valid_from_json(self):
        """Valid profile JSON deserializes correctly."""
        data = get_valid_profile_json()
        profile = ProjectTrimProfile(**data)
        assert profile.profile_id == "bookabook_comic_a5_default"
        assert profile.target_content_width_px == 1773
        assert profile.target_content_height_px == 2538
        assert profile.dpi == 300

    def test_target_dimensions_match_spec(self):
        """Target dimensions match Spec §8.B.2: 1773×2538 px at 300 DPI."""
        profile = create_default_profile()
        assert profile.target_content_width_px == 1773
        assert profile.target_content_height_px == 2538
        assert profile.target_content_width_pt == 425.52
        assert profile.target_content_height_pt == 609.12

    def test_pixel_pt_conversion_exact(self):
        """px = round(pt × 300/72) must yield exact target (Spec §8.B.2)."""
        profile = create_default_profile()
        assert round(profile.target_content_width_pt * 300 / 72) == 1773
        assert round(profile.target_content_height_pt * 300 / 72) == 2538

    def test_cover_auto_crop_disabled(self):
        """Cover auto-crop must be False (Spec §8.B.1, §15.A.6)."""
        profile = create_default_profile()
        assert profile.cover_auto_crop_enabled is False

    def test_reject_cover_auto_crop_enabled(self):
        """Reject profile with cover_auto_crop_enabled=True."""
        with pytest.raises(ValidationError, match="cover_auto_crop_enabled must be False"):
            ProjectTrimProfile(**get_invalid_profile_cover_auto_crop_enabled())

    def test_reject_pixel_mismatch(self):
        """Reject profile where px != round(pt × dpi/72)."""
        with pytest.raises(ValidationError, match="target_content_width_px.*does not match"):
            ProjectTrimProfile(**get_invalid_profile_pixel_mismatch())

    def test_reject_uppercase_profile_id(self):
        """Reject profile_id with uppercase characters."""
        with pytest.raises(ValidationError, match="pattern"):
            ProjectTrimProfile(**get_invalid_profile_id_uppercase())

    def test_tick_tolerance_mm_value(self):
        """Tick deviation tolerance must be 1.0 mm (Spec §6.B)."""
        profile = create_default_profile()
        assert profile.tick_deviation_tolerance_mm == 1.0

    def test_tick_tolerance_pt_auto_computed(self):
        """Tick tolerance in pt is auto-computed: 1.0 mm × 72/25.4 ≈ 2.835 pt."""
        profile = create_default_profile()
        assert profile.tick_deviation_tolerance_pt is not None
        assert abs(profile.tick_deviation_tolerance_pt - 2.835) < 0.01

    def test_spine_config(self):
        """Spine width must be 15.02 mm and excluded (Spec §8.B.1)."""
        profile = create_default_profile()
        assert profile.spine_width_mm == 15.02
        assert profile.spine_excluded is True

    def test_outer_margin_values(self):
        """Outer margin values match Spec §10.A: 13.85 pt / 14.50 pt."""
        profile = create_default_profile()
        assert profile.outer_margin.horizontal_pt == 13.85
        assert profile.outer_margin.vertical_pt == 14.50
        assert profile.outer_margin.horizontal_mm == 4.886
        assert profile.outer_margin.vertical_mm == 5.115

    def test_cover_dimensions(self):
        """Cover target dimensions match Spec §8.A and §14.A.4."""
        profile = create_default_profile()
        cd = profile.cover_dimensions
        assert cd.target_backcover_width_px == 1890
        assert cd.target_backcover_height_px == 2657
        assert cd.target_backcover_dpi == 300
        assert cd.target_cover_width_px == 630
        assert cd.target_cover_height_px == 886
        assert cd.target_cover_dpi == 100
        # BACKCOVER and COVER must have distinct output dimensions per spec
        assert (cd.target_backcover_width_px, cd.target_backcover_height_px) != (
            cd.target_cover_width_px, cd.target_cover_height_px
        )

    def test_reject_identical_cover_dimensions(self):
        """Reject configuration assigning identical output dimensions to both cover files."""
        data = get_invalid_profile_identical_cover_dimensions()
        with pytest.raises(ValidationError, match="BACKCOVER and COVER cannot have identical output dimensions"):
            ProjectTrimProfile(**data)

    def test_serialization_roundtrip(self):
        """Profile serializes to JSON and deserializes back identically."""
        profile = create_default_profile()
        json_str = profile.model_dump_json()
        restored = ProjectTrimProfile.model_validate_json(json_str)
        assert restored == profile

    def test_no_stretching_validation(self):
        """Aspect ratio consistency prevents stretching."""
        # This should pass: 425.52/609.12 ≈ 0.6986 ≈ 1773/2538 ≈ 0.6986
        profile = create_default_profile()
        pt_ratio = profile.target_content_width_pt / profile.target_content_height_pt
        px_ratio = profile.target_content_width_px / profile.target_content_height_px
        assert abs(pt_ratio - px_ratio) < 0.001


# =============================================================================
# SECTION 3: CropRegion Tests
# =============================================================================

class TestCropRegion:
    """Test CropRegion model validation."""

    def test_valid_4up_q1(self):
        """Valid 4-Up Quadrant 1 crop region."""
        data = get_valid_crop_region_4up_q1_json()
        region = CropRegion(**data)
        assert region.region_id == "PAGE-01"
        assert region.quadrant == 1
        assert region.target_width_px == 1773
        assert region.target_height_px == 2538

    def test_width_height_properties(self):
        """Width and height properties compute correctly."""
        region = CropRegion(**get_valid_crop_region_4up_q1_json())
        assert region.width_pt > 0
        assert region.height_pt > 0
        assert abs(region.width_pt - (439.37 - 13.85)) < 0.01
        assert abs(region.height_pt - (623.62 - 14.50)) < 0.01

    def test_reject_inverted_bbox(self):
        """Reject bounding box where x_max < x_min."""
        with pytest.raises(ValidationError, match="x_max_pt.*must be greater"):
            CropRegion(**get_invalid_crop_region_inverted_bbox())

    def test_reject_zero_area(self):
        """Reject crop region with zero width."""
        with pytest.raises(ValidationError, match="must be greater"):
            CropRegion(**get_invalid_crop_region_zero_area())

    def test_reject_negative_coords(self):
        """Reject negative coordinate values."""
        with pytest.raises(ValidationError):
            CropRegion(**get_invalid_crop_region_negative_coords())

    def test_blank_page_status_default(self):
        """Default blank_page_status is CONTENT_PRESENT."""
        region = CropRegion(
            region_id="TEST",
            x_min_pt=0.0,
            y_min_pt=0.0,
            x_max_pt=100.0,
            y_max_pt=200.0,
            target_width_px=1773,
            target_height_px=2538,
        )
        assert region.blank_page_status == BlankPageStatus.CONTENT_PRESENT

    def test_blank_page_detected(self):
        """Blank page status can be set (non-blocking, Spec §7.C)."""
        region = CropRegion(
            region_id="PAGE-05",
            x_min_pt=0.0,
            y_min_pt=0.0,
            x_max_pt=100.0,
            y_max_pt=200.0,
            target_width_px=1773,
            target_height_px=2538,
            blank_page_status=BlankPageStatus.BLANK_PAGE_DETECTED,
        )
        assert region.blank_page_status == BlankPageStatus.BLANK_PAGE_DETECTED

    def test_quadrant_range(self):
        """Quadrant must be 1-4 or None."""
        with pytest.raises(ValidationError):
            CropRegion(
                region_id="TEST",
                quadrant=5,
                x_min_pt=0.0,
                y_min_pt=0.0,
                x_max_pt=100.0,
                y_max_pt=200.0,
                target_width_px=1773,
                target_height_px=2538,
            )

    def test_serialization_roundtrip(self):
        """CropRegion serializes to JSON and deserializes back."""
        region = CropRegion(**get_valid_crop_region_4up_q1_json())
        json_str = region.model_dump_json()
        restored = CropRegion.model_validate_json(json_str)
        assert restored == region


# =============================================================================
# SECTION 4: PageCropPlan Tests
# =============================================================================

class TestPageCropPlan:
    """Test PageCropPlan model validation and business rules."""

    def test_valid_cover_plan(self):
        """Valid cover plan: CLASSIFIED but MANUAL_REVIEW_REQUIRED (Spec §11 C-01)."""
        plan = PageCropPlan(**get_valid_page_crop_plan_cover_json())
        assert plan.layout_type == LayoutType.COVER_SPREAD
        assert plan.classification_status == ClassificationStatus.CLASSIFIED
        assert plan.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED
        assert ManualReviewFlag.COVER_FORMULA_UNVALIDATED in plan.manual_review_flags
        assert plan.expected_page_yield == 2
        assert len(plan.crop_regions) == 2

    def test_valid_4up_plan(self):
        """Valid 4-Up plan: CLASSIFIED and CROP_READY (Spec §11 C-02)."""
        plan = PageCropPlan(**get_valid_page_crop_plan_4up_json())
        assert plan.layout_type == LayoutType.IMPOSITION_4UP
        assert plan.crop_readiness == CropReadinessStatus.CROP_READY
        assert plan.expected_page_yield == 4
        assert len(plan.crop_regions) == 4

    def test_valid_single_page_plan(self):
        """Valid single page plan: CLASSIFIED and CROP_READY (Spec §11 C-03)."""
        plan = PageCropPlan(**get_valid_page_crop_plan_single_json())
        assert plan.layout_type == LayoutType.SINGLE_PAGE
        assert plan.crop_readiness == CropReadinessStatus.CROP_READY
        assert plan.expected_page_yield == 1
        assert len(plan.crop_regions) == 1

    def test_4up_quadrant_regions_ordered(self):
        """4-Up crop regions have correct quadrant assignments."""
        plan = PageCropPlan(**get_valid_page_crop_plan_4up_json())
        for i, region in enumerate(plan.crop_regions, start=1):
            assert region.quadrant == i
            assert region.region_id == f"PAGE-{i:02d}"

    def test_cover_always_manual_review(self):
        """Cover page MUST be MANUAL_REVIEW_REQUIRED (Spec §8.B.1)."""
        with pytest.raises(ValidationError, match="Cover sheets must have"):
            PageCropPlan(**get_invalid_page_plan_cover_crop_ready())

    def test_rotated_sheet_manual_review(self):
        """Rotated sheet MUST be MANUAL_REVIEW_REQUIRED (Spec §11 C-06)."""
        with pytest.raises(ValidationError, match="Non-zero rotation"):
            PageCropPlan(**get_invalid_page_plan_rotated_crop_ready())

    def test_unknown_layout_no_strategy(self):
        """UNKNOWN_LAYOUT must not have a crop strategy."""
        with pytest.raises(ValidationError, match="UNKNOWN_LAYOUT must have crop_strategy=None"):
            PageCropPlan(**get_invalid_page_plan_unknown_with_strategy())

    def test_manual_review_requires_flags(self):
        """MANUAL_REVIEW_REQUIRED must have at least one flag."""
        with pytest.raises(ValidationError, match="requires at least one"):
            PageCropPlan(**get_invalid_page_plan_manual_review_no_flags())

    def test_page_number_consistency(self):
        """pdf_page_number must equal pdf_page_index + 1."""
        with pytest.raises(ValidationError, match="pdf_page_number.*must equal"):
            PageCropPlan(**get_invalid_page_plan_page_number_mismatch())

    def test_invalid_rotation_value(self):
        """Rotation must be 0, 90, 180, or 270."""
        with pytest.raises(ValidationError, match="rotation must be"):
            PageCropPlan(**get_invalid_page_plan_bad_rotation())

    def test_classified_requires_layout_type(self):
        """CLASSIFIED status must have layout_type assigned."""
        with pytest.raises(ValidationError, match="CLASSIFIED status must have a layout_type"):
            PageCropPlan(**get_invalid_page_plan_classified_no_layout())

    def test_confidence_score_range(self):
        """Confidence score must be in [0.0, 1.0]."""
        base = get_valid_page_crop_plan_4up_json()
        base["confidence_score"] = 1.5
        with pytest.raises(ValidationError):
            PageCropPlan(**base)

    def test_cover_crop_regions_have_correct_ids(self):
        """Cover regions should have BACKCOVER and COVER with distinct target dimensions."""
        plan = PageCropPlan(**get_valid_page_crop_plan_cover_json())
        region_ids = {r.region_id for r in plan.crop_regions}
        assert region_ids == {"BACKCOVER", "COVER"}
        regions = {r.region_id: r for r in plan.crop_regions}
        # BACKCOVER: 1890x2657 @ 300 DPI
        assert regions["BACKCOVER"].target_width_px == 1890
        assert regions["BACKCOVER"].target_height_px == 2657
        # COVER: 630x886 @ 100 DPI
        assert regions["COVER"].target_width_px == 630
        assert regions["COVER"].target_height_px == 886
        # Must not be identical
        assert (regions["BACKCOVER"].target_width_px, regions["BACKCOVER"].target_height_px) != (
            regions["COVER"].target_width_px, regions["COVER"].target_height_px
        )

    def test_flipped_4up_manual_review(self):
        """Flipped 4-Up candidate requires MANUAL_REVIEW_REQUIRED (Spec §11 C-05)."""
        plan = PageCropPlan(
            pdf_page_index=0,
            pdf_page_number=1,
            width_pt=1247.24,
            height_pt=878.74,
            orientation=Orientation.LANDSCAPE,
            rotation=0,
            layout_type=None,
            classification_status=ClassificationStatus.CANDIDATE_IMPOSITION_4UP_FLIPPED,
            confidence_score=0.92,
            crop_strategy=CropStrategyType.IMPOSITION_4UP,
            crop_readiness=CropReadinessStatus.MANUAL_REVIEW_REQUIRED,
            manual_review_flags=[ManualReviewFlag.FLIPPED_ORIENTATION_DETECTED],
            crop_regions=[],
            expected_page_yield=4,
        )
        assert plan.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED

    def test_blank_page_non_blocking(self):
        """Blank page detection is non-blocking: still CROP_READY (Spec §7.C)."""
        data = get_valid_page_crop_plan_4up_json()
        # Set one region to BLANK_PAGE_DETECTED
        data["crop_regions"][2]["blank_page_status"] = "BLANK_PAGE_DETECTED"
        plan = PageCropPlan(**data)
        assert plan.crop_readiness == CropReadinessStatus.CROP_READY
        assert plan.crop_regions[2].blank_page_status == BlankPageStatus.BLANK_PAGE_DETECTED

    def test_serialization_roundtrip(self):
        """PageCropPlan serializes and deserializes correctly."""
        plan = PageCropPlan(**get_valid_page_crop_plan_4up_json())
        json_str = plan.model_dump_json()
        restored = PageCropPlan.model_validate_json(json_str)
        assert restored == plan


# =============================================================================
# SECTION 5: CropValidationResult Tests
# =============================================================================

class TestCropValidationResult:
    """Test CropValidationResult model validation."""

    def test_valid_passing_result(self):
        """Valid passing validation result."""
        result = CropValidationResult(**get_valid_crop_validation_result_json())
        assert result.is_valid is True
        assert result.dimension_match is True
        assert result.errors == []

    def test_valid_failing_result(self):
        """Valid failing validation result."""
        result = CropValidationResult(**get_valid_crop_validation_result_failed_json())
        assert result.is_valid is False
        assert result.dimension_match is False
        assert len(result.errors) == 2

    def test_reject_valid_with_errors(self):
        """Reject is_valid=True with non-empty errors."""
        with pytest.raises(ValidationError, match="inconsistent with non-empty errors"):
            CropValidationResult(**get_invalid_validation_valid_with_errors())

    def test_reject_invalid_no_errors(self):
        """Reject is_valid=False with empty errors."""
        with pytest.raises(ValidationError, match="requires at least one error"):
            CropValidationResult(**get_invalid_validation_invalid_no_errors())

    def test_reject_dimension_mismatch_flag(self):
        """Reject dimension_match=True when actual != expected."""
        with pytest.raises(ValidationError, match="dimension_match.*inconsistent"):
            CropValidationResult(**get_invalid_validation_dimension_mismatch_flag())

    def test_dimension_match_auto_computed(self):
        """dimension_match is auto-computed from actual vs expected dimensions."""
        result = CropValidationResult(
            region_id="PAGE-01",
            pdf_page_index=1,
            is_valid=True,
            actual_width_px=1773,
            actual_height_px=2538,
            expected_width_px=1773,
            expected_height_px=2538,
            errors=[],
            warnings=[],
        )
        assert result.dimension_match is True

    def test_tick_deviation_tolerance_check(self):
        """Tick deviation values are recorded for tolerance validation."""
        result = CropValidationResult(**get_valid_crop_validation_result_json())
        assert result.tick_deviation_x_mm == 0.3
        assert result.tick_deviation_y_mm == 0.2
        assert result.tick_within_tolerance is True

    def test_serialization_roundtrip(self):
        """CropValidationResult serializes and deserializes correctly."""
        result = CropValidationResult(**get_valid_crop_validation_result_json())
        json_str = result.model_dump_json()
        restored = CropValidationResult.model_validate_json(json_str)
        assert restored == result


# =============================================================================
# SECTION 6: DocumentCropPlan Tests
# =============================================================================

class TestDocumentCropPlan:
    """Test DocumentCropPlan model aggregation and validation."""

    def _make_golden_path_document(self) -> DocumentCropPlan:
        """Create the standard 6-page Bookabook golden path document.

        Page 1: Cover Spread → MANUAL_REVIEW_REQUIRED
        Pages 2-6: 4-Up Imposition → CROP_READY
        Total yield: 2 + 5*4 = 22 book pages
        """
        profile = create_default_profile()

        cover_plan = PageCropPlan(**get_valid_page_crop_plan_cover_json())

        content_plans = []
        for page_idx in range(1, 6):
            base = get_valid_page_crop_plan_4up_json()
            base["pdf_page_index"] = page_idx
            base["pdf_page_number"] = page_idx + 1
            offset = (page_idx - 1) * 4
            for i, region in enumerate(base["crop_regions"]):
                region["region_id"] = f"PAGE-{offset + i + 1:02d}"
            content_plans.append(PageCropPlan(**base))

        page_plans = [cover_plan] + content_plans

        return DocumentCropPlan(
            source_filename="Preview COMIC COLLECTION vol 1.pdf",
            total_pdf_pages=6,
            profile=profile,
            page_plans=page_plans,
            document_status=DocumentStatus(
                has_unknown_layout=False,
                has_manual_review_required=True,
                all_pages_crop_ready=False,
                document_status="MANUAL_REVIEW_REQUIRED",
            ),
            expected_total_book_pages=22,
            page_sequence_signature=[
                "COVER_SPREAD",
                "IMPOSITION_4UP",
                "IMPOSITION_4UP",
                "IMPOSITION_4UP",
                "IMPOSITION_4UP",
                "IMPOSITION_4UP",
            ],
        )

    def test_golden_path_document(self):
        """Golden path: 6-page Bookabook yields 22 output pages (Spec §10.B)."""
        doc = self._make_golden_path_document()
        assert doc.total_pdf_pages == 6
        assert doc.expected_total_book_pages == 22
        assert doc.document_status.document_status == "MANUAL_REVIEW_REQUIRED"
        assert doc.document_status.has_manual_review_required is True

    def test_page_sequence_signature(self):
        """Page sequence matches expected pattern."""
        doc = self._make_golden_path_document()
        assert doc.page_sequence_signature[0] == "COVER_SPREAD"
        assert all(
            s == "IMPOSITION_4UP" for s in doc.page_sequence_signature[1:]
        )

    def test_page_count_mismatch_rejected(self):
        """Reject document where page_plans count != total_pdf_pages."""
        profile = create_default_profile()
        plan = PageCropPlan(**get_valid_page_crop_plan_single_json())

        with pytest.raises(ValidationError, match="page_plans count.*does not match"):
            DocumentCropPlan(
                source_filename="test.pdf",
                total_pdf_pages=3,
                profile=profile,
                page_plans=[plan],
                document_status=DocumentStatus(
                    has_unknown_layout=False,
                    has_manual_review_required=False,
                    all_pages_crop_ready=True,
                    document_status="AUTO_READY_FOR_PREVIEW",
                ),
                expected_total_book_pages=1,
                page_sequence_signature=["SINGLE_PAGE"],
            )

    def test_yield_mismatch_rejected(self):
        """Reject document where total yield doesn't match sum of per-page yields."""
        profile = create_default_profile()
        plan = PageCropPlan(**get_valid_page_crop_plan_single_json())

        with pytest.raises(ValidationError, match="expected_total_book_pages.*does not match"):
            DocumentCropPlan(
                source_filename="test.pdf",
                total_pdf_pages=1,
                profile=profile,
                page_plans=[plan],
                document_status=DocumentStatus(
                    has_unknown_layout=False,
                    has_manual_review_required=False,
                    all_pages_crop_ready=True,
                    document_status="AUTO_READY_FOR_PREVIEW",
                ),
                expected_total_book_pages=99,
                page_sequence_signature=["SINGLE_PAGE"],
            )

    def test_auto_ready_document(self):
        """All-CROP_READY document has AUTO_READY_FOR_PREVIEW status."""
        profile = create_default_profile()
        plan = PageCropPlan(**get_valid_page_crop_plan_single_json())

        doc = DocumentCropPlan(
            source_filename="single_page.pdf",
            total_pdf_pages=1,
            profile=profile,
            page_plans=[plan],
            document_status=DocumentStatus(
                has_unknown_layout=False,
                has_manual_review_required=False,
                all_pages_crop_ready=True,
                document_status="AUTO_READY_FOR_PREVIEW",
            ),
            expected_total_book_pages=1,
            page_sequence_signature=["SINGLE_PAGE"],
        )
        assert doc.document_status.document_status == "AUTO_READY_FOR_PREVIEW"

    def test_rejected_unknown_layout(self):
        """Document with UNKNOWN_LAYOUT page must be REJECTED."""
        profile = create_default_profile()
        unknown_plan = PageCropPlan(
            pdf_page_index=0,
            pdf_page_number=1,
            width_pt=500.0,
            height_pt=700.0,
            orientation=Orientation.PORTRAIT,
            rotation=0,
            layout_type=None,
            classification_status=ClassificationStatus.UNKNOWN_LAYOUT,
            confidence_score=0.40,
            crop_strategy=None,
            crop_readiness=CropReadinessStatus.NOT_APPLICABLE,
            manual_review_flags=[],
            crop_regions=[],
            expected_page_yield=0,
        )

        doc = DocumentCropPlan(
            source_filename="unknown.pdf",
            total_pdf_pages=1,
            profile=profile,
            page_plans=[unknown_plan],
            document_status=DocumentStatus(
                has_unknown_layout=True,
                has_manual_review_required=False,
                all_pages_crop_ready=False,
                document_status="REJECTED_UNKNOWN_LAYOUT",
            ),
            expected_total_book_pages=0,
            page_sequence_signature=["UNKNOWN_LAYOUT"],
        )
        assert doc.document_status.document_status == "REJECTED_UNKNOWN_LAYOUT"

    def test_document_status_invalid_combination(self):
        """Reject document status that doesn't match page aggregation."""
        profile = create_default_profile()
        plan = PageCropPlan(**get_valid_page_crop_plan_single_json())

        # Claiming has_unknown_layout=True when no page is UNKNOWN
        with pytest.raises(ValidationError, match="has_unknown_layout"):
            DocumentCropPlan(
                source_filename="test.pdf",
                total_pdf_pages=1,
                profile=profile,
                page_plans=[plan],
                document_status=DocumentStatus(
                    has_unknown_layout=True,
                    has_manual_review_required=False,
                    all_pages_crop_ready=False,
                    document_status="REJECTED_UNKNOWN_LAYOUT",
                ),
                expected_total_book_pages=1,
                page_sequence_signature=["SINGLE_PAGE"],
            )

    def test_serialization_roundtrip(self):
        """Full document plan serializes and deserializes."""
        doc = self._make_golden_path_document()
        json_str = doc.model_dump_json()
        restored = DocumentCropPlan.model_validate_json(json_str)
        assert restored.total_pdf_pages == doc.total_pdf_pages
        assert restored.expected_total_book_pages == doc.expected_total_book_pages


# =============================================================================
# SECTION 7: Profile Factory Tests
# =============================================================================

class TestProfileFactories:
    """Test profile factory functions."""

    def test_default_profile(self):
        """Default profile covers all three strategies."""
        profile = create_default_profile()
        assert len(profile.applicable_strategies) == 3
        assert profile.cover_auto_crop_enabled is False

    def test_cover_profile(self):
        """Cover profile only applies CoverCropStrategy."""
        profile = create_cover_profile()
        assert profile.applicable_strategies == [CropStrategyType.COVER]
        assert profile.cover_auto_crop_enabled is False
        assert profile.profile_id == "bookabook_cover_spread"

    def test_imposition_4up_profile(self):
        """4-Up profile only applies Imposition4UpCropStrategy."""
        profile = create_imposition_4up_profile()
        assert profile.applicable_strategies == [CropStrategyType.IMPOSITION_4UP]
        assert profile.target_content_width_px == 1773
        assert profile.target_content_height_px == 2538
        assert profile.profile_id == "bookabook_imposition_4up"

    def test_single_page_profile(self):
        """Single page profile only applies SinglePageCropStrategy."""
        profile = create_single_page_profile()
        assert profile.applicable_strategies == [CropStrategyType.SINGLE_PAGE]
        assert profile.target_content_width_px == 1773
        assert profile.target_content_height_px == 2538
        assert profile.profile_id == "bookabook_single_page"

    def test_all_profiles_share_same_output_dimensions(self):
        """All profiles use the same 1773×2538 content target."""
        profiles = [
            create_default_profile(),
            create_cover_profile(),
            create_imposition_4up_profile(),
            create_single_page_profile(),
        ]
        for p in profiles:
            assert p.target_content_width_px == 1773
            assert p.target_content_height_px == 2538
            assert p.dpi == 300


# =============================================================================
# SECTION 8: JSON Schema Generation Tests
# =============================================================================

class TestSchemaGeneration:
    """Test JSON Schema generation from Pydantic models."""

    def test_all_schemas_generated(self):
        """All model schemas are generated."""
        schemas = generate_all_schemas()
        expected = {
            "ProjectTrimProfile",
            "CropRegion",
            "PageCropPlan",
            "CropValidationResult",
            "DocumentCropPlan",
            "DocumentStatus",
        }
        assert set(schemas.keys()) == expected

    def test_schemas_are_valid_json(self):
        """All schemas serialize to valid JSON."""
        schemas = generate_all_schemas()
        for name, schema in schemas.items():
            json_str = json.dumps(schema)
            parsed = json.loads(json_str)
            assert isinstance(parsed, dict), f"Schema {name} is not a dict"

    def test_profile_schema_has_required_fields(self):
        """ProjectTrimProfile schema lists required fields."""
        schemas = generate_all_schemas()
        profile_schema = schemas["ProjectTrimProfile"]
        assert "properties" in profile_schema
        props = profile_schema["properties"]
        assert "profile_id" in props
        assert "target_content_width_px" in props
        assert "target_content_height_px" in props
        assert "cover_auto_crop_enabled" in props


# =============================================================================
# SECTION 9: DocumentStatus Tests
# =============================================================================

class TestDocumentStatus:
    """Test DocumentStatus aggregation rules."""

    def test_rejected_unknown_layout(self):
        """has_unknown_layout → REJECTED_UNKNOWN_LAYOUT."""
        status = DocumentStatus(
            has_unknown_layout=True,
            has_manual_review_required=False,
            all_pages_crop_ready=False,
            document_status="REJECTED_UNKNOWN_LAYOUT",
        )
        assert status.document_status == "REJECTED_UNKNOWN_LAYOUT"

    def test_manual_review_required(self):
        """has_manual_review (no unknown) → MANUAL_REVIEW_REQUIRED."""
        status = DocumentStatus(
            has_unknown_layout=False,
            has_manual_review_required=True,
            all_pages_crop_ready=False,
            document_status="MANUAL_REVIEW_REQUIRED",
        )
        assert status.document_status == "MANUAL_REVIEW_REQUIRED"

    def test_auto_ready(self):
        """No unknown, no manual → AUTO_READY_FOR_PREVIEW."""
        status = DocumentStatus(
            has_unknown_layout=False,
            has_manual_review_required=False,
            all_pages_crop_ready=True,
            document_status="AUTO_READY_FOR_PREVIEW",
        )
        assert status.document_status == "AUTO_READY_FOR_PREVIEW"

    def test_invalid_status_string(self):
        """Reject invalid document_status string."""
        with pytest.raises(ValidationError, match="document_status must be one of"):
            DocumentStatus(
                has_unknown_layout=False,
                has_manual_review_required=False,
                all_pages_crop_ready=True,
                document_status="INVALID_STATUS",
            )

    def test_inconsistent_unknown_status(self):
        """Reject: has_unknown=True but status is AUTO_READY."""
        with pytest.raises(ValidationError, match="REJECTED_UNKNOWN_LAYOUT"):
            DocumentStatus(
                has_unknown_layout=True,
                has_manual_review_required=False,
                all_pages_crop_ready=False,
                document_status="AUTO_READY_FOR_PREVIEW",
            )

    def test_inconsistent_manual_review_status(self):
        """Reject: has_manual_review=True but status is AUTO_READY."""
        with pytest.raises(ValidationError, match="MANUAL_REVIEW_REQUIRED"):
            DocumentStatus(
                has_unknown_layout=False,
                has_manual_review_required=True,
                all_pages_crop_ready=False,
                document_status="AUTO_READY_FOR_PREVIEW",
            )


# =============================================================================
# SECTION 10: Single Page Non-Nominal Dimension Policy Test
# =============================================================================

class TestSinglePageNonNominalPolicy:
    """Test that Single Page with non-nominal dimensions triggers review."""

    def test_non_nominal_single_page_manual_review(self):
        """Single Page with non-nominal size → MANUAL_REVIEW_REQUIRED.

        Per user requirement: 'Single Page dengan ukuran non-nominal
        harus masuk manual review sampai kebijakan normalisasi ditentukan.'
        """
        # Non-nominal width (480 pt instead of 425.52 pt) triggers manual review
        plan = PageCropPlan(
            pdf_page_index=0,
            pdf_page_number=1,
            width_pt=480.0,
            height_pt=680.0,
            orientation=Orientation.PORTRAIT,
            rotation=0,
            layout_type=LayoutType.SINGLE_PAGE,
            classification_status=ClassificationStatus.CLASSIFIED,
            confidence_score=0.91,
            crop_strategy=CropStrategyType.SINGLE_PAGE,
            crop_readiness=CropReadinessStatus.MANUAL_REVIEW_REQUIRED,
            manual_review_flags=[ManualReviewFlag.TICK_DEVIATION_EXCEEDED],
            crop_regions=[
                CropRegion(
                    region_id="PAGE-01",
                    x_min_pt=0.0,
                    y_min_pt=0.0,
                    x_max_pt=480.0,
                    y_max_pt=680.0,
                    target_width_px=1773,
                    target_height_px=2538,
                )
            ],
            expected_page_yield=1,
        )
        assert plan.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED

    def test_non_nominal_single_page_crop_ready_rejected(self):
        """Single Page with non-nominal dimensions MUST NOT be CROP_READY.

        Per user requirement: 'Single Page dengan ukuran non-nominal
        harus masuk manual review sampai kebijakan normalisasi ditentukan.'
        """
        data = get_invalid_page_plan_single_non_nominal_crop_ready()
        with pytest.raises(ValidationError, match="must have crop_readiness=MANUAL_REVIEW_REQUIRED"):
            PageCropPlan(**data)

    def test_single_page_within_detection_window_non_nominal_requires_manual_review(self):
        """Single Page within classifier window [415-450]x[590-640] but non-nominal requires review."""
        base = get_valid_page_crop_plan_single_json()
        base["width_pt"] = 440.0
        base["height_pt"] = 620.0
        # When CROP_READY: rejected!
        base["crop_readiness"] = "CROP_READY"
        with pytest.raises(ValidationError, match="must have crop_readiness=MANUAL_REVIEW_REQUIRED"):
            PageCropPlan(**base)

        # When MANUAL_REVIEW_REQUIRED: accepted!
        base["crop_readiness"] = "MANUAL_REVIEW_REQUIRED"
        base["manual_review_flags"] = ["NON_NOMINAL_DIMENSIONS_DETECTED"]
        plan = PageCropPlan(**base)
        assert plan.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED

    def test_single_page_slightly_off_nominal_rejected_as_crop_ready(self):
        """Single Page off by only 0.48 pt must be rejected (no ungrounded ±1 pt tolerance)."""
        base = get_valid_page_crop_plan_single_json()
        base["width_pt"] = 426.0  # +0.48 pt off nominal 425.52
        base["height_pt"] = 609.12
        base["crop_readiness"] = "CROP_READY"
        with pytest.raises(ValidationError, match="must have crop_readiness=MANUAL_REVIEW_REQUIRED"):
            PageCropPlan(**base)

    def test_single_page_exact_nominal_accepted_as_crop_ready(self):
        """Single Page with exact nominal dimensions 425.52x609.12 pt is CROP_READY."""
        base = get_valid_page_crop_plan_single_json()
        base["width_pt"] = 425.52
        base["height_pt"] = 609.12
        base["crop_readiness"] = "CROP_READY"
        plan = PageCropPlan(**base)
        assert plan.crop_readiness == CropReadinessStatus.CROP_READY


# =============================================================================
# SECTION 11: DocumentCropPlan Valid Examples & Serialization
# =============================================================================

class TestDocumentCropPlanGoldenPath:
    """Test full DocumentCropPlan golden path JSON schema serialization."""

    def test_valid_document_crop_plan_json_loads(self):
        """get_valid_document_crop_plan_json loads and validates cleanly."""
        data = get_valid_document_crop_plan_json()
        doc = DocumentCropPlan(**data)
        assert doc.total_pdf_pages == 6
        assert doc.expected_total_book_pages == 22
        assert len(doc.page_plans) == 6
        assert doc.document_status.document_status == "MANUAL_REVIEW_REQUIRED"
        assert doc.page_sequence_signature[0] == "COVER_SPREAD"
        assert all(s == "IMPOSITION_4UP" for s in doc.page_sequence_signature[1:])


# =============================================================================
# SECTION 12: File Writers and Disk Serialization
# =============================================================================

class TestExampleWriters:
    """Test writing and verifying valid, invalid, and profile configuration files."""

    def test_write_profile_configs(self, tmp_path):
        """Test writing profile configs to disk."""
        written = write_profile_configs_to_directory(tmp_path)
        assert len(written) == 4
        expected_names = {
            "profile_default.json",
            "profile_cover.json",
            "profile_imposition_4up.json",
            "profile_single_page.json",
        }
        assert {p.name for p in written} == expected_names
        for p in written:
            data = json.loads(p.read_text(encoding="utf-8"))
            profile = ProjectTrimProfile(**data)
            assert profile.target_content_width_px == 1773
            assert profile.target_content_height_px == 2538

    def test_write_valid_examples(self, tmp_path):
        """Test writing valid example JSON files to disk."""
        written = write_valid_examples(tmp_path)
        assert len(written) == 8
        for p in written:
            assert p.exists()
            assert p.stat().st_size > 0
            data = json.loads(p.read_text(encoding="utf-8"))
            assert isinstance(data, dict)

    def test_write_invalid_examples(self, tmp_path):
        """Test writing invalid example JSON files to disk."""
        written = write_invalid_examples(tmp_path)
        assert len(written) == len(get_all_invalid_examples())
        for p in written:
            assert p.exists()
            assert p.stat().st_size > 0

    def test_all_invalid_examples_fail_model_validation(self):
        """Verify that every invalid example is genuinely rejected by its model."""
        invalid_map = {
            "profile_cover_auto_crop_enabled": (ProjectTrimProfile, get_invalid_profile_cover_auto_crop_enabled()),
            "profile_pixel_mismatch": (ProjectTrimProfile, get_invalid_profile_pixel_mismatch()),
            "profile_id_uppercase": (ProjectTrimProfile, get_invalid_profile_id_uppercase()),
            "profile_identical_cover_dimensions": (ProjectTrimProfile, get_invalid_profile_identical_cover_dimensions()),
            "crop_region_inverted_bbox": (CropRegion, get_invalid_crop_region_inverted_bbox()),
            "crop_region_zero_area": (CropRegion, get_invalid_crop_region_zero_area()),
            "crop_region_negative_coords": (CropRegion, get_invalid_crop_region_negative_coords()),
            "page_plan_cover_crop_ready": (PageCropPlan, get_invalid_page_plan_cover_crop_ready()),
            "page_plan_rotated_crop_ready": (PageCropPlan, get_invalid_page_plan_rotated_crop_ready()),
            "page_plan_unknown_with_strategy": (PageCropPlan, get_invalid_page_plan_unknown_with_strategy()),
            "page_plan_manual_review_no_flags": (PageCropPlan, get_invalid_page_plan_manual_review_no_flags()),
            "page_plan_page_number_mismatch": (PageCropPlan, get_invalid_page_plan_page_number_mismatch()),
            "page_plan_bad_rotation": (PageCropPlan, get_invalid_page_plan_bad_rotation()),
            "page_plan_classified_no_layout": (PageCropPlan, get_invalid_page_plan_classified_no_layout()),
            "page_plan_single_non_nominal_crop_ready": (PageCropPlan, get_invalid_page_plan_single_non_nominal_crop_ready()),
            "validation_valid_with_errors": (CropValidationResult, get_invalid_validation_valid_with_errors()),
            "validation_invalid_no_errors": (CropValidationResult, get_invalid_validation_invalid_no_errors()),
            "validation_dimension_mismatch_flag": (CropValidationResult, get_invalid_validation_dimension_mismatch_flag()),
        }

        for name, (model_cls, data) in invalid_map.items():
            with pytest.raises(ValidationError):
                model_cls(**data)

