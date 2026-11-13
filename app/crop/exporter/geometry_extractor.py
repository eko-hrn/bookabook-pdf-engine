"""Deterministic PyMuPDF geometry extraction and production crop planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pymupdf

from app.crop.calculator.conversions import validate_bounding_box
from app.crop.calculator.cover_strategy import CoverCropMarks, CoverCropStrategy
from app.crop.calculator.imposition_4up_strategy import (
    Imposition4UpCropStrategy,
    TickMarkCoordinates,
)
from app.crop.calculator.single_page_strategy import SinglePageCropStrategy
from app.crop.exporter.models import PageKind
from app.crop.models.enums import LayoutType


@dataclass(frozen=True)
class PlannedCropTarget:
    """One verified rectangular PDF crop target ready for 300 DPI JPEG rendering."""

    page_key: str
    filename: str
    page_kind: PageKind
    order_index: int
    source_pdf_page: int
    pdf_page_index: int
    quadrant: Optional[int]
    x_min_pt: float
    y_min_pt: float
    x_max_pt: float
    y_max_pt: float
    target_width_px: int
    target_height_px: int
    layout_type: LayoutType
    warnings: list[str]

    @property
    def width_pt(self) -> float:
        return self.x_max_pt - self.x_min_pt

    @property
    def height_pt(self) -> float:
        return self.y_max_pt - self.y_min_pt


def classify_pdf_sheet_layout(
    width_pt: float,
    height_pt: float,
) -> Optional[LayoutType]:
    """Classify a PDF sheet into COVER_SPREAD, IMPOSITION_4UP, or SINGLE_PAGE.

    Supports both full-bleed Cover spreads (~1247x878.74 pt) and pre-trimmed
    Cover sheets (~1259.69x637.80 pt) used in tests.
    """
    if width_pt > height_pt:
        if 1180.0 <= width_pt <= 1350.0 and 600.0 <= height_pt <= 920.0:
            return LayoutType.COVER_SPREAD
        return None

    # 4-Up imposition sheet (Bookabook Comic A5 4-Up portrait ~878.74 x 1247.24 pt)
    if 830.0 <= width_pt <= 930.0 and 1190.0 <= height_pt <= 1310.0:
        return LayoutType.IMPOSITION_4UP

    # Single A5 interior page (~425.52 x 609.12 pt, ±15% heuristic envelope)
    if 380.0 <= width_pt <= 500.0 and 540.0 <= height_pt <= 700.0:
        return LayoutType.SINGLE_PAGE

    return None


def extract_4up_ticks(
    page: pymupdf.Page,
    width_pt: float,
    height_pt: float,
) -> tuple[TickMarkCoordinates, bool]:
    """Extract 4-Up midpoint cut ticks from PyMuPDF vector drawings."""
    center_x = width_pt / 2.0
    center_y = height_pt / 2.0

    top_xs: list[float] = []
    bottom_xs: list[float] = []
    left_ys: list[float] = []
    right_ys: list[float] = []

    try:
        drawings = page.get_drawings()
    except Exception:
        drawings = []

    for drawing in drawings:
        for item in drawing.get("items", []):
            if not item or item[0] != "l":
                continue
            p1, p2 = item[1], item[2]
            dx = abs(p1.x - p2.x)
            dy = abs(p1.y - p2.y)

            # Vertical edge tick near horizontal midpoint
            if dx < 0.25 and 1.0 <= dy <= 35.0:
                x_mid = (p1.x + p2.x) / 2.0
                if abs(x_mid - center_x) <= 25.0:
                    y_min = min(p1.y, p2.y)
                    y_max = max(p1.y, p2.y)
                    if y_min <= 25.0:
                        top_xs.append(x_mid)
                    elif y_max >= height_pt - 25.0:
                        bottom_xs.append(x_mid)

            # Horizontal edge tick near vertical midpoint
            elif dy < 0.25 and 1.0 <= dx <= 35.0:
                y_mid = (p1.y + p2.y) / 2.0
                if abs(y_mid - center_y) <= 25.0:
                    x_min = min(p1.x, p2.x)
                    x_max = max(p1.x, p2.x)
                    if x_min <= 25.0:
                        left_ys.append(y_mid)
                    elif x_max >= width_pt - 25.0:
                        right_ys.append(y_mid)

    found = bool(top_xs or bottom_xs or left_ys or right_ys)
    ticks = TickMarkCoordinates(
        x_top=sum(top_xs) / len(top_xs) if top_xs else center_x,
        x_bottom=sum(bottom_xs) / len(bottom_xs) if bottom_xs else center_x,
        y_left=sum(left_ys) / len(left_ys) if left_ys else center_y,
        y_right=sum(right_ys) / len(right_ys) if right_ys else center_y,
    )
    return ticks, found


def extract_cover_marks(
    page: pymupdf.Page,
    width_pt: float,
    height_pt: float,
) -> CoverCropMarks:
    """Resolve verified Cover crop marks from PDF vector lines or safe defaults.

    Preserves validated vector coordinates without mutating geometry unless
    explicit symmetrical bleed/trim marks match the Cover Spread structure.
    Handles pre-trimmed cover spread sheets (e.g. 1259.69 x 637.80 pt) by
    anchoring symmetrically within actual page bounds while keeping spine exclusion.
    """
    defaults = CoverCropMarks()

    # Handle synthetic or pre-trimmed cover sheets smaller than bleed y_bottom
    if height_pt < defaults.y_bottom - 0.1 or width_pt < defaults.x_right - 0.1:
        spine_half = defaults.spine_width_pt / 2.0
        center_x = width_pt / 2.0
        target_y_top = 0.0
        target_y_bottom = height_pt
        x_left = max(0.0, center_x - spine_half - defaults.backcover_vector_width_pt)
        x_right = min(width_pt, center_x + spine_half + defaults.frontcover_vector_width_pt)
        return CoverCropMarks(
            x_left=x_left,
            x_spine_left=center_x - spine_half,
            x_spine_right=center_x + spine_half,
            x_right=x_right,
            y_top=target_y_top,
            y_bottom=target_y_bottom,
        )

    # Standard full-bleed Cover Spread (~1247.24 x 878.74 pt): verify vector marks
    if abs(width_pt - 1247.24) > 25.0 or abs(height_pt - 878.74) > 25.0:
        return defaults

    try:
        drawings = page.get_drawings()
    except Exception:
        return defaults

    vlines: list[float] = []
    hlines: list[float] = []
    for drawing in drawings:
        for item in drawing.get("items", []):
            if not item or item[0] != "l":
                continue
            p1, p2 = item[1], item[2]
            if abs(p1.x - p2.x) < 0.1:
                vlines.append((p1.x + p2.x) / 2.0)
            elif abs(p1.y - p2.y) < 0.1:
                hlines.append((p1.y + p2.y) / 2.0)

    def _nearest(values: list[float], target: float, tol: float = 0.5) -> float:
        candidates = [v for v in values if abs(v - target) <= tol]
        if not candidates:
            return target
        return min(candidates, key=lambda v: abs(v - target))

    return CoverCropMarks(
        x_left=_nearest(vlines, defaults.x_left),
        x_spine_left=_nearest(vlines, defaults.x_spine_left),
        x_spine_right=_nearest(vlines, defaults.x_spine_right),
        x_right=_nearest(vlines, defaults.x_right),
        y_top=_nearest(hlines, defaults.y_top),
        y_bottom=_nearest(hlines, defaults.y_bottom),
    )


def plan_document_production_crops(
    doc: pymupdf.Document,
    target_dpi: int = 300,
) -> tuple[list[PlannedCropTarget], list[str], list[str]]:
    """Build ordered production crop targets (COVER -> PAGE-01..N -> BACKCOVER).

    Rules enforced:
    - COVER comes strictly from the right side of the spine (front cover).
    - BACKCOVER comes strictly from the left side of the spine.
    - Spine zone between x_spine_left and x_spine_right is excluded (no SPINE.jpg).
    - Every target computes 300 DPI pixel dimensions preserving cropped aspect ratio.
    - Automated validation checks layout, bounds, spine separation, and tick deviation.
    """
    warnings: list[str] = []
    errors: list[str] = []

    if doc.page_count < 1:
        return [], warnings, ["PDF document contains 0 pages."]

    cover_strategy = CoverCropStrategy()
    imp_strategy = Imposition4UpCropStrategy()
    single_strategy = SinglePageCropStrategy()

    cover_target: Optional[PlannedCropTarget] = None
    backcover_target: Optional[PlannedCropTarget] = None
    content_targets: list[PlannedCropTarget] = []

    next_content_page_num = 1

    for idx in range(doc.page_count):
        page = doc[idx]
        width_pt = float(page.rect.width)
        height_pt = float(page.rect.height)
        rotation = int(page.rotation or 0)
        page_num_1based = idx + 1

        layout = classify_pdf_sheet_layout(width_pt, height_pt)
        if layout is None:
            errors.append(
                f"Sheet {page_num_1based} ({width_pt:.2f}x{height_pt:.2f} pt) does not match any supported Bookabook layout."
            )
            continue

        if rotation != 0:
            warnings.append(
                f"Sheet {page_num_1based} reports PDF rotation={rotation} deg; coordinates evaluated in page space."
            )

        if layout == LayoutType.COVER_SPREAD:
            if cover_target is not None or backcover_target is not None:
                warnings.append(
                    f"Additional cover spread detected on sheet {page_num_1based}; using first Cover spread."
                )
                continue

            marks = extract_cover_marks(page, width_pt, height_pt)
            plan = cover_strategy.calculate(
                pdf_page_index=idx,
                page_width_pt=width_pt,
                page_height_pt=height_pt,
                rotation=rotation,
                marks=marks,
                anchor_to_target_width=False,
            )

            region_by_id = {r.region_id: r for r in plan.crop_regions}
            bc_reg = region_by_id.get("BACKCOVER")
            fc_reg = region_by_id.get("COVER")
            if bc_reg is None or fc_reg is None:
                errors.append(
                    f"Sheet {page_num_1based}: Cover spread did not yield both BACKCOVER and COVER regions."
                )
                continue
            if bc_reg.x_max_pt >= fc_reg.x_min_pt:
                errors.append(
                    f"Sheet {page_num_1based}: Spine exclusion failed (BACKCOVER x_max={bc_reg.x_max_pt} >= COVER x_min={fc_reg.x_min_pt})."
                )
                continue

            fc_w_pt = fc_reg.x_max_pt - fc_reg.x_min_pt
            fc_h_pt = fc_reg.y_max_pt - fc_reg.y_min_pt
            bc_w_pt = bc_reg.x_max_pt - bc_reg.x_min_pt
            bc_h_pt = bc_reg.y_max_pt - bc_reg.y_min_pt

            cover_target = PlannedCropTarget(
                page_key="COVER",
                filename="COVER.jpg",
                page_kind=PageKind.COVER,
                order_index=0,
                source_pdf_page=page_num_1based,
                pdf_page_index=idx,
                quadrant=None,
                x_min_pt=fc_reg.x_min_pt,
                y_min_pt=fc_reg.y_min_pt,
                x_max_pt=fc_reg.x_max_pt,
                y_max_pt=fc_reg.y_max_pt,
                target_width_px=round(fc_w_pt * target_dpi / 72.0),
                target_height_px=round(fc_h_pt * target_dpi / 72.0),
                layout_type=LayoutType.COVER_SPREAD,
                warnings=[],
            )
            backcover_target = PlannedCropTarget(
                page_key="BACKCOVER",
                filename="BACKCOVER.jpg",
                page_kind=PageKind.BACKCOVER,
                order_index=99999,
                source_pdf_page=page_num_1based,
                pdf_page_index=idx,
                quadrant=None,
                x_min_pt=bc_reg.x_min_pt,
                y_min_pt=bc_reg.y_min_pt,
                x_max_pt=bc_reg.x_max_pt,
                y_max_pt=bc_reg.y_max_pt,
                target_width_px=round(bc_w_pt * target_dpi / 72.0),
                target_height_px=round(bc_h_pt * target_dpi / 72.0),
                layout_type=LayoutType.COVER_SPREAD,
                warnings=[],
            )
            continue

        if layout == LayoutType.IMPOSITION_4UP:
            ticks, _found_ticks = extract_4up_ticks(page, width_pt, height_pt)
            plan = imp_strategy.calculate(
                pdf_page_index=idx,
                page_width_pt=width_pt,
                page_height_pt=height_pt,
                rotation=rotation,
                ticks=ticks,
                start_page_number=next_content_page_num,
            )
            for flag in plan.manual_review_flags:
                warnings.append(f"Sheet {page_num_1based}: {flag.value}")

            for region in plan.crop_regions:
                r_w_pt = region.x_max_pt - region.x_min_pt
                r_h_pt = region.y_max_pt - region.y_min_pt
                bbox_errs = validate_bounding_box(
                    region.x_min_pt,
                    region.y_min_pt,
                    region.x_max_pt,
                    region.y_max_pt,
                    width_pt,
                    height_pt,
                )
                if bbox_errs:
                    errors.extend(
                        [f"Sheet {page_num_1based} {region.region_id}: {e}" for e in bbox_errs]
                    )
                    continue

                p_key = f"PAGE-{next_content_page_num:02d}"
                content_targets.append(
                    PlannedCropTarget(
                        page_key=p_key,
                        filename=f"{p_key}.jpg",
                        page_kind=PageKind.CONTENT,
                        order_index=next_content_page_num,
                        source_pdf_page=page_num_1based,
                        pdf_page_index=idx,
                        quadrant=region.quadrant,
                        x_min_pt=region.x_min_pt,
                        y_min_pt=region.y_min_pt,
                        x_max_pt=region.x_max_pt,
                        y_max_pt=region.y_max_pt,
                        target_width_px=round(r_w_pt * target_dpi / 72.0),
                        target_height_px=round(r_h_pt * target_dpi / 72.0),
                        layout_type=LayoutType.IMPOSITION_4UP,
                        warnings=[],
                    )
                )
                next_content_page_num += 1
            continue

        if layout == LayoutType.SINGLE_PAGE:
            plan = single_strategy.calculate(
                pdf_page_index=idx,
                page_width_pt=width_pt,
                page_height_pt=height_pt,
                rotation=rotation,
                page_number=next_content_page_num,
            )
            for flag in plan.manual_review_flags:
                warnings.append(f"Sheet {page_num_1based}: {flag.value}")

            for region in plan.crop_regions:
                r_w_pt = region.x_max_pt - region.x_min_pt
                r_h_pt = region.y_max_pt - region.y_min_pt
                p_key = f"PAGE-{next_content_page_num:02d}"
                content_targets.append(
                    PlannedCropTarget(
                        page_key=p_key,
                        filename=f"{p_key}.jpg",
                        page_kind=PageKind.CONTENT,
                        order_index=next_content_page_num,
                        source_pdf_page=page_num_1based,
                        pdf_page_index=idx,
                        quadrant=None,
                        x_min_pt=region.x_min_pt,
                        y_min_pt=region.y_min_pt,
                        x_max_pt=region.x_max_pt,
                        y_max_pt=region.y_max_pt,
                        target_width_px=round(r_w_pt * target_dpi / 72.0),
                        target_height_px=round(r_h_pt * target_dpi / 72.0),
                        layout_type=LayoutType.SINGLE_PAGE,
                        warnings=[],
                    )
                )
                next_content_page_num += 1

    ordered: list[PlannedCropTarget] = []
    if cover_target is not None:
        ordered.append(cover_target)
    ordered.extend(content_targets)
    if backcover_target is not None:
        ordered.append(
            PlannedCropTarget(
                **{
                    **backcover_target.__dict__,
                    "order_index": len(content_targets) + 1,
                }
            )
        )

    return ordered, warnings, errors
