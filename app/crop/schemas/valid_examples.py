"""Valid JSON configuration examples for testing and documentation.

All values are derived from Layout Classifier Specification v1.3.4.
These examples represent the "golden path" Bookabook 6-page PDF
(1 Cover + 5 Imposition 4-Up sheets = 22 output files).
"""

from __future__ import annotations

import json
from pathlib import Path


def get_valid_profile_json() -> dict:
    """Valid ProjectTrimProfile JSON matching Spec §10.A config."""
    return {
        "profile_id": "bookabook_comic_a5_default",
        "profile_name": "Bookabook Comic A5 Standard",
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
            "frontcover_height_discrepancy_note": (
                "100dpi 3x scaling yields 2658 px; vector 300dpi render "
                "yields 2657 px (1 px discrepancy, status UNRESOLVED_ROUNDING_1PX)"
            )
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
        "spine_excluded": True,
        "applicable_strategies": [
            "CoverCropStrategy",
            "Imposition4UpCropStrategy",
            "SinglePageCropStrategy"
        ]
    }


def get_valid_crop_region_4up_q1_json() -> dict:
    """Valid CropRegion for 4-Up Quadrant 1 (Top-Left, PAGE-01).

    Coordinates use anchor point (x_cut, y_cut) = (439.37, 623.62) pt
    as defined in Spec §8.B.2, with content dimensions 425.52 × 609.12 pt.
    """
    return {
        "region_id": "PAGE-01",
        "quadrant": 1,
        "x_min_pt": 13.85,
        "y_min_pt": 14.50,
        "x_max_pt": 439.37,
        "y_max_pt": 623.62,
        "target_width_px": 1773,
        "target_height_px": 2538,
        "blank_page_status": "CONTENT_PRESENT"
    }


def get_valid_page_crop_plan_cover_json() -> dict:
    """Valid PageCropPlan for Cover Spread (Page 1, MANUAL_REVIEW_REQUIRED).

    Per Spec §11 C-01: Cover is CLASSIFIED but MANUAL_REVIEW_REQUIRED.
    """
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
        "crop_readiness": "MANUAL_REVIEW_REQUIRED",
        "manual_review_flags": ["COVER_FORMULA_UNVALIDATED"],
        "crop_regions": [
            {
                "region_id": "BACKCOVER",
                "quadrant": None,
                "x_min_pt": 155.95,
                "y_min_pt": 120.49,
                "x_max_pt": 608.54,
                "y_max_pt": 758.25,
                "target_width_px": 1890,
                "target_height_px": 2657,
                "blank_page_status": "CONTENT_PRESENT"
            },
            {
                "region_id": "COVER",
                "quadrant": None,
                "x_min_pt": 651.11,
                "y_min_pt": 120.49,
                "x_max_pt": 1105.62,
                "y_max_pt": 758.25,
                "target_width_px": 630,
                "target_height_px": 886,
                "blank_page_status": "CONTENT_PRESENT"
            }
        ],
        "expected_page_yield": 2
    }


