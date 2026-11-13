"""Preview Visualization Engine (Phase 1.2.2.4).

Main visualization coordinator for generating structured preview payloads
and vector preview overlays for PDF page sheets.

Key Principles:
1. Pure coordinate transformation: respects PyMuPDF top-left convention.
2. Uniform scaling: strictly preserves physical page aspect ratio (zero stretching).
3. Visual styling: uses distinct stroke patterns, colors, and accessible text badges.
4. Comprehensive overlays:
   - 4-Up: Q1-Q4 boxes, midpoint cut lines, outer trim boundaries, page labels (PAGE-01..PAGE-20).
   - Cover: BACKCOVER & COVER boxes, spine exclusion zone (15.02 mm), manual review mark,
     auto-crop disabled flag, unresolved discrepancies preserved.
   - Single Page: crop boundary, non-nominal dimension identification, review warnings.
5. Strict separation of preview metadata from production raster rendering.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union

from PIL import Image

from app.crop.calculator.conversions import points_to_mm
from app.crop.calculator.cover_strategy import (
    DEFAULT_COVER_SPINE_INNER_LEFT_PT,
    DEFAULT_COVER_SPINE_INNER_RIGHT_PT,
    CoverCropMarks,
)
from app.crop.calculator.imposition_4up_strategy import (
    NOMINAL_4UP_HALF_HEIGHT_PT,
    NOMINAL_4UP_HALF_WIDTH_PT,
    TickMarkCoordinates,
)
from app.crop.calculator.unresolved import (
    UNRESOLVED_COVER_WIDTH_DISCREPANCY,
    UNRESOLVED_ROUNDING_1PX,
    UNRESOLVED_SINGLE_PAGE_NORMALIZATION_POLICY,
)
from app.crop.models.document_crop_plan import DocumentCropPlan
from app.crop.models.enums import ClassificationStatus, CropReadinessStatus, LayoutType
from app.crop.models.page_crop_plan import PageCropPlan
from app.crop.preview.compositor import PreviewCompositor
from app.crop.preview.models import (
    PreviewBox,
    PreviewDocumentPayload,
    PreviewImageOutput,
    PreviewLine,
    PreviewPagePayload,
    PreviewRegion,
    PreviewSpineZone,
    PreviewStatusBadge,
)
from app.crop.preview.pdf_renderer import PDFPageRenderer
from app.crop.preview.svg_renderer import SVGRenderer
from app.crop.preview.theme import (
    STYLE_MIDPOINT_CUT,
    STYLE_OUTER_TRIM,
    STYLE_SPINE_EXCLUSION,
    get_status_style,
)
from app.crop.preview.transformer import CoordinateTransformer


class PreviewVisualizationEngine:
    """Coordinator for preview coordinate generation, payload assembly, and SVG visualization."""

    def __init__(
        self,
        default_canvas_width: float = 800.0,
        default_canvas_height: float = 600.0,
        default_dpi: int = 100,
    ) -> None:
        """Initialize preview visualization engine."""
        self.default_canvas_width = default_canvas_width
        self.default_canvas_height = default_canvas_height
        self.default_dpi = default_dpi
        self._svg_renderer = SVGRenderer()
        self._pdf_renderer = PDFPageRenderer(default_dpi=default_dpi)
        self._compositor = PreviewCompositor()

    def generate_page_preview(
        self,
        page_plan: PageCropPlan,
        canvas_width: Optional[float] = None,
        canvas_height: Optional[float] = None,
        tick_coords: Optional[TickMarkCoordinates] = None,
        cover_marks: Optional[CoverCropMarks] = None,
        margin_padding_px: float = 20.0,
    ) -> PreviewPagePayload:
        """Generate a complete structured PreviewPagePayload for a single PageCropPlan.

        Strictly guarantees:
        - Aspect ratio preservation (no stretching).
        - PyMuPDF top-left coordinate mapping.
        - Inclusion of all guidelines, labels, and safety badges.
        """
        c_w = canvas_width or self.default_canvas_width
        c_h = canvas_height or self.default_canvas_height

        transformer = CoordinateTransformer(
            page_width_pt=page_plan.width_pt,
            page_height_pt=page_plan.height_pt,
            canvas_width=c_w,
            canvas_height=c_h,
            margin_padding_px=margin_padding_px,
        )

        # 1. Anti-stretching verification
        if not transformer.verify_no_stretching():
            raise ValueError(
                f"Page preview aspect ratio distorted: "
                f"physical={transformer.page_aspect_ratio_pt:.4f}, "
                f"rendered={transformer.rendered_page_aspect_ratio:.4f}"
            )

        # 2. Rendered sheet box
        sheet_box_tuple = transformer.get_rendered_page_box()
        rendered_sheet_box = PreviewBox(
            x=sheet_box_tuple.x,
            y=sheet_box_tuple.y,
            width=sheet_box_tuple.width,
            height=sheet_box_tuple.height,
            x_min=sheet_box_tuple.x_min,
            y_min=sheet_box_tuple.y_min,
            x_max=sheet_box_tuple.x_max,
            y_max=sheet_box_tuple.y_max,
        )

        # 3. Status badge & accessibility theme
        status_style = get_status_style(page_plan.crop_readiness)
        status_badge = PreviewStatusBadge(
            status=page_plan.crop_readiness.value,
            badge_text=status_style.badge_text,
            accessibility_label=status_style.accessibility_label,
            color=status_style.stroke_color,
            background_color=status_style.fill_color,
            pattern_type=status_style.pattern_type,
        )

        # 4. Transform Crop Regions
        preview_regions: list[PreviewRegion] = []
        for r in page_plan.crop_regions:
            r_box = transformer.transform_bbox(r.x_min_pt, r.y_min_pt, r.x_max_pt, r.y_max_pt)
            r_preview_box = PreviewBox(
                x=r_box.x,
                y=r_box.y,
                width=r_box.width,
                height=r_box.height,
                x_min=r_box.x_min,
                y_min=r_box.y_min,
                x_max=r_box.x_max,
                y_max=r_box.y_max,
            )

            # Aspect ratios
            ar_pt = r.width_pt / r.height_pt
            ar_px = r.target_width_px / r.target_height_px
            distortion = abs(ar_pt - ar_px) / ar_px * 100.0

            # Determine render DPI
            if r.region_id == "COVER":
                region_dpi = 100
            else:
                region_dpi = 300

            # Construct region display label
            if r.quadrant:
                reg_label = f"{r.region_id} (Quadrant {r.quadrant})"
            else:
                reg_label = f"{r.region_id}"

            preview_regions.append(
                PreviewRegion(
                    region_id=r.region_id,
                    quadrant=r.quadrant,
                    bbox_pt=[r.x_min_pt, r.y_min_pt, r.x_max_pt, r.y_max_pt],
                    bbox_preview=r_preview_box,
                    target_width_px=r.target_width_px,
                    target_height_px=r.target_height_px,
                    dpi=region_dpi,
                    aspect_ratio_pt=ar_pt,
                    aspect_ratio_target_px=ar_px,
                    aspect_ratio_distortion_percent=distortion,
                    visual_style=status_style,
                    label=reg_label,
                    is_blank=(r.blank_page_status.value == "BLANK_DETECTED"),
                )
            )

        # 5. Layout-specific guidelines and elements
        cut_lines: list[PreviewLine] = []
        outer_trim_box: Optional[PreviewBox] = None
        spine_zone: Optional[PreviewSpineZone] = None
        unresolved_discrepancies: list[str] = []
        is_non_nominal: bool = False
        is_auto_crop_allowed = (page_plan.crop_readiness == CropReadinessStatus.CROP_READY)

        # A. 4-Up Imposition Grid
        if page_plan.layout_type == LayoutType.IMPOSITION_4UP:
            x_cut_pt = tick_coords.x_cut if tick_coords else NOMINAL_4UP_HALF_WIDTH_PT
            y_cut_pt = tick_coords.y_cut if tick_coords else NOMINAL_4UP_HALF_HEIGHT_PT

            # Midpoint vertical cut line (full sheet height)
            x_cut_prev = transformer.pt_to_preview_x(x_cut_pt)
            y_top_prev = transformer.pt_to_preview_y(0.0)
            y_bot_prev = transformer.pt_to_preview_y(page_plan.height_pt)
            cut_lines.append(
                PreviewLine(
                    line_type="MIDPOINT_CUT_VERTICAL",
                    label=f"Midpoint Vertical Cut Line (x={x_cut_pt:.2f} pt)",
                    x1=x_cut_prev,
                    y1=y_top_prev,
                    x2=x_cut_prev,
                    y2=y_bot_prev,
                    stroke_color=STYLE_MIDPOINT_CUT.stroke_color,
                    stroke_dasharray=STYLE_MIDPOINT_CUT.stroke_dasharray,
                    stroke_width=STYLE_MIDPOINT_CUT.stroke_width,
                )
            )

            # Midpoint horizontal cut line (full sheet width)
            y_cut_prev = transformer.pt_to_preview_y(y_cut_pt)
            x_left_prev = transformer.pt_to_preview_x(0.0)
            x_right_prev = transformer.pt_to_preview_x(page_plan.width_pt)
            cut_lines.append(
                PreviewLine(
                    line_type="MIDPOINT_CUT_HORIZONTAL",
                    label=f"Midpoint Horizontal Cut Line (y={y_cut_pt:.2f} pt)",
                    x1=x_left_prev,
                    y1=y_cut_prev,
                    x2=x_right_prev,
                    y2=y_cut_prev,
                    stroke_color=STYLE_MIDPOINT_CUT.stroke_color,
                    stroke_dasharray=STYLE_MIDPOINT_CUT.stroke_dasharray,
                    stroke_width=STYLE_MIDPOINT_CUT.stroke_width,
                )
            )

            # Outer trim boundary rectangle (Spec §10.A: 13.85 pt horizontal, 14.50 pt vertical)
            trim_x1 = 13.85
            trim_y1 = 14.50
            trim_x2 = page_plan.width_pt - 13.85
            trim_y2 = page_plan.height_pt - 14.50
            tb = transformer.transform_bbox(trim_x1, trim_y1, trim_x2, trim_y2)
            outer_trim_box = PreviewBox(
                x=tb.x, y=tb.y, width=tb.width, height=tb.height,
                x_min=tb.x_min, y_min=tb.y_min, x_max=tb.x_max, y_max=tb.y_max,
            )

        # B. Cover Spread
        elif page_plan.layout_type == LayoutType.COVER_SPREAD:
            # Auto-crop is ALWAYS prohibited on Cover
            is_auto_crop_allowed = False

            # Spine exclusion zone (Spec §8.A.1, §15.A.6: 15.02 mm / 42.57 pt)
            sp_left = cover_marks.x_spine_left if cover_marks else DEFAULT_COVER_SPINE_INNER_LEFT_PT
            sp_right = cover_marks.x_spine_right if cover_marks else DEFAULT_COVER_SPINE_INNER_RIGHT_PT
            sp_w_pt = sp_right - sp_left
            sp_w_mm = points_to_mm(sp_w_pt)

            spine_prev_box = transformer.transform_bbox(sp_left, 0.0, sp_right, page_plan.height_pt)
            spine_zone = PreviewSpineZone(
                left_boundary_pt=sp_left,
                right_boundary_pt=sp_right,
                width_pt=sp_w_pt,
                width_mm=sp_w_mm,
                box_preview=PreviewBox(
                    x=spine_prev_box.x,
                    y=spine_prev_box.y,
                    width=spine_prev_box.width,
                    height=spine_prev_box.height,
                    x_min=spine_prev_box.x_min,
                    y_min=spine_prev_box.y_min,
                    x_max=spine_prev_box.x_max,
                    y_max=spine_prev_box.y_max,
                ),
                label=f"PROTECTED SPINE ZONE ({sp_w_mm:.2f} mm / {sp_w_pt:.2f} pt)",
                visual_style=STYLE_SPINE_EXCLUSION,
            )

            # Preserve all unresolved cover discrepancies explicitly
            unresolved_discrepancies.append(UNRESOLVED_COVER_WIDTH_DISCREPANCY)
            unresolved_discrepancies.append(UNRESOLVED_ROUNDING_1PX)

        # C. Single Page Layout
        elif page_plan.layout_type == LayoutType.SINGLE_PAGE:
            nominal_w = 425.52
            nominal_h = 609.12
            if (
                round(page_plan.width_pt, 2) != nominal_w
                or round(page_plan.height_pt, 2) != nominal_h
            ):
                is_non_nominal = True
                is_auto_crop_allowed = False
                unresolved_discrepancies.append(UNRESOLVED_SINGLE_PAGE_NORMALIZATION_POLICY)

        # Review flags & warnings
        review_flag_names = [f.value for f in page_plan.manual_review_flags]
        warnings: list[str] = []
        if is_non_nominal:
            warnings.append(
                f"Non-nominal single page dimensions ({page_plan.width_pt:.2f}x{page_plan.height_pt:.2f} pt). "
                f"Held in manual review until normalization policy is decided."
            )
        if page_plan.rotation != 0:
            warnings.append(f"Non-zero page rotation ({page_plan.rotation}°). Auto-rotation is prohibited.")
        if page_plan.layout_type == LayoutType.COVER_SPREAD:
            warnings.append("Cover Spread auto-crop is disabled. Hold for manual review.")

        return PreviewPagePayload(
            pdf_page_index=page_plan.pdf_page_index,
            pdf_page_number=page_plan.pdf_page_number,
            layout_type=page_plan.layout_type,
            classification_status=page_plan.classification_status,
            crop_readiness=page_plan.crop_readiness,
            width_pt=page_plan.width_pt,
            height_pt=page_plan.height_pt,
            orientation=page_plan.orientation.value,
            rotation=page_plan.rotation,
            canvas_width=c_w,
            canvas_height=c_h,
            scale_factor=transformer.scale_factor,
            offset_x=transformer.offset_x,
            offset_y=transformer.offset_y,
            rendered_page_box=rendered_sheet_box,
            regions=preview_regions,
            cut_lines=cut_lines,
            outer_trim_box=outer_trim_box,
            spine_zone=spine_zone,
            status_badge=status_badge,
            is_auto_crop_allowed=is_auto_crop_allowed,
            is_non_nominal=is_non_nominal,
            review_flags=review_flag_names,
            warnings=warnings,
            unresolved_discrepancies=unresolved_discrepancies,
            metadata={
                "margin_padding_px": transformer.margin_padding_px,
                "rendered_page_width": transformer.rendered_page_width,
                "rendered_page_height": transformer.rendered_page_height,
            },
        )

    def generate_document_preview(
        self,
        doc_plan: DocumentCropPlan,
        canvas_width: Optional[float] = None,
        canvas_height: Optional[float] = None,
    ) -> PreviewDocumentPayload:
        """Generate a complete PreviewDocumentPayload across all sheets in a DocumentCropPlan."""
        c_w = canvas_width or self.default_canvas_width
        c_h = canvas_height or self.default_canvas_height

        pages: list[PreviewPagePayload] = []
        for plan in doc_plan.page_plans:
            page_payload = self.generate_page_preview(
                page_plan=plan,
                canvas_width=c_w,
                canvas_height=c_h,
            )
            pages.append(page_payload)

        # Document-level status badge
        doc_status_str = doc_plan.document_status.document_status
        doc_style = get_status_style(doc_status_str)
        doc_badge = PreviewStatusBadge(
            status=doc_status_str,
            badge_text=doc_style.badge_text,
            accessibility_label=doc_style.accessibility_label,
            color=doc_style.stroke_color,
            background_color=doc_style.fill_color,
            pattern_type=doc_style.pattern_type,
        )

        total_regions = sum(len(p.regions) for p in pages)
        has_manual_review = doc_plan.document_status.has_manual_review_required
        has_unknown = doc_plan.document_status.has_unknown_layout

        summary = {
            "source_filename": doc_plan.source_filename,
            "total_pdf_pages": doc_plan.total_pdf_pages,
            "expected_total_book_pages": doc_plan.expected_total_book_pages,
            "total_crop_regions": total_regions,
            "document_status": doc_status_str,
            "all_pages_crop_ready": doc_plan.document_status.all_pages_crop_ready,
            "has_manual_review_required": has_manual_review,
            "has_unknown_layout": has_unknown,
            "page_sequence_signature": doc_plan.page_sequence_signature,
        }

        return PreviewDocumentPayload(
            source_filename=doc_plan.source_filename,
            total_pdf_pages=doc_plan.total_pdf_pages,
            expected_total_book_pages=doc_plan.expected_total_book_pages,
            document_status=doc_status_str,
            status_badge=doc_badge,
            pages=pages,
            page_sequence_signature=doc_plan.page_sequence_signature,
            total_crop_regions=total_regions,
            has_manual_review_required=has_manual_review,
            has_unknown_layout=has_unknown,
            summary=summary,
        )

    def render_svg(self, page_payload: PreviewPagePayload) -> str:
        """Render a single page preview payload into an SVG string."""
        return self._svg_renderer.render_page_svg(page_payload)

    def render_pdf_page(
        self,
        source: Any,
        page_index: int,
        dpi: Optional[int] = None,
    ) -> Image.Image:
        """Render a single PDF page into an in-memory PIL Image.

        Strictly read-only: does not modify or save to the source PDF.
        """
        return self._pdf_renderer.render_page_to_image(source=source, page_index=page_index, dpi=dpi)

    def compose_page_preview(
        self,
        page_plan: PageCropPlan,
        pdf_source: Any,
        dpi: Optional[int] = None,
        save_to_dir: Optional[Union[str, Path]] = None,
        tick_coords: Optional[TickMarkCoordinates] = None,
        cover_marks: Optional[CoverCropMarks] = None,
    ) -> PreviewImageOutput:
        """Render actual PDF page and composite structured crop preview overlay on top.

        Args:
            page_plan: Validated PageCropPlan for the sheet.
            pdf_source: PDF Document, file path, or bytes.
            dpi: Resolution for preview rasterization (default: self.default_dpi, usually 100).
            save_to_dir: Optional directory to save PREVIEW_PAGE_{n}.png artifact.
            tick_coords: Optional tick mark coordinates for 4-Up.
            cover_marks: Optional cover crop marks for Cover Spread.

        Returns:
            PreviewImageOutput containing PNG bytes, base64 data URI, dimensions, and metadata.
        """
        render_dpi = dpi if dpi is not None else self.default_dpi

        # 1. Render base PDF page to in-memory PIL Image
        page_image = self._pdf_renderer.render_page_to_image(
            source=pdf_source,
            page_index=page_plan.pdf_page_index,
            dpi=render_dpi,
        )

        # 2. Generate structured preview payload mapped 1:1 to image pixel canvas
        payload = self.generate_page_preview(
            page_plan=page_plan,
            canvas_width=float(page_image.width),
            canvas_height=float(page_image.height),
            tick_coords=tick_coords,
            cover_marks=cover_marks,
            margin_padding_px=0.0,
        )

        # 3. Composite visual overlays (quadrants, cut lines, spine zone, labels, badges)
        return self._compositor.composite_page_preview(
            page_image=page_image,
            page_payload=payload,
            dpi=render_dpi,
            save_to_dir=save_to_dir,
        )

    def compose_document_preview(
        self,
        doc_plan: DocumentCropPlan,
        pdf_source: Any,
        dpi: Optional[int] = None,
        save_to_dir: Optional[Union[str, Path]] = None,
    ) -> list[PreviewImageOutput]:
        """Render and composite visual previews for all pages in a DocumentCropPlan.

        Args:
            doc_plan: DocumentCropPlan containing all PageCropPlans.
            pdf_source: PDF Document, file path, or bytes.
            dpi: Resolution for preview rasterization.
            save_to_dir: Optional directory to save all preview PNG files.

        Returns:
            List of PreviewImageOutput objects, one per PDF page.
        """
        results: list[PreviewImageOutput] = []
        for plan in doc_plan.page_plans:
            out = self.compose_page_preview(
                page_plan=plan,
                pdf_source=pdf_source,
                dpi=dpi,
                save_to_dir=save_to_dir,
            )
            results.append(out)
        return results

    def render_clean_page_png(
        self,
        page_plan: PageCropPlan,
        pdf_source: Any,
        dpi: Optional[int] = None,
    ) -> bytes:
        """Render clean PDF sheet PNG without any crop overlay annotations."""
        render_dpi = dpi if dpi is not None else self.default_dpi
        return self._pdf_renderer.render_page_to_bytes(
            source=pdf_source,
            page_index=page_plan.pdf_page_index,
            dpi=render_dpi,
            image_format="PNG",
        )

    def render_region_preview_png(
        self,
        page_plan: PageCropPlan,
        pdf_source: Any,
        region_id: str,
        dpi: Optional[int] = None,
        overlay: bool = True,
    ) -> bytes:
        """Render a single cropped book page/cover region as PNG with optional overlay."""
        target_region = next(
            (r for r in page_plan.crop_regions if r.region_id == region_id),
            None,
        )
        if target_region is None:
            raise KeyError(
                f"Region '{region_id}' not found on page {page_plan.pdf_page_number}."
            )

        render_dpi = dpi if dpi is not None else self.default_dpi
        region_img = self._pdf_renderer.render_region_to_image(
            source=pdf_source,
            page_index=page_plan.pdf_page_index,
            clip_rect_pt=(
                target_region.x_min_pt,
                target_region.y_min_pt,
                target_region.x_max_pt,
                target_region.y_max_pt,
            ),
            dpi=render_dpi,
        )
        return self._compositor.render_region_png(
            region_image=region_img,
            region_id=target_region.region_id,
            quadrant=target_region.quadrant,
            crop_readiness=page_plan.crop_readiness,
            is_blank=(target_region.blank_page_status.value == "BLANK_DETECTED"),
            overlay=overlay,
        )

