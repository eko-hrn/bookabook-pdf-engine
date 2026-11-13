"""Unit conversion and geometry validation utilities.

Handles PDF point (pt), pixel (px), and metric millimeter (mm) conversions
using the exact mathematical definitions in Spec v1.3.4 §8, §15, §17.

Constants:
- 1 inch = 72 points (PostScript / PDF standard)
- 1 inch = 25.4 mm (International Yard and Pound agreement)
- Standard resolution: 300 DPI for content & backcover; 100 DPI for frontcover reference.
"""

from __future__ import annotations

import math
from typing import Final


PT_PER_INCH: Final[float] = 72.0
MM_PER_INCH: Final[float] = 25.4
PT_PER_MM: Final[float] = PT_PER_INCH / MM_PER_INCH  # ≈ 2.834645669 pt/mm
MM_PER_PT: Final[float] = MM_PER_INCH / PT_PER_INCH  # ≈ 0.352777778 mm/pt


def points_to_pixels(pt: float, dpi: int = 300) -> int:
    """Convert PDF points to rendered pixels at given DPI with standard rounding.

    Formula (Spec §8.B.2, §15.B.3):
        px = round(pt * dpi / 72.0)
    """
    if dpi <= 0:
        raise ValueError(f"DPI must be positive. Got: {dpi}")
    return round(pt * (dpi / PT_PER_INCH))


def pixels_to_points(px: int, dpi: int = 300) -> float:
    """Convert rendered pixels to PDF points at given DPI.

    Formula (Spec §8.A.2):
        pt = px * 72.0 / dpi
    """
    if dpi <= 0:
        raise ValueError(f"DPI must be positive. Got: {dpi}")
    return round(px * (PT_PER_INCH / dpi), 4)


def mm_to_points(mm: float) -> float:
    """Convert millimeters to PDF points.

    1 mm = 72 / 25.4 pt ≈ 2.8346 pt (Spec §6.B).
    """
    return round(mm * PT_PER_MM, 4)


def points_to_mm(pt: float) -> float:
    """Convert PDF points to millimeters.

    1 pt = 25.4 / 72 mm ≈ 0.3528 mm (Spec §17).
    """
    return round(pt * MM_PER_PT, 4)


def check_tick_deviation(
    delta_x_pt: float,
    delta_y_pt: float,
    tolerance_mm: float = 1.0,
) -> tuple[bool, float, float]:
    """Check if midpoint tick mark deviations are within tolerance.

    Spec §6.B, §8.B.2:
        Tolerance is 1.0 mm (≈ 2.835 pt).
        Deviations exceeding 1.0 mm trigger MANUAL_REVIEW_REQUIRED.

    Returns:
        (within_tolerance, delta_x_mm, delta_y_mm)
    """
    delta_x_mm = points_to_mm(abs(delta_x_pt))
    delta_y_mm = points_to_mm(abs(delta_y_pt))
    # Allow epsilon for floating point representation
    eps = 1e-6
    within_tolerance = (delta_x_mm <= tolerance_mm + eps) and (delta_y_mm <= tolerance_mm + eps)
    return within_tolerance, delta_x_mm, delta_y_mm


def validate_no_stretching(
    width_pt: float,
    height_pt: float,
    target_width_px: int,
    target_height_px: int,
    dpi: int = 300,
    max_distortion_percent: float = 0.5,
) -> tuple[bool, float]:
    """Validate that the crop aspect ratio matches the target pixel aspect ratio.

    Prevents non-uniform scaling / image stretching as mandated by the specification:
    "Tidak boleh melakukan stretching gambar."

    Returns:
        (is_valid, distortion_percent)
    """
    if width_pt <= 0 or height_pt <= 0:
        raise ValueError(f"Dimensions in pt must be positive: {width_pt}x{height_pt}")
    if target_width_px <= 0 or target_height_px <= 0:
        raise ValueError(f"Target dimensions in px must be positive: {target_width_px}x{target_height_px}")

    aspect_ratio_pt = width_pt / height_pt
    aspect_ratio_px = target_width_px / target_height_px

    # Compute percentage distortion between aspect ratios
    distortion_percent = abs(aspect_ratio_pt - aspect_ratio_px) / aspect_ratio_px * 100.0

    is_valid = distortion_percent <= max_distortion_percent
    return is_valid, distortion_percent


def validate_bounding_box(
    x_min: float,
    y_min: float,
    x_max: float,
    y_max: float,
    page_width: float,
    page_height: float,
) -> list[str]:
    """Validate that a bounding box is geometrically sound within the page boundary.

    Returns a list of error strings (empty if valid).
    """
    errors: list[str] = []

    if x_min < 0:
        errors.append(f"x_min ({x_min:.3f}) cannot be negative")
    if y_min < 0:
        errors.append(f"y_min ({y_min:.3f}) cannot be negative")
    if x_max <= x_min:
        errors.append(f"x_max ({x_max:.3f}) must be strictly greater than x_min ({x_min:.3f})")
    if y_max <= y_min:
        errors.append(f"y_max ({y_max:.3f}) must be strictly greater than y_min ({y_min:.3f})")

    # Check bounds against page boundary with small epsilon for rounding
    eps = 0.05
    if x_max > page_width + eps:
        errors.append(f"x_max ({x_max:.3f}) exceeds page width ({page_width:.3f})")
    if y_max > page_height + eps:
        errors.append(f"y_max ({y_max:.3f}) exceeds page height ({page_height:.3f})")

    return errors