def get_valid_page_crop_plan_4up_json() -> dict:
    """Valid PageCropPlan for 4-Up Imposition (Page 2, CROP_READY).

    Per Spec §11 C-02: 4-Up with safe tick deviation → CROP_READY.
    Anchor point: (x_cut, y_cut) = (439.37, 623.62) pt.
    """
    x_cut = 439.37
    y_cut = 623.62
    w_net = 425.52
    h_net = 609.12

    return {
        "pdf_page_index": 1,
        "pdf_page_number": 2,
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
        "crop_regions": [
            {
                "region_id": "PAGE-01",
                "quadrant": 1,
                "x_min_pt": round(x_cut - w_net, 2),
                "y_min_pt": round(y_cut - h_net, 2),
                "x_max_pt": x_cut,
                "y_max_pt": y_cut,
                "target_width_px": 1773,
                "target_height_px": 2538,
                "blank_page_status": "CONTENT_PRESENT"
            },
            {
                "region_id": "PAGE-02",
                "quadrant": 2,
                "x_min_pt": x_cut,
                "y_min_pt": round(y_cut - h_net, 2),
                "x_max_pt": round(x_cut + w_net, 2),
                "y_max_pt": y_cut,
                "target_width_px": 1773,
                "target_height_px": 2538,
                "blank_page_status": "CONTENT_PRESENT"
            },
            {
                "region_id": "PAGE-03",
                "quadrant": 3,
                "x_min_pt": round(x_cut - w_net, 2),
                "y_min_pt": y_cut,
                "x_max_pt": x_cut,
                "y_max_pt": round(y_cut + h_net, 2),
                "target_width_px": 1773,
                "target_height_px": 2538,
                "blank_page_status": "CONTENT_PRESENT"
            },
            {
                "region_id": "PAGE-04",
                "quadrant": 4,
                "x_min_pt": x_cut,
                "y_min_pt": y_cut,
                "x_max_pt": round(x_cut + w_net, 2),
                "y_max_pt": round(y_cut + h_net, 2),
                "target_width_px": 1773,
                "target_height_px": 2538,
                "blank_page_status": "CONTENT_PRESENT"
            }
        ],
        "expected_page_yield": 4
    }


def get_valid_page_crop_plan_single_json() -> dict:
    """Valid PageCropPlan for Single Page (CROP_READY).

    Per Spec §11 C-03: Single page with rotation 0 → CROP_READY.
    """
    return {
        "pdf_page_index": 0,
        "pdf_page_number": 1,
        "width_pt": 425.52,
        "height_pt": 609.12,
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
                "x_max_pt": 425.52,
                "y_max_pt": 609.12,
                "target_width_px": 1773,
                "target_height_px": 2538,
                "blank_page_status": "CONTENT_PRESENT"
            }
        ],
        "expected_page_yield": 1
    }


def get_valid_crop_validation_result_json() -> dict:
    """Valid CropValidationResult for a passing 4-Up region."""
    return {
        "region_id": "PAGE-01",
        "pdf_page_index": 1,
        "is_valid": True,
        "actual_width_px": 1773,
        "actual_height_px": 2538,
        "expected_width_px": 1773,
        "expected_height_px": 2538,
        "dimension_match": True,
        "tick_deviation_x_mm": 0.3,
        "tick_deviation_y_mm": 0.2,
        "tick_within_tolerance": True,
        "errors": [],
        "warnings": []
    }


def get_valid_crop_validation_result_failed_json() -> dict:
    """Valid CropValidationResult for a failing validation."""
    return {
        "region_id": "PAGE-01",
        "pdf_page_index": 1,
        "is_valid": False,
        "actual_width_px": 1770,
        "actual_height_px": 2538,
        "expected_width_px": 1773,
        "expected_height_px": 2538,
        "dimension_match": False,
        "tick_deviation_x_mm": 1.5,
        "tick_deviation_y_mm": 0.2,
        "tick_within_tolerance": False,
        "errors": [
            "Dimension mismatch: actual 1770x2538 != expected 1773x2538",
            "Tick deviation X (1.5 mm) exceeds tolerance (1.0 mm)"
        ],
        "warnings": []
    }


