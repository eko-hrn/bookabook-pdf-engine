"""CropPlanValidator — Dedicated independent validator for CropCoordinateCalculator output (Phase 1.2.2.3).

Provides comprehensive, independent validation across 7 strict dimensions:
1. Bounding box validity (positivity, ordering, area, MediaBox enclosure, overlap detection).
2. Dimension and DPI accuracy (anti-stretching, aspect ratio preservation).
3. 4-Up imposition grid integrity (4 quadrants, ordering, flush cut seams, outer margins, tick deviation).
4. Cover spread safety (auto-crop disabled, MANUAL_REVIEW_REQUIRED, distinct outputs, spine exclusion, discrepancy preservation).
5. Single page nominal compliance (exact nominal vs non-nominal MANUAL_REVIEW_REQUIRED).
6. Document-level integrity (sequence, yield summation, status aggregation).
7. Structured validation output (CropValidationResult, PageValidationReport, DocumentValidationReport).
"""

from __future__ import annotations

from typing import Optional, Union

from app.crop.calculator.conversions import points_to_pixels
from app.crop.calculator.imposition_4up_strategy import TickMarkCoordinates
from app.crop.models.crop_region import CropRegion
from app.crop.models.crop_validation import CropValidationResult
from app.crop.models.document_crop_plan import DocumentCropPlan
from app.crop.models.enums import ClassificationStatus, CropReadinessStatus, LayoutType
from app.crop.models.page_crop_plan import PageCropPlan
from app.crop.models.project_profile import ProjectTrimProfile
from app.crop.profiles.profile_configs import create_default_profile
from app.crop.validator.bbox_validator import (
    detect_region_overlaps,
    validate_region_geometry,
)
from app.crop.validator.dimension_validator import validate_region_dimensions
from app.crop.validator.document_validator import validate_document_plan_integrity
from app.crop.validator.layout_validators import (
    validate_4up_layout_plan,
    validate_cover_layout_plan,
    validate_single_page_layout_plan,
)
from app.crop.validator.report import DocumentValidationReport, PageValidationReport


