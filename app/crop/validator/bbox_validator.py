"""Bounding box and spatial geometry validation rules (Phase 1.2.2.3).

Validates:
1. Coordinate ordering and positivity.
2. Positive area (rejects zero-area or inverted boxes).
3. Confinement inside MediaBox/CropBox boundaries.
4. Overlap detection (rejects intersecting crop regions while allowing 1D flush-cut seams).
5. Spine zone exclusion enforcement for cover spreads.
"""

from __future__ import annotations

from typing import Optional, Sequence

from app.crop.models.crop_region import CropRegion


def validate_region_geometry(
    region: CropRegion,
    page_width_pt: float,
    page_height_pt: float,
    epsilon: float = 0.05,
) -> list[str]:
    """Validate that a single crop region has valid geometry and is inside the page.

    Returns a list of error strings (empty if valid).
    """
    errors: list[str] = []

    # 1. Non-negativity
    if region.x_min_pt < 0:
        errors.append(f"Region {region.region_id}: x_min_pt ({region.x_min_pt:.3f}) is negative")
    if region.y_min_pt < 0:
        errors.append(f"Region {region.region_id}: y_min_pt ({region.y_min_pt:.3f}) is negative")

    # 2. Ordering
    if region.x_max_pt <= region.x_min_pt:
        errors.append(
            f"Region {region.region_id}: inverted or zero width "
            f"(x_min_pt={region.x_min_pt:.3f}, x_max_pt={region.x_max_pt:.3f})"
        )
    if region.y_max_pt <= region.y_min_pt:
        errors.append(
            f"Region {region.region_id}: inverted or zero height "
            f"(y_min_pt={region.y_min_pt:.3f}, y_max_pt={region.y_max_pt:.3f})"
        )

    # 3. Positive area
    width = region.x_max_pt - region.x_min_pt
    height = region.y_max_pt - region.y_min_pt
    if width <= 0 or height <= 0 or (width * height) <= 0:
        errors.append(
            f"Region {region.region_id}: non-positive area ({width:.3f} x {height:.3f} pt)"
        )

    # 4. Enclosure within page MediaBox
    if region.x_max_pt > page_width_pt + epsilon:
        errors.append(
            f"Region {region.region_id}: x_max_pt ({region.x_max_pt:.3f}) "
            f"exceeds page width ({page_width_pt:.3f} pt)"
        )
    if region.y_max_pt > page_height_pt + epsilon:
        errors.append(
            f"Region {region.region_id}: y_max_pt ({region.y_max_pt:.3f}) "
            f"exceeds page height ({page_height_pt:.3f} pt)"
        )

    return errors


def detect_region_overlaps(
    regions: Sequence[CropRegion],
    seam_tolerance_pt: float = 0.05,
) -> list[str]:
    """Detect overlapping interior areas among crop regions on the same sheet.

    Adjacent quadrants that meet at a 1D boundary (flush cut) have an overlap
    dimension of 0.0 pt and are NOT considered overlapping. An overlap error is
    only reported when two regions share a 2D interior area > seam_tolerance_pt^2.

    Returns a list of error strings (empty if no invalid overlaps).
    """
    errors: list[str] = []
    n = len(regions)

    for i in range(n):
        for j in range(i + 1, n):
            r1 = regions[i]
            r2 = regions[j]

            # Compute 2D intersection
            overlap_x = min(r1.x_max_pt, r2.x_max_pt) - max(r1.x_min_pt, r2.x_min_pt)
            overlap_y = min(r1.y_max_pt, r2.y_max_pt) - max(r1.y_min_pt, r2.y_min_pt)

            # Both X and Y overlap must exceed tolerance for a 2D area overlap
            if overlap_x > seam_tolerance_pt and overlap_y > seam_tolerance_pt:
                overlap_area = overlap_x * overlap_y
                errors.append(
                    f"Overlapping crop regions detected: '{r1.region_id}' and '{r2.region_id}' "
                    f"intersect by {overlap_x:.2f} x {overlap_y:.2f} pt (area={overlap_area:.2f} pt²)"
                )

    return errors


def validate_spine_exclusion(
    backcover: CropRegion,
    frontcover: CropRegion,
    expected_spine_left_pt: float = 608.51709,
    expected_spine_right_pt: float = 651.10938,
    tolerance_pt: float = 0.1,
) -> list[str]:
    """Validate that the central spine zone is strictly excluded between cover regions.

    Spec §8.A.1, §8.B.1:
    - Back cover must not extend into spine (x_max <= spine_left).
    - Front cover must not extend into spine (x_min >= spine_right).
    - Front cover must be strictly to the right of back cover.
    """
    errors: list[str] = []

    # 1. Back cover boundary
    if backcover.x_max_pt > expected_spine_left_pt + tolerance_pt:
        errors.append(
            f"Back cover right edge ({backcover.x_max_pt:.3f} pt) extends into the spine zone "
            f"(spine_left={expected_spine_left_pt:.3f} pt)"
        )

    # 2. Front cover boundary
    if frontcover.x_min_pt < expected_spine_right_pt - tolerance_pt:
        errors.append(
            f"Front cover left edge ({frontcover.x_min_pt:.3f} pt) extends into the spine zone "
            f"(spine_right={expected_spine_right_pt:.3f} pt)"
        )

    # 3. Gap between covers
    gap = frontcover.x_min_pt - backcover.x_max_pt
    if gap <= 0:
        errors.append(
            f"No spine separation between backcover and frontcover: gap={gap:.3f} pt"
        )

    return errors