def get_valid_document_crop_plan_json() -> dict:
    """Valid DocumentCropPlan JSON for the Bookabook 6-page golden path document.

    Page 1: Cover Spread (MANUAL_REVIEW_REQUIRED, 2 book pages)
    Pages 2-6: 4-Up Imposition (CROP_READY, 4 pages each = 20 book pages)
    Total Yield: 22 book pages (Spec §3.B, §10.B, §11 C-01 & C-02).
    """
    cover_plan = get_valid_page_crop_plan_cover_json()

    x_cut = 439.37
    y_cut = 623.62
    w_net = 425.52
    h_net = 609.12

    content_plans = []
    for page_idx in range(1, 6):
        page_num = page_idx + 1
        page_offset = (page_idx - 1) * 4
        content_plans.append({
            "pdf_page_index": page_idx,
            "pdf_page_number": page_num,
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
            "crop_regions": [
                {
                    "region_id": f"PAGE-{page_offset + 1:02d}",
                    "quadrant": 1,
                    "x_min_pt": round(x_cut - w_net, 2),
                    "y_min_pt": round(y_cut - h_net, 2),
                    "x_max_pt": x_cut,
                    "y_max_pt": y_cut,
                    "target_width_px": 1773,
                    "target_height_px": 2538,
                    "blank_page_status": "CONTENT_PRESENT"
                },
                {
                    "region_id": f"PAGE-{page_offset + 2:02d}",
                    "quadrant": 2,
                    "x_min_pt": x_cut,
                    "y_min_pt": round(y_cut - h_net, 2),
                    "x_max_pt": round(x_cut + w_net, 2),
                    "y_max_pt": y_cut,
                    "target_width_px": 1773,
                    "target_height_px": 2538,
                    "blank_page_status": "CONTENT_PRESENT"
                },
                {
                    "region_id": f"PAGE-{page_offset + 3:02d}",
                    "quadrant": 3,
                    "x_min_pt": round(x_cut - w_net, 2),
                    "y_min_pt": y_cut,
                    "x_max_pt": x_cut,
                    "y_max_pt": round(y_cut + h_net, 2),
                    "target_width_px": 1773,
                    "target_height_px": 2538,
                    "blank_page_status": "CONTENT_PRESENT"
                },
                {
                    "region_id": f"PAGE-{page_offset + 4:02d}",
                    "quadrant": 4,
                    "x_min_pt": x_cut,
                    "y_min_pt": y_cut,
                    "x_max_pt": round(x_cut + w_net, 2),
                    "y_max_pt": round(y_cut + h_net, 2),
                    "target_width_px": 1773,
                    "target_height_px": 2538,
                    "blank_page_status": "CONTENT_PRESENT"
                }
            ],
            "expected_page_yield": 4
        })

    all_page_plans = [cover_plan] + content_plans

    return {
        "source_filename": "Preview COMIC COLLECTION vol 1.pdf",
        "total_pdf_pages": 6,
        "profile": get_valid_profile_json(),
        "page_plans": all_page_plans,
        "document_status": {
            "has_unknown_layout": False,
            "has_manual_review_required": True,
            "all_pages_crop_ready": False,
            "document_status": "MANUAL_REVIEW_REQUIRED"
        },
        "expected_total_book_pages": 22,
        "page_sequence_signature": [
            "COVER_SPREAD",
            "IMPOSITION_4UP",
            "IMPOSITION_4UP",
            "IMPOSITION_4UP",
            "IMPOSITION_4UP",
            "IMPOSITION_4UP"
        ],
        "validation_results": []
    }


def write_valid_examples(output_dir: Path | str) -> list[Path]:
    """Write all valid JSON examples to the specified directory."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    examples = {
        "valid_profile.json": get_valid_profile_json(),
        "valid_crop_region_4up_q1.json": get_valid_crop_region_4up_q1_json(),
        "valid_page_plan_cover.json": get_valid_page_crop_plan_cover_json(),
        "valid_page_plan_4up.json": get_valid_page_crop_plan_4up_json(),
        "valid_page_plan_single.json": get_valid_page_crop_plan_single_json(),
        "valid_document_crop_plan.json": get_valid_document_crop_plan_json(),
        "valid_validation_result_pass.json": get_valid_crop_validation_result_json(),
        "valid_validation_result_fail.json": get_valid_crop_validation_result_failed_json(),
    }

    written: list[Path] = []
    for filename, data in examples.items():
        filepath = output_dir / filename
        filepath.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        written.append(filepath)

    return written


if __name__ == "__main__":
    out = Path(__file__).parent
    for p in write_valid_examples(out):
        print(f"Written: {p}")

