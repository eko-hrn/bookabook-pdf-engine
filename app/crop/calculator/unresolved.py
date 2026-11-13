"""Documentation of unresolved technical decisions in Crop Coordinate Calculation.

As mandated by Layout Classifier Specification v1.3.4, unresolved gaps,
rounding discrepancies, and pending stakeholder policies must be explicitly
recorded and must NOT be resolved through arbitrary assumptions.
"""

from __future__ import annotations
from typing import Final


# ---------------------------------------------------------------------------
# UNRESOLVED DECISION 1: Cover Height 1 px Rounding Discrepancy
# Spec §1.23, §8.A.3 Item 1, §14.A.4, §16 Item 1, §17
# ---------------------------------------------------------------------------
UNRESOLVED_ROUNDING_1PX: Final[str] = (
    "COVER_HEIGHT_1PX_DISCREPANCY: "
    "Designer reference file COVER.jpg at 100 DPI is 630x886 px. "
    "Integer 3x scaling (300 DPI / 100 DPI) yields 886 * 3 = 2658 px. "
    "However, direct vector render at 300 DPI of vertical height 637.76068 pt yields "
    "round(637.76068 * 300 / 72) = 2657 px (identical to BACKCOVER.jpg at 300 DPI). "
    "Status: UNRESOLVED_ROUNDING_1PX. Production target for COVER at 300 DPI requires "
    "stakeholder/designer confirmation (2657 px vs 2658 px)."
)


# ---------------------------------------------------------------------------
# UNRESOLVED DECISION 2: Cover Spread Vector vs Target Width Discrepancy
# Spec §8.A.3 Items 2-4, §16 Item 2, §17
# ---------------------------------------------------------------------------
UNRESOLVED_COVER_WIDTH_DISCREPANCY: Final[str] = (
    "COVER_WIDTH_DISCREPANCY: "
    "Observed PDF vector crop marks define: "
    "Back Cover pure vector width = 608.54 - 155.95 = 452.59 pt (1886 px @ 300 DPI), "
    "which is -1.01 pt (-4.22 px, -0.36 mm) compared to designer target 453.60 pt (1890 px). "
    "Front Cover pure vector width = 1105.62 - 651.11 = 454.51 pt (1894 px @ 300 DPI), "
    "which is +0.91 pt (+3.79 px, +0.32 mm) compared to designer target 453.60 pt (1890 px). "
    "Cover vector asymmetry between front and back is 1.92 pt (8.01 px, 0.68 mm). "
    "Status: UNRESOLVED GAP. Because of this asymmetry, Cover Spread auto-crop is strictly "
    "prohibited and PageCropPlan must remain MANUAL_REVIEW_REQUIRED."
)


# ---------------------------------------------------------------------------
# UNRESOLVED DECISION 3: Single Page Non-Nominal Normalization Policy
# Spec §8.B.3, §11 C-03, §16 Item 8, §17
# ---------------------------------------------------------------------------
UNRESOLVED_SINGLE_PAGE_NORMALIZATION_POLICY: Final[str] = (
    "SINGLE_PAGE_NORMALIZATION_POLICY: "
    "Nominal Bookabook Comic A5 single page dimensions are exactly 425.52 x 609.12 pt "
    "(yielding 1773 x 2538 px @ 300 DPI). "
    "The classifier acceptance window permits 415-450 pt width and 590-640 pt height. "
    "However, existing single page PDFs exhibit varied dimensions (e.g. 419.53x595.28 pt, "
    "420.94x595.28 pt, 430.87x606.61 pt, 442.20x623.62 pt). "
    "Until a formal policy (letterbox padding vs. trim-to-bleed vs. proportional resample) "
    "is approved by stakeholders, all non-nominal single page sheets must remain "
    "MANUAL_REVIEW_REQUIRED with flag NON_NOMINAL_DIMENSIONS_DETECTED."
)


ALL_UNRESOLVED_DECISIONS: Final[dict[str, str]] = {
    "UNRESOLVED_ROUNDING_1PX": UNRESOLVED_ROUNDING_1PX,
    "UNRESOLVED_COVER_WIDTH_DISCREPANCY": UNRESOLVED_COVER_WIDTH_DISCREPANCY,
    "UNRESOLVED_SINGLE_PAGE_NORMALIZATION_POLICY": UNRESOLVED_SINGLE_PAGE_NORMALIZATION_POLICY,
}