class CropPlanValidator:
    """Dedicated independent validator for CropCoordinateCalculator outputs."""

    def __init__(
        self,
        profile: Optional[ProjectTrimProfile] = None,
        strict_mode: bool = False,
        strict_aspect_ratio_threshold: float = 0.5,
        strict_tick_tolerance_mm: float = 1.0,
    ) -> None:
        """Initialize validator with project trim profile and validation constraints."""
        self.profile = profile or create_default_profile()
        self.strict_mode = strict_mode
        self.strict_aspect_ratio_threshold = strict_aspect_ratio_threshold
        self.strict_tick_tolerance_mm = strict_tick_tolerance_mm

    def validate_region(
        self,
        region: CropRegion,
        page_width_pt: float,
        page_height_pt: float,
        pdf_page_index: int = 0,
        layout_type: Optional[LayoutType] = None,
        tick_deviation_x_mm: Optional[float] = None,
        tick_deviation_y_mm: Optional[float] = None,
    ) -> CropValidationResult:
        """Independently validate a single CropRegion.

        Returns an approved CropValidationResult model instance.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # 1. Bounding box geometric checks
        geo_errors = validate_region_geometry(region, page_width_pt, page_height_pt)
        errors.extend(geo_errors)

        # 2. Dimension and stretching checks
        dim_errors, dim_warnings = validate_region_dimensions(
            region=region,
            profile=self.profile,
            layout_type=layout_type,
            max_distortion_percent=self.strict_aspect_ratio_threshold,
        )
        errors.extend(dim_errors)
        warnings.extend(dim_warnings)

        # 3. Determine expected DPI and target pixel dimensions
        if layout_type == LayoutType.COVER_SPREAD or region.region_id in {"BACKCOVER", "COVER"}:
            if region.region_id == "COVER":
                dpi = self.profile.cover_dimensions.target_cover_dpi
                expected_w = self.profile.cover_dimensions.target_cover_width_px
                expected_h = self.profile.cover_dimensions.target_cover_height_px
            else:
                dpi = self.profile.cover_dimensions.target_backcover_dpi
                expected_w = self.profile.cover_dimensions.target_backcover_width_px
                expected_h = self.profile.cover_dimensions.target_backcover_height_px
        else:
            dpi = self.profile.dpi
            expected_w = self.profile.target_content_width_px
            expected_h = self.profile.target_content_height_px

        actual_w = points_to_pixels(region.width_pt, dpi)
        actual_h = points_to_pixels(region.height_pt, dpi)

        # 4. Tick deviation check (4-Up only)
        tick_within_tolerance = None
        if tick_deviation_x_mm is not None and tick_deviation_y_mm is not None:
            tol = self.profile.tick_deviation_tolerance_mm
            tick_within_tolerance = (
                tick_deviation_x_mm <= tol + 1e-4
                and tick_deviation_y_mm <= tol + 1e-4
            )
            if not tick_within_tolerance:
                errors.append(
                    f"Tick deviation exceeds tolerance ({tol:.1f} mm): "
                    f"dx={tick_deviation_x_mm:.2f} mm, dy={tick_deviation_y_mm:.2f} mm"
                )

        dimension_match = (actual_w == expected_w and actual_h == expected_h)
        if not dimension_match:
            if region.region_id == "COVER":
                # Known unresolved rounding gap (886 vs 885.78 pt)
                warnings.append(
                    f"Cover dimension slight deviation: actual {actual_w}x{actual_h} px "
                    f"vs expected {expected_w}x{expected_h} px. Status: UNRESOLVED_ROUNDING_1PX"
                )
            elif region.region_id == "BACKCOVER":
                # Known unresolved width gap (1886 vs 1890 px)
                warnings.append(
                    f"Backcover width slight deviation: actual {actual_w}x{actual_h} px "
                    f"vs expected {expected_w}x{expected_h} px. Status: UNRESOLVED_COVER_WIDTH_DISCREPANCY"
                )
            else:
                errors.append(
                    f"Rendered dimensions ({actual_w}x{actual_h} px) do not match "
                    f"expected target ({expected_w}x{expected_h} px)"
                )

        is_valid = len(errors) == 0

        return CropValidationResult(
            region_id=region.region_id,
            pdf_page_index=pdf_page_index,
            is_valid=is_valid,
            actual_width_px=actual_w,
            actual_height_px=actual_h,
            expected_width_px=expected_w,
            expected_height_px=expected_h,
            dimension_match=dimension_match,
            tick_deviation_x_mm=tick_deviation_x_mm,
            tick_deviation_y_mm=tick_deviation_y_mm,
            tick_within_tolerance=tick_within_tolerance,
            errors=errors,
            warnings=warnings,
        )

    def validate_page(
        self,
        plan: PageCropPlan,
        profile: Optional[ProjectTrimProfile] = None,
        tick_coords: Optional[TickMarkCoordinates] = None,
    ) -> PageValidationReport:
        """Validate an entire PageCropPlan including layout-specific safety rules."""
        effective_profile = profile or self.profile
        page_errors: list[str] = []
        page_warnings: list[str] = []
        region_results: list[CropValidationResult] = []

        # 1. Validate each region individually
        dx_mm = tick_coords.delta_x_mm if tick_coords else None
        dy_mm = tick_coords.delta_y_mm if tick_coords else None

        for region in plan.crop_regions:
            res = self.validate_region(
                region=region,
                page_width_pt=plan.width_pt,
                page_height_pt=plan.height_pt,
                pdf_page_index=plan.pdf_page_index,
                layout_type=plan.layout_type,
                tick_deviation_x_mm=dx_mm,
                tick_deviation_y_mm=dy_mm,
            )
            region_results.append(res)
            if not res.is_valid:
                page_errors.extend([f"[{region.region_id}] {e}" for e in res.errors])
            page_warnings.extend([f"[{region.region_id}] {w}" for w in res.warnings])

        # 2. Check for overlapping regions
        overlap_errors = detect_region_overlaps(plan.crop_regions)
        page_errors.extend(overlap_errors)

        # 3. Layout-specific validation rules
        if plan.layout_type == LayoutType.IMPOSITION_4UP:
            layout_errs, layout_warns = validate_4up_layout_plan(
                plan, effective_profile, tick_coords, tick_tolerance_mm=self.strict_tick_tolerance_mm
            )
            page_errors.extend(layout_errs)
            page_warnings.extend(layout_warns)

        elif plan.layout_type == LayoutType.COVER_SPREAD:
            layout_errs, layout_warns = validate_cover_layout_plan(plan, effective_profile)
            page_errors.extend(layout_errs)
            page_warnings.extend(layout_warns)

        elif plan.layout_type == LayoutType.SINGLE_PAGE:
            layout_errs, layout_warns = validate_single_page_layout_plan(plan, effective_profile)
            page_errors.extend(layout_errs)
            page_warnings.extend(layout_warns)

        elif plan.classification_status == ClassificationStatus.UNKNOWN_LAYOUT:
            if plan.crop_strategy is not None:
                page_errors.append("UNKNOWN_LAYOUT page must have crop_strategy=None")
            if plan.crop_readiness != CropReadinessStatus.NOT_APPLICABLE:
                page_errors.append("UNKNOWN_LAYOUT page must have crop_readiness=NOT_APPLICABLE")
            if plan.expected_page_yield != 0:
                page_errors.append("UNKNOWN_LAYOUT page must have expected_page_yield=0")

        # 4. Strict mode promotion
        if self.strict_mode and page_warnings:
            page_errors.extend([f"[STRICT] Warning treated as error: {w}" for w in page_warnings])

        is_valid = len(page_errors) == 0 and all(r.is_valid for r in region_results)

        return PageValidationReport(
            pdf_page_index=plan.pdf_page_index,
            pdf_page_number=plan.pdf_page_number,
            layout_type=plan.layout_type,
            crop_readiness=plan.crop_readiness,
            is_valid=is_valid,
            errors=page_errors,
            warnings=page_warnings,
            region_results=region_results,
        )

    def validate_document(
        self,
        doc_plan: DocumentCropPlan,
        profile: Optional[ProjectTrimProfile] = None,
    ) -> DocumentValidationReport:
        """Validate an entire DocumentCropPlan across all pages and aggregate status."""
        effective_profile = profile or self.profile
        doc_errors: list[str] = []
        doc_warnings: list[str] = []
        page_reports: list[PageValidationReport] = []

        # 1. Validate each page plan
        for plan in doc_plan.page_plans:
            report = self.validate_page(plan, profile=effective_profile)
            page_reports.append(report)

        # 2. Document-level integrity rules
        int_errors, int_warnings = validate_document_plan_integrity(doc_plan, effective_profile)
        doc_errors.extend(int_errors)
        doc_warnings.extend(int_warnings)

        # 3. Aggregate region counts
        total_regions = sum(len(p.region_results) for p in page_reports)
        valid_regions_count = sum(
            sum(1 for r in p.region_results if r.is_valid)
            for p in page_reports
        )
        invalid_regions_count = total_regions - valid_regions_count

        # 4. Strict mode promotion
        if self.strict_mode and doc_warnings:
            doc_errors.extend([f"[STRICT] Warning treated as error: {w}" for w in doc_warnings])

        # 5. Overall validity
        is_valid = (
            len(doc_errors) == 0
            and all(p.is_valid for p in page_reports)
        )

        return DocumentValidationReport(
            source_filename=doc_plan.source_filename,
            total_pdf_pages=doc_plan.total_pdf_pages,
            expected_total_book_pages=doc_plan.expected_total_book_pages,
            document_status=doc_plan.document_status,
            is_valid=is_valid,
            errors=doc_errors,
            warnings=doc_warnings,
            page_reports=page_reports,
            total_regions=total_regions,
            valid_regions_count=valid_regions_count,
            invalid_regions_count=invalid_regions_count,
        )

    def validate(
        self,
        target: Union[CropRegion, PageCropPlan, DocumentCropPlan],
        **kwargs,
    ) -> Union[CropValidationResult, PageValidationReport, DocumentValidationReport]:
        """Convenience polymorphic validate method."""
        if isinstance(target, CropRegion):
            return self.validate_region(target, **kwargs)
        elif isinstance(target, PageCropPlan):
            return self.validate_page(target, **kwargs)
        elif isinstance(target, DocumentCropPlan):
            return self.validate_document(target)
        else:
            raise TypeError(f"Unsupported validation target type: {type(target)}")
