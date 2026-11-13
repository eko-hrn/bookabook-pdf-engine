"""Invalid JSON examples for testing model validation rejection.

Each example targets a specific validation rule defined in the Pydantic
models. These should ALL fail validation when loaded into their
respective model classes.
"""

from __future__ import annotations


def get_invalid_profile_cover_auto_crop_enabled() -> dict:
    """INVALID: cover_auto_crop_enabled=True violates Spec §8.B.1, §15.A.6."""
    return {
        "profile_id": "bad_profile_autocrop",
        "profile_name": "Bad Profile - Cover Auto Crop Enabled",
        "production_basis": "OPTION_B_EXACT_TARGET",
        "dpi": 300,
        "target_content_width_px": 1773,
        "target_content_height_px": 2538,
        "target_content_width_pt": 425.52,
        "target_content_height_pt": 609.12,
        "cover_dimensions": {
            "target_backcover_width_px": 1890,
            "target_backcover_height_px": 2657,
            "target_backcover_dpi": 300,
            "target_cover_width_px": 630,
            "target_cover_height_px": 886,
            "target_cover_dpi": 100,
            "frontcover_height_discrepancy_note": "test"
        },
        "cover_auto_crop_enabled": True,
        "outer_margin": {
            "horizontal_pt": 13.85,
            "vertical_pt": 14.50,
            "horizontal_mm": 4.886,
            "vertical_mm": 5.115
        },
        "tick_deviation_tolerance_mm": 1.0,
        "spine_width_mm": 15.02,
        "spine_excluded": True
    }


def get_invalid_profile_pixel_mismatch() -> dict:
    """INVALID: pixel dimensions don't match pt×dpi/72 conversion."""
    return {
        "profile_id": "bad_profile_px_mismatch",
        "profile_name": "Bad Profile - Pixel Mismatch",
        "production_basis": "OPTION_B_EXACT_TARGET",
        "dpi": 300,
        "target_content_width_px": 1800,
        "target_content_height_px": 2538,
        "target_content_width_pt": 425.52,
        "target_content_height_pt": 609.12,
        "cover_dimensions": {
            "target_backcover_width_px": 1890,
            "target_backcover_height_px": 2657,
            "target_backcover_dpi": 300,
            "target_cover_width_px": 630,
            "target_cover_height_px": 886,
            "target_cover_dpi": 100,
            "frontcover_height_discrepancy_note": "test"
        },
        "cover_auto_crop_enabled": False,
        "outer_margin": {
            "horizontal_pt": 13.85,
            "vertical_pt": 14.50,
            "horizontal_mm": 4.886,
            "vertical_mm": 5.115
        },
        "tick_deviation_tolerance_mm": 1.0,
        "spine_width_mm": 15.02,
        "spine_excluded": True
    }


def get_invalid_profile_id_uppercase() -> dict:
    """INVALID: profile_id contains uppercase characters."""
    return {
        "profile_id": "Bad_Profile_ID",
        "profile_name": "Bad Profile - Uppercase ID",
        "production_basis": "OPTION_B_EXACT_TARGET",
        "dpi": 300,
        "target_content_width_px": 1773,
        "target_content_height_px": 2538,
        "target_content_width_pt": 425.52,
        "target_content_height_pt": 609.12,
        "cover_dimensions": {
            "target_backcover_width_px": 1890,
            "target_backcover_height_px": 2657,
            "target_backcover_dpi": 300,
            "target_cover_width_px": 630,
            "target_cover_height_px": 886,
            "target_cover_dpi": 100,
            "frontcover_height_discrepancy_note": "test"
        },
        "cover_auto_crop_enabled": False,
        "outer_margin": {
            "horizontal_pt": 13.85,
            "vertical_pt": 14.50,
            "horizontal_mm": 4.886,
            "vertical_mm": 5.115
        },
        "tick_deviation_tolerance_mm": 1.0,
        "spine_width_mm": 15.02,
        "spine_excluded": True
    }


