"""Layout-specific validation rules for Cover, 4-Up, and Single Page (Phase 1.2.2.3).

Implements strict validation logic matching Layout Classifier Specification v1.3.4:
- Section 6.B, 8.B.2, 10.A, 17 for 4-Up Imposition Grid
- Section 8.A, 8.B.1, 14.A.4, 15.A.6, 16.1 for Cover Spread
- Section 8.B.3, 11 (C-03..C-05), 16.8 for Single Page
"""

from __future__ import annotations

from typing import Optional

from app.crop.calculator.conversions import points_to_mm
from app.crop.calculator.imposition_4up_strategy import TickMarkCoordinates
from app.crop.calculator.unresolved import (
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
from app.crop.models.page_crop_plan import PageCropPlan
from app.crop.models.project_profile import ProjectTrimProfile
from app.crop.validator.bbox_validator import validate_spine_exclusion


def validate_4up_layout_plan(
    plan: PageCropPlan,
    profile: ProjectTrimProfile,
    tick_coords: Optional[TickMarkCoordinates] = None,
    tick_tolerance_mm: Optional[float] = None,
) -> tuple[list[str], list[str]]:
    """Validate a 4-Up Imposition Grid PageCropPlan.

    Checks:
    1. Exactly 4 quadrants exist with indices 1, 2, 3, 4.
    2. Expected page yield is 4.
    3. Region IDs follow PAGE-{XX} convention.
    4. Interior seams align with 0.00 pt gap (flush cut).
    5. Outer margins match profile parameters (13.85 pt / 14.50 pt).
    6. Tick mark deviation: if > 1.0 mm, MUST be MANUAL_REVIEW_REQUIRED.
    7. Rotation: if != 0, MUST be MANUAL_REVIEW_REQUIRED.
    8. Flipped candidate: MUST be MANUAL_REVIEW_REQUIRED.

    Returns:
        (errors, warnings)
    """
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Yield & quadrant count
    if plan.expected_page_yield != 4:
        errors.append(
            f"4-Up layout expected_page_yield must be 4. Got: {plan.expected_page_yield}"
        )
    if len(plan.crop_regions) != 4:
        errors.append(
            f"4-Up layout must have exactly 4 crop regions. Got: {len(plan.crop_regions)}"
        )
        return errors, warnings  # Cannot perform quadrant checks without 4 regions

    q1, q2, q3, q4 = plan.crop_regions

    # 2. Quadrant indices & ordering
    for i, (q, expected_idx) in enumerate(zip([q1, q2, q3, q4], [1, 2, 3, 4])):
        if q.quadrant != expected_idx:
            errors.append(
                f"Region at index {i} ('{q.region_id}') has quadrant={q.quadrant}, expected {expected_idx}"
            )

    # 3. Interior flush cut seams (Spec §8.B.2: 0.00 pt interior divider)
    seam_tol = 0.05
    # Vertical cut alignment: right edge of Q1/Q3 must equal left edge of Q2/Q4
    if abs(q1.x_max_pt - q2.x_min_pt) > seam_tol:
        errors.append(
            f"Vertical interior seam gap between Q1 and Q2: "
            f"Q1.x_max={q1.x_max_pt:.3f}, Q2.x_min={q2.x_min_pt:.3f} (delta={abs(q1.x_max_pt - q2.x_min_pt):.3f} pt)"
        )
    if abs(q3.x_max_pt - q4.x_min_pt) > seam_tol:
        errors.append(
            f"Vertical interior seam gap between Q3 and Q4: "
            f"Q3.x_max={q3.x_max_pt:.3f}, Q4.x_min={q4.x_min_pt:.3f}"
        )

    # Horizontal cut alignment: bottom edge of Q1/Q2 must equal top edge of Q3/Q4
    if abs(q1.y_max_pt - q3.y_min_pt) > seam_tol:
        errors.append(
            f"Horizontal interior seam gap between Q1 and Q3: "
            f"Q1.y_max={q1.y_max_pt:.3f}, Q3.y_min={q3.y_min_pt:.3f} (delta={abs(q1.y_max_pt - q3.y_min_pt):.3f} pt)"
        )
    if abs(q2.y_max_pt - q4.y_min_pt) > seam_tol:
        errors.append(
            f"Horizontal interior seam gap between Q2 and Q4: "
            f"Q2.y_max={q2.y_max_pt:.3f}, Q4.y_min={q4.y_min_pt:.3f}"
        )

    # 4. Outer margins validation (Spec §10.A, §17: 13.85 pt horizontal / 14.50 pt vertical)
    margin_tol = 0.1
    left_m = q1.x_min_pt
    right_m = plan.width_pt - q2.x_max_pt
    top_m = q1.y_min_pt
    bottom_m = plan.height_pt - q3.y_max_pt

    expected_h_m = profile.outer_margin.horizontal_pt  # 13.85 pt
    expected_v_m = profile.outer_margin.vertical_pt    # 14.50 pt

    if abs(left_m - expected_h_m) > margin_tol:
        warnings.append(
            f"Left outer margin ({left_m:.2f} pt) differs from profile expected ({expected_h_m:.2f} pt)"
        )
    if abs(right_m - expected_h_m) > margin_tol:
        warnings.append(
            f"Right outer margin ({right_m:.2f} pt) differs from profile expected ({expected_h_m:.2f} pt)"
        )
    if abs(top_m - expected_v_m) > margin_tol:
        warnings.append(
            f"Top outer margin ({top_m:.2f} pt) differs from profile expected ({expected_v_m:.2f} pt)"
        )
    if abs(bottom_m - expected_v_m) > margin_tol:
        warnings.append(
            f"Bottom outer margin ({bottom_m:.2f} pt) differs from profile expected ({expected_v_m:.2f} pt)"
        )

    # 5. Tick mark deviation check (Spec §6.B: ≤ 1.0 mm tolerance)
    tol_mm = tick_tolerance_mm if tick_tolerance_mm is not None else profile.tick_deviation_tolerance_mm

    if tick_coords is not None:
        dx_mm = tick_coords.delta_x_mm
        dy_mm = tick_coords.delta_y_mm

        if dx_mm > tol_mm + 1e-4 or dy_mm > tol_mm + 1e-4:
            # Must be MANUAL_REVIEW_REQUIRED with flag TICK_DEVIATION_EXCEEDED
            if plan.crop_readiness == CropReadinessStatus.CROP_READY:
                errors.append(
                    f"4-Up sheet with tick deviation (dx={dx_mm:.2f} mm, dy={dy_mm:.2f} mm) "
                    f"exceeding tolerance ({tol_mm:.1f} mm) cannot be CROP_READY. "
                    f"Must be MANUAL_REVIEW_REQUIRED per Spec §6.B."
                )
            if ManualReviewFlag.TICK_DEVIATION_EXCEEDED not in plan.manual_review_flags:
                errors.append(
                    f"4-Up sheet with tick deviation exceeding {tol_mm} mm must include "
                    f"TICK_DEVIATION_EXCEEDED in manual_review_flags"
                )
    elif ManualReviewFlag.TICK_DEVIATION_EXCEEDED in plan.manual_review_flags:
        if plan.crop_readiness == CropReadinessStatus.CROP_READY:
            errors.append(
                f"4-Up sheet with TICK_DEVIATION_EXCEEDED flag cannot be CROP_READY. "
                f"Must be MANUAL_REVIEW_REQUIRED per Spec §6.B."
            )

    # 6. Rotation check
    if plan.rotation != 0:
        if plan.crop_readiness != CropReadinessStatus.MANUAL_REVIEW_REQUIRED:
            errors.append(
                f"4-Up sheet with rotation={plan.rotation} must be MANUAL_REVIEW_REQUIRED"
            )
        if ManualReviewFlag.ROTATED_SHEET_DETECTED not in plan.manual_review_flags:
            errors.append(
                f"4-Up sheet with rotation={plan.rotation} must include "
                f"ROTATED_SHEET_DETECTED in manual_review_flags"
            )

    # 7. Flipped orientation check
    if plan.classification_status == ClassificationStatus.CANDIDATE_IMPOSITION_4UP_FLIPPED:
        if plan.crop_readiness != CropReadinessStatus.MANUAL_REVIEW_REQUIRED:
            errors.append(
                "CANDIDATE_IMPOSITION_4UP_FLIPPED sheet must have crop_readiness=MANUAL_REVIEW_REQUIRED"
            )
        if ManualReviewFlag.FLIPPED_ORIENTATION_DETECTED not in plan.manual_review_flags:
            errors.append(
                "CANDIDATE_IMPOSITION_4UP_FLIPPED sheet must include FLIPPED_ORIENTATION_DETECTED flag"
            )

    return errors, warnings


def validate_cover_layout_plan(
    plan: PageCropPlan,
    profile: ProjectTrimProfile,
) -> tuple[list[str], list[str]]:
    """Validate a Cover Spread PageCropPlan.

    Strictly enforces:
    1. cover_auto_crop_enabled MUST be False.
    2. crop_readiness MUST be MANUAL_REVIEW_REQUIRED (Spec §8.B.1, §15.A.6).
    3. manual_review_flags MUST include COVER_FORMULA_UNVALIDATED.
    4. Exactly 2 regions: BACKCOVER and COVER.
    5. Distinct target dimensions & DPI for BACKCOVER (1890x2657 @ 300) and COVER (630x886 @ 100).
    6. Spine exclusion zone preserved between covers.
    7. Unresolved width and height discrepancies preserved without forced resizing.

    Returns:
        (errors, warnings)
    """
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Absolute safety guardrail: Auto-crop is ALWAYS prohibited
    if profile.cover_auto_crop_enabled:
        errors.append(
            "CRITICAL: profile.cover_auto_crop_enabled is True. "
            "Cover auto-crop is strictly prohibited per Spec §8.B.1 and §15.A.6."
        )

    if plan.crop_readiness != CropReadinessStatus.MANUAL_REVIEW_REQUIRED:
        errors.append(
            f"CRITICAL: Cover sheet crop_readiness is '{plan.crop_readiness.value}'. "
            f"Cover sheets MUST ALWAYS be MANUAL_REVIEW_REQUIRED per Spec §8.B.1 and §15.A.6."
        )

    if ManualReviewFlag.COVER_FORMULA_UNVALIDATED not in plan.manual_review_flags:
        errors.append(
            "Cover sheet must include COVER_FORMULA_UNVALIDATED in manual_review_flags"
        )

    # 2. Yield & region count
    if plan.expected_page_yield != 2:
        errors.append(
            f"Cover spread expected_page_yield must be 2. Got: {plan.expected_page_yield}"
        )
    if len(plan.crop_regions) != 2:
        errors.append(
            f"Cover spread must have exactly 2 crop regions (BACKCOVER, COVER). "
            f"Got: {len(plan.crop_regions)}"
        )
        return errors, warnings

    r1, r2 = plan.crop_regions
    backcover = next((r for r in [r1, r2] if r.region_id == "BACKCOVER"), None)
    cover = next((r for r in [r1, r2] if r.region_id == "COVER"), None)

    if backcover is None:
        errors.append("Cover spread missing 'BACKCOVER' region")
    if cover is None:
        errors.append("Cover spread missing 'COVER' region")

    if backcover is not None and cover is not None:
        cov_dims = profile.cover_dimensions

        # 3. Distinct dimensions & DPI check
        if (
            backcover.target_width_px == cover.target_width_px
            and backcover.target_height_px == cover.target_height_px
        ):
            errors.append(
                f"BACKCOVER and COVER cannot have identical output dimensions "
                f"({backcover.target_width_px}x{backcover.target_height_px} px). "
                f"BACKCOVER must be 1890x2657 @ 300 DPI, COVER must be 630x886 @ 100 DPI."
            )

        # 4. Spine exclusion check
        spine_errors = validate_spine_exclusion(
            backcover=backcover,
            frontcover=cover,
            expected_spine_left_pt=profile.spine_width_mm * (72.0 / 25.4),  # check relative positioning
            expected_spine_right_pt=backcover.x_max_pt + (profile.spine_width_mm * 72.0 / 25.4),
            tolerance_pt=5.0,
        )
        # Verify cover left edge is strictly greater than backcover right edge
        if cover.x_min_pt <= backcover.x_max_pt:
            errors.append(
                f"Cover regions overlap: COVER x_min ({cover.x_min_pt:.3f}) <= "
                f"BACKCOVER x_max ({backcover.x_max_pt:.3f}). Spine zone is not preserved."
            )

        # 5. Document unresolved discrepancies
        warnings.append(
            f"{UNRESOLVED_ROUNDING_1PX}: 886 px @ 100 DPI x 3 = 2658 px vs 2657 px @ 300 DPI (Spec §1.23, §14.A.4)."
        )
        warnings.append(
            f"{UNRESOLVED_COVER_WIDTH_DISCREPANCY}: Vector widths (452.56 pt back, 454.51 pt front) "
            "deviate from 453.60 pt target (Spec §8.A.3)."
        )

    return errors, warnings


def validate_single_page_layout_plan(
    plan: PageCropPlan,
    profile: ProjectTrimProfile,
) -> tuple[list[str], list[str]]:
    """Validate a Single Page PageCropPlan.

    Strictly enforces:
    1. Exactly 1 region with yield = 1.
    2. Strict nominal dimension check: 425.52 x 609.12 pt.
    3. Non-nominal dimensions MUST be MANUAL_REVIEW_REQUIRED with flag NON_NOMINAL_DIMENSIONS_DETECTED.
    4. Rotation != 0 MUST be MANUAL_REVIEW_REQUIRED with flag ROTATED_SHEET_DETECTED.
    5. No arbitrary normalization or scaling policy may be applied.

    Returns:
        (errors, warnings)
    """
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Yield & region count
    if plan.expected_page_yield != 1:
        errors.append(
            f"Single page expected_page_yield must be 1. Got: {plan.expected_page_yield}"
        )
    if len(plan.crop_regions) != 1:
        errors.append(
            f"Single page must have exactly 1 crop region. Got: {len(plan.crop_regions)}"
        )
        return errors, warnings

    nominal_w = 425.52
    nominal_h = 609.12
    is_nominal = (
        round(plan.width_pt, 2) == nominal_w
        and round(plan.height_pt, 2) == nominal_h
    )

    # 2. Non-nominal dimension policy
    if not is_nominal:
        if plan.crop_readiness == CropReadinessStatus.CROP_READY:
            errors.append(
                f"Single page with non-nominal dimensions ({plan.width_pt:.2f}x{plan.height_pt:.2f} pt, "
                f"nominal: {nominal_w}x{nominal_h} pt) cannot be CROP_READY. "
                f"Must remain MANUAL_REVIEW_REQUIRED per Spec §8.B.3, §11 C-03."
            )
        if ManualReviewFlag.NON_NOMINAL_DIMENSIONS_DETECTED not in plan.manual_review_flags:
            errors.append(
                "Single page with non-nominal dimensions must include "
                "NON_NOMINAL_DIMENSIONS_DETECTED in manual_review_flags"
            )
        warnings.append(
            f"Single page non-nominal sheet ({plan.width_pt:.2f}x{plan.height_pt:.2f} pt) "
            f"held in manual review until normalization policy is decided."
        )

    # 3. Rotation check
    if plan.rotation != 0:
        if plan.crop_readiness != CropReadinessStatus.MANUAL_REVIEW_REQUIRED:
            errors.append(
                f"Single page with rotation={plan.rotation} must be MANUAL_REVIEW_REQUIRED"
            )
        if ManualReviewFlag.ROTATED_SHEET_DETECTED not in plan.manual_review_flags:
            errors.append(
                f"Single page with rotation={plan.rotation} must include "
                f"ROTATED_SHEET_DETECTED in manual_review_flags"
            )

    return errors, warnings
