"""Enumeration types for the Crop Plan & Preview Architecture.

All enum values are derived from Layout Classifier Specification v1.3.4.
Do NOT modify enum members without updating the specification first.
"""

from enum import Enum


class LayoutType(str, Enum):
    """Layout types identified by the classifier (Spec §4, §11)."""

    COVER_SPREAD = "COVER_SPREAD"
    IMPOSITION_4UP = "IMPOSITION_4UP"
    SINGLE_PAGE = "SINGLE_PAGE"


class CropStrategyType(str, Enum):
    """Crop strategy types mapped 1:1 to layout types (Spec §8.B)."""

    COVER = "CoverCropStrategy"
    IMPOSITION_4UP = "Imposition4UpCropStrategy"
    SINGLE_PAGE = "SinglePageCropStrategy"


class ClassificationStatus(str, Enum):
    """Layout classification status from the classifier engine (Spec §2, §11).

    These represent the outcome of TAHAP 1: In-Memory Layout Classifier Engine.
    """

    CLASSIFIED = "CLASSIFIED"
    UNKNOWN_LAYOUT = "UNKNOWN_LAYOUT"
    CANDIDATE_IMPOSITION_4UP_FLIPPED = "CANDIDATE_IMPOSITION_4UP_FLIPPED"


class CropReadinessStatus(str, Enum):
    """Crop execution readiness status from safety guardrails (Spec §2, §11).

    These represent the outcome of TAHAP 2: Crop Strategy Router &
    Safety Guardrails Validator.
    """

    CROP_READY = "CROP_READY"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Orientation(str, Enum):
    """PDF page orientation (Spec §3.A.1)."""

    LANDSCAPE = "LANDSCAPE"
    PORTRAIT = "PORTRAIT"
    SQUARE = "SQUARE"


class ProductionBasis(str, Enum):
    """Production output dimension basis (Spec §15.A.5)."""

    OPTION_B_EXACT_TARGET = "OPTION_B_EXACT_TARGET"


class ManualReviewFlag(str, Enum):
    """Flags indicating reason for manual review hold (Spec §2, §6, §8, §11).

    Multiple flags may be present on a single page.
    """

    COVER_FORMULA_UNVALIDATED = "COVER_FORMULA_UNVALIDATED"
    TICK_DEVIATION_EXCEEDED = "TICK_DEVIATION_EXCEEDED"
    TICK_ASYMMETRY_DETECTED = "TICK_ASYMMETRY_DETECTED"
    FLIPPED_ORIENTATION_DETECTED = "FLIPPED_ORIENTATION_DETECTED"
    ROTATED_SHEET_DETECTED = "ROTATED_SHEET_DETECTED"
    OPENCV_FALLBACK_USED = "OPENCV_FALLBACK_USED"
    NON_NOMINAL_DIMENSIONS_DETECTED = "NON_NOMINAL_DIMENSIONS_DETECTED"


class BlankPageStatus(str, Enum):
    """Blank page detection status (Spec §7.B).

    All statuses remain CROP_READY (non-blocking warning).
    """

    CONTENT_PRESENT = "CONTENT_PRESENT"
    LOW_CONTRAST_BLANK_SUSPECTED = "LOW_CONTRAST_BLANK_SUSPECTED"
    BLANK_PAGE_DETECTED = "BLANK_PAGE_DETECTED"