def get_invalid_profile_identical_cover_dimensions() -> dict:
    """INVALID: BACKCOVER and COVER assigned identical output dimensions.

    Per specification: BACKCOVER is 1890x2657 @ 300 DPI, COVER is 630x886 @ 100 DPI.
    They must NOT be assigned identical output dimensions.
    """
    return {
        "profile_id": "bad_profile_identical_cover",
        "profile_name": "Bad Profile - Identical Cover Dimensions",
        "production_basis": "OPTION_B_EXACT_TARGET",
        "dpi": 300,
        "target_content_width_px": 1773,
        "target_content_height_px": 2538,
        "target_content_width_pt": 425.52,
        "target_content_height_pt": 609.12,
        "cover_dimensions": {
            "target_backcover_width_px": 1890,
            "target_backcover_height_px": 2657,
            "target_backcover_dpi": 300,
            "target_cover_width_px": 1890,
            "target_cover_height_px": 2657,
            "target_cover_dpi": 300,
            "frontcover_height_discrepancy_note": "test"
        },
        "cover_auto_crop_enabled": False,
        "outer_margin": {
            "horizontal_pt": 13.85,
            "vertical_pt": 14.50,
            "horizontal_mm": 4.886,
            "vertical_mm": 5.115
        },
        "tick_deviation_tolerance_mm": 1.0,
        "spine_width_mm": 15.02,
        "spine_excluded": True
    }


def get_invalid_crop_region_inverted_bbox() -> dict:
    """INVALID: x_max < x_min (inverted bounding box)."""
    return {
        "region_id": "PAGE-01",
        "quadrant": 1,
        "x_min_pt": 439.37,
        "y_min_pt": 14.50,
        "x_max_pt": 13.85,
        "y_max_pt": 623.62,
        "target_width_px": 1773,
        "target_height_px": 2538
    }


def get_invalid_crop_region_zero_area() -> dict:
    """INVALID: zero-width crop region."""
    return {
        "region_id": "PAGE-01",
        "quadrant": 1,
        "x_min_pt": 100.0,
        "y_min_pt": 100.0,
        "x_max_pt": 100.0,
        "y_max_pt": 500.0,
        "target_width_px": 1773,
        "target_height_px": 2538
    }


def get_invalid_crop_region_negative_coords() -> dict:
    """INVALID: negative coordinate values."""
    return {
        "region_id": "PAGE-01",
        "quadrant": 1,
        "x_min_pt": -10.0,
        "y_min_pt": 14.50,
        "x_max_pt": 439.37,
        "y_max_pt": 623.62,
        "target_width_px": 1773,
        "target_height_px": 2538
    }


def get_invalid_page_plan_cover_crop_ready() -> dict:
    """INVALID: Cover page with CROP_READY status (must be MANUAL_REVIEW_REQUIRED)."""
    return {
        "pdf_page_index": 0,
        "pdf_page_number": 1,
        "width_pt": 1247.24,
        "height_pt": 878.74,
        "orientation": "LANDSCAPE",
        "rotation": 0,
        "layout_type": "COVER_SPREAD",
        "classification_status": "CLASSIFIED",
        "confidence_score": 0.95,
        "crop_strategy": "CoverCropStrategy",
        "crop_readiness": "CROP_READY",
        "manual_review_flags": [],
        "crop_regions": [],
        "expected_page_yield": 2
    }


def get_invalid_page_plan_rotated_crop_ready() -> dict:
    """INVALID: Rotated page (90°) with CROP_READY status (Spec §11 C-06)."""
    return {
        "pdf_page_index": 1,
        "pdf_page_number": 2,
        "width_pt": 878.74,
        "height_pt": 1247.24,
        "orientation": "PORTRAIT",
        "rotation": 90,
        "layout_type": "IMPOSITION_4UP",
        "classification_status": "CLASSIFIED",
        "confidence_score": 1.0,
        "crop_strategy": "Imposition4UpCropStrategy",
        "crop_readiness": "CROP_READY",
        "manual_review_flags": [],
        "crop_regions": [],
        "expected_page_yield": 4
    }


def get_invalid_page_plan_unknown_with_strategy() -> dict:
    """INVALID: UNKNOWN_LAYOUT with a crop strategy assigned."""
    return {
        "pdf_page_index": 0,
        "pdf_page_number": 1,
        "width_pt": 500.0,
        "height_pt": 700.0,
        "orientation": "PORTRAIT",
        "rotation": 0,
        "layout_type": None,
        "classification_status": "UNKNOWN_LAYOUT",
        "confidence_score": 0.40,
        "crop_strategy": "SinglePageCropStrategy",
        "crop_readiness": "NOT_APPLICABLE",
        "manual_review_flags": [],
        "crop_regions": [],
        "expected_page_yield": 0
    }


def get_invalid_page_plan_manual_review_no_flags() -> dict:
    """INVALID: MANUAL_REVIEW_REQUIRED without any flags."""
    return {
        "pdf_page_index": 1,
        "pdf_page_number": 2,
        "width_pt": 878.74,
        "height_pt": 1247.24,
        "orientation": "PORTRAIT",
        "rotation": 0,
        "layout_type": "IMPOSITION_4UP",
        "classification_status": "CLASSIFIED",
        "confidence_score": 0.95,
        "crop_strategy": "Imposition4UpCropStrategy",
        "crop_readiness": "MANUAL_REVIEW_REQUIRED",
        "manual_review_flags": [],
        "crop_regions": [],
        "expected_page_yield": 4
    }


def get_invalid_page_plan_page_number_mismatch() -> dict:
    """INVALID: pdf_page_number != pdf_page_index + 1."""
    return {
        "pdf_page_index": 0,
        "pdf_page_number": 5,
        "width_pt": 878.74,
        "height_pt": 1247.24,
        "orientation": "PORTRAIT",
        "rotation": 0,
        "layout_type": "IMPOSITION_4UP",
        "classification_status": "CLASSIFIED",
        "confidence_score": 1.0,
        "crop_strategy": "Imposition4UpCropStrategy",
        "crop_readiness": "CROP_READY",
        "manual_review_flags": [],
        "crop_regions": [],
        "expected_page_yield": 4
    }


def get_invalid_page_plan_bad_rotation() -> dict:
    """INVALID: rotation value 45 (must be 0, 90, 180, or 270)."""
    return {
        "pdf_page_index": 0,
        "pdf_page_number": 1,
        "width_pt": 878.74,
        "height_pt": 1247.24,
        "orientation": "PORTRAIT",
        "rotation": 45,
        "layout_type": "IMPOSITION_4UP",
        "classification_status": "CLASSIFIED",
        "confidence_score": 1.0,
        "crop_strategy": "Imposition4UpCropStrategy",
        "crop_readiness": "CROP_READY",
        "manual_review_flags": [],
        "crop_regions": [],
        "expected_page_yield": 4
    }


def get_invalid_page_plan_classified_no_layout() -> dict:
    """INVALID: CLASSIFIED status without layout_type."""
    return {
        "pdf_page_index": 0,
        "pdf_page_number": 1,
        "width_pt": 878.74,
        "height_pt": 1247.24,
        "orientation": "PORTRAIT",
        "rotation": 0,
        "layout_type": None,
        "classification_status": "CLASSIFIED",
        "confidence_score": 0.95,
        "crop_strategy": "Imposition4UpCropStrategy",
        "crop_readiness": "CROP_READY",
        "manual_review_flags": [],
        "crop_regions": [],
        "expected_page_yield": 4
    }


def get_invalid_validation_valid_with_errors() -> dict:
    """INVALID: is_valid=True but errors list is non-empty."""
    return {
        "region_id": "PAGE-01",
        "pdf_page_index": 1,
        "is_valid": True,
        "expected_width_px": 1773,
        "expected_height_px": 2538,
        "errors": ["Some error that contradicts is_valid=True"],
        "warnings": []
    }


def get_invalid_validation_invalid_no_errors() -> dict:
    """INVALID: is_valid=False but errors list is empty."""
    return {
        "region_id": "PAGE-01",
        "pdf_page_index": 1,
        "is_valid": False,
        "expected_width_px": 1773,
        "expected_height_px": 2538,
        "errors": [],
        "warnings": []
    }


def get_invalid_validation_dimension_mismatch_flag() -> dict:
    """INVALID: dimension_match=True but actual != expected."""
    return {
        "region_id": "PAGE-01",
        "pdf_page_index": 1,
        "is_valid": True,
        "actual_width_px": 1770,
        "actual_height_px": 2538,
        "expected_width_px": 1773,
        "expected_height_px": 2538,
        "dimension_match": True,
        "errors": [],
        "warnings": []
    }


def get_invalid_page_plan_single_non_nominal_crop_ready() -> dict:
    """INVALID: Single Page with non-nominal dimensions set to CROP_READY.

    Per requirements: Single Page with non-nominal dimensions must enter
    manual review until normalization policy is determined.
    """
    return {
        "pdf_page_index": 0,
        "pdf_page_number": 1,
        "width_pt": 480.0,
        "height_pt": 680.0,
        "orientation": "PORTRAIT",
        "rotation": 0,
        "layout_type": "SINGLE_PAGE",
        "classification_status": "CLASSIFIED",
        "confidence_score": 0.95,
        "crop_strategy": "SinglePageCropStrategy",
        "crop_readiness": "CROP_READY",
        "manual_review_flags": [],
        "crop_regions": [
            {
                "region_id": "PAGE-01",
                "quadrant": None,
                "x_min_pt": 0.0,
                "y_min_pt": 0.0,
                "x_max_pt": 480.0,
                "y_max_pt": 680.0,
                "target_width_px": 1773,
                "target_height_px": 2538,
                "blank_page_status": "CONTENT_PRESENT"
            }
        ],
        "expected_page_yield": 1
    }


def get_all_invalid_examples() -> dict[str, dict]:
    """Return all invalid examples keyed by descriptive name."""
    return {
        "profile_cover_auto_crop_enabled": get_invalid_profile_cover_auto_crop_enabled(),
        "profile_pixel_mismatch": get_invalid_profile_pixel_mismatch(),
        "profile_id_uppercase": get_invalid_profile_id_uppercase(),
        "profile_identical_cover_dimensions": get_invalid_profile_identical_cover_dimensions(),
        "crop_region_inverted_bbox": get_invalid_crop_region_inverted_bbox(),
        "crop_region_zero_area": get_invalid_crop_region_zero_area(),
        "crop_region_negative_coords": get_invalid_crop_region_negative_coords(),
        "page_plan_cover_crop_ready": get_invalid_page_plan_cover_crop_ready(),
        "page_plan_rotated_crop_ready": get_invalid_page_plan_rotated_crop_ready(),
        "page_plan_unknown_with_strategy": get_invalid_page_plan_unknown_with_strategy(),
        "page_plan_manual_review_no_flags": get_invalid_page_plan_manual_review_no_flags(),
        "page_plan_page_number_mismatch": get_invalid_page_plan_page_number_mismatch(),
        "page_plan_bad_rotation": get_invalid_page_plan_bad_rotation(),
        "page_plan_classified_no_layout": get_invalid_page_plan_classified_no_layout(),
        "page_plan_single_non_nominal_crop_ready": get_invalid_page_plan_single_non_nominal_crop_ready(),
        "validation_valid_with_errors": get_invalid_validation_valid_with_errors(),
        "validation_invalid_no_errors": get_invalid_validation_invalid_no_errors(),
        "validation_dimension_mismatch_flag": get_invalid_validation_dimension_mismatch_flag(),
    }


def write_invalid_examples(output_dir: str | None = None) -> list:
    """Write all invalid JSON examples to the specified directory.

    If output_dir is None, writes to the directory where this file resides.
    """
    import json
    from pathlib import Path

    if output_dir is None:
        target_dir = Path(__file__).parent
    else:
        target_dir = Path(output_dir)

    target_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for name, data in get_all_invalid_examples().items():
        filename = f"invalid_{name}.json"
        filepath = target_dir / filename
        filepath.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        written.append(filepath)

    return written


if __name__ == "__main__":
    for p in write_invalid_examples():
        print(f"Written invalid example: {p}")

