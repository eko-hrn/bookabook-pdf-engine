"""Preview Compositor (Phase 1.2.2.5).

Composites vector crop planning overlays (quadrants, cut lines, outer trim,
spine exclusion zones, status badges, and accessibility labels) on top of
rendered PDF page raster images using Pillow.

Guarantees:
1. Pixel-perfect alignment: transforms physical PDF coordinates (points) directly
   into rendered raster pixel coordinates at matching DPI.
2. Aspect ratio preservation: zero image stretching or non-uniform scaling.
3. Alpha compositing: clear visual readability without obscuring underlying PDF content.
4. Non-reliance on color alone: text badges and pattern cues for every status.
5. In-memory PNG outputs & data URIs: never produces production JPGs.
6. Temporary preview artifact support: optional saving as PREVIEW_PAGE_{n}.png.
"""

from __future__ import annotations

import base64
import io
import math
import os
from pathlib import Path
from typing import Optional, Union

from PIL import Image, ImageDraw, ImageFont

from app.crop.models.enums import CropReadinessStatus, LayoutType
from app.crop.preview.models import PreviewImageOutput, PreviewPagePayload
from app.crop.preview.transformer import CoordinateTransformer


class PreviewCompositor:
    """Composites structured preview overlays onto rendered PDF page raster images."""

    # Color Palette (RGBA)
    COLOR_CROP_READY_FILL = (16, 185, 129, 45)         # Emerald green 18%
    COLOR_CROP_READY_STROKE = (16, 185, 129, 240)      # Emerald green solid
    COLOR_REVIEW_FILL = (245, 158, 11, 45)             # Amber 18%
    COLOR_REVIEW_STROKE = (217, 119, 6, 240)           # Amber solid
    COLOR_REJECTED_FILL = (239, 68, 68, 50)            # Red 20%
    COLOR_REJECTED_STROKE = (220, 38, 38, 240)         # Red solid
    COLOR_BLANK_FILL = (148, 163, 184, 30)             # Slate 12%
    COLOR_BLANK_STROKE = (100, 116, 139, 180)          # Slate muted

    COLOR_CUT_LINE = (37, 99, 235, 230)                # Royal blue
    COLOR_OUTER_TRIM = (124, 58, 237, 210)             # Violet / Purple
    COLOR_SPINE_ZONE_FILL = (245, 158, 11, 40)         # Amber
    COLOR_SPINE_HATCH = (217, 119, 6, 120)             # Amber hatch
    COLOR_SPINE_STROKE = (217, 119, 6, 230)            # Amber boundary

    COLOR_PILL_BG = (15, 23, 42, 225)                  # Slate-900 high contrast
    COLOR_TEXT_WHITE = (255, 255, 255, 255)            # Pure white
    COLOR_BANNER_AMBER_BG = (180, 83, 9, 230)          # Warning banner background

    def __init__(self, font_size: int = 14, title_font_size: int = 16) -> None:
        """Initialize compositor with typography settings."""
        self.font_size = font_size
        self.title_font_size = title_font_size
        try:
            self.font_body = ImageFont.load_default(size=font_size)
            self.font_title = ImageFont.load_default(size=title_font_size)
            self.font_small = ImageFont.load_default(size=max(10, font_size - 3))
        except TypeError:
            # Fallback for older Pillow versions where load_default has no size param
            default_font = ImageFont.load_default()
            self.font_body = default_font
            self.font_title = default_font
            self.font_small = default_font

    def composite_page_preview(
        self,
        page_image: Image.Image,
        page_payload: PreviewPagePayload,
        dpi: int = 100,
        save_to_dir: Optional[Union[str, Path]] = None,
    ) -> PreviewImageOutput:
        """Composite structured preview overlays on top of a rendered PDF page image.

        Args:
            page_image: Rendered base PDF page image (PIL Image in RGB mode).
            page_payload: Structured PreviewPagePayload containing regions, guides, and status.
            dpi: Resolution used to render the preview (e.g. 100 DPI).
            save_to_dir: Optional directory path to save temporary PREVIEW_PAGE_{n}.png.

        Returns:
            PreviewImageOutput containing PNG bytes, data URI, dimensions, and metadata.
        """
        img_w, img_h = page_image.size
        if img_w <= 0 or img_h <= 0:
            raise ValueError(f"Invalid image dimensions: {img_w}x{img_h}")

        # Direct 1:1 point-to-pixel coordinate transformer
        transformer = CoordinateTransformer(
            page_width_pt=page_payload.width_pt,
            page_height_pt=page_payload.height_pt,
            canvas_width=img_w,
            canvas_height=img_h,
            margin_padding_px=0.0,
        )

        # Create transparent overlay image of identical dimensions
        overlay = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # 1. Draw Spine Exclusion Zone (Cover Spread)
        if page_payload.spine_zone is not None:
            sz = page_payload.spine_zone
            sp_box = transformer.transform_bbox(
                sz.left_boundary_pt, 0.0, sz.right_boundary_pt, page_payload.height_pt
            )
            self._draw_spine_exclusion_zone(draw, sp_box, sz.label)

        # 2. Draw Outer Trim Box (4-Up Imposition)
        if page_payload.outer_trim_box is not None:
            # Physical outer trim is 13.85 pt horizontal, 14.50 pt vertical
            trim_x1 = 13.85
            trim_y1 = 14.50
            trim_x2 = page_payload.width_pt - 13.85
            trim_y2 = page_payload.height_pt - 14.50
            ot_box = transformer.transform_bbox(trim_x1, trim_y1, trim_x2, trim_y2)
            self._draw_dashed_rect(
                draw,
                (ot_box.x_min, ot_box.y_min, ot_box.x_max, ot_box.y_max),
                fill=self.COLOR_OUTER_TRIM,
                width=2,
                dash_len=8.0,
                space_len=4.0,
            )
            self._draw_text_pill(
                draw,
                (ot_box.x_min + 12, ot_box.y_min + 10),
                "OUTER SHEET TRIM (13.85 pt / 14.50 pt margins)",
                border_color=self.COLOR_OUTER_TRIM,
                font=self.font_small,
            )

        # 3. Draw Midpoint Cut Lines (4-Up Imposition)
        for cut_line in page_payload.cut_lines:
            if cut_line.line_type == "MIDPOINT_CUT_VERTICAL":
                # Compute exact center line
                x_mid = transformer.pt_to_preview_x(page_payload.width_pt / 2.0)
                self._draw_dashed_line(
                    draw,
                    (x_mid, 0.0),
                    (x_mid, float(img_h)),
                    fill=self.COLOR_CUT_LINE,
                    width=2,
                    dash_len=6.0,
                    space_len=4.0,
                )
                self._draw_text_pill(
                    draw,
                    (x_mid + 8, float(img_h) - 40),
                    f"VERTICAL CUT: x={page_payload.width_pt / 2.0:.2f} pt",
                    border_color=self.COLOR_CUT_LINE,
                    font=self.font_small,
                )
            elif cut_line.line_type == "MIDPOINT_CUT_HORIZONTAL":
                y_mid = transformer.pt_to_preview_y(page_payload.height_pt / 2.0)
                self._draw_dashed_line(
                    draw,
                    (0.0, y_mid),
                    (float(img_w), y_mid),
                    fill=self.COLOR_CUT_LINE,
                    width=2,
                    dash_len=6.0,
                    space_len=4.0,
                )
                self._draw_text_pill(
                    draw,
                    (20.0, y_mid - 24),
                    f"HORIZONTAL CUT: y={page_payload.height_pt / 2.0:.2f} pt",
                    border_color=self.COLOR_CUT_LINE,
                    font=self.font_small,
                )

        # 4. Draw Crop Regions (Q1-Q4, COVER, BACKCOVER, Single Page)
        for region in page_payload.regions:
            x_min_pt, y_min_pt, x_max_pt, y_max_pt = region.bbox_pt
            r_box = transformer.transform_bbox(x_min_pt, y_min_pt, x_max_pt, y_max_pt)
            self._draw_crop_region(
                draw=draw,
                box=r_box,
                region=region,
                page_payload=page_payload,
            )

        # 5. Draw Prominent Sheet Status Badge (Top-Left or Top-Right)
        self._draw_status_badge(draw, page_payload)

        # 6. Draw Bottom Warning Banner if MANUAL_REVIEW_REQUIRED
        if (
            page_payload.crop_readiness != CropReadinessStatus.CROP_READY
            or not page_payload.is_auto_crop_allowed
            or page_payload.warnings
        ):
            self._draw_warning_banner(draw, page_payload, img_w, img_h)

        # Alpha composite overlay over base image
        base_rgba = page_image.convert("RGBA")
        composite_rgba = Image.alpha_composite(base_rgba, overlay)
        final_rgb = composite_rgba.convert("RGB")

        # Encode to PNG in memory
        png_buffer = io.BytesIO()
        final_rgb.save(png_buffer, format="PNG")
        png_bytes = png_buffer.getvalue()

        # Generate Base64 Data URI
        b64_str = base64.b64encode(png_bytes).decode("ascii")
        data_uri = f"data:image/png;base64,{b64_str}"

        # Handle optional save to disk
        temp_file_path: Optional[str] = None
        if save_to_dir is not None:
            save_path = Path(save_to_dir)
            save_path.mkdir(parents=True, exist_ok=True)
            filename = f"PREVIEW_PAGE_{page_payload.pdf_page_number}.png"
            file_dest = save_path / filename
            final_rgb.save(str(file_dest), format="PNG")
            temp_file_path = str(file_dest)

        return PreviewImageOutput(
            pdf_page_index=page_payload.pdf_page_index,
            pdf_page_number=page_payload.pdf_page_number,
            layout_type=page_payload.layout_type,
            crop_readiness=page_payload.crop_readiness,
            image_bytes=png_bytes,
            image_format="PNG",
            width_px=img_w,
            height_px=img_h,
            dpi=dpi,
            data_uri=data_uri,
            temp_file_path=temp_file_path,
            is_auto_crop_allowed=page_payload.is_auto_crop_allowed,
            is_non_nominal=page_payload.is_non_nominal,
            review_flags=page_payload.review_flags,
            warnings=page_payload.warnings,
            unresolved_discrepancies=page_payload.unresolved_discrepancies,
            metadata={
                "margin_padding_px": 0.0,
                "scale_factor": transformer.scale_factor,
                "aspect_ratio_preservation": "EXACT",
            },
        )

    def render_region_png(
        self,
        region_image: Image.Image,
        region_id: str,
        quadrant: Optional[int],
        crop_readiness: CropReadinessStatus,
        is_blank: bool = False,
        overlay: bool = True,
    ) -> bytes:
        """Encode a single clipped crop region image to PNG with optional lightweight crop border."""
        img_rgb = region_image.convert("RGB")
        if not overlay:
            buf = io.BytesIO()
            img_rgb.save(buf, format="PNG")
            return buf.getvalue()

        img_w, img_h = img_rgb.size
        overlay_layer = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay_layer)

        if is_blank:
            stroke_color = self.COLOR_BLANK_STROKE
            is_solid = False
        elif crop_readiness == CropReadinessStatus.CROP_READY:
            stroke_color = self.COLOR_CROP_READY_STROKE
            is_solid = True
        else:
            stroke_color = self.COLOR_REVIEW_STROKE
            is_solid = False

        inset = 2.0
        bbox = (inset, inset, max(inset + 1.0, img_w - 1 - inset), max(inset + 1.0, img_h - 1 - inset))
        if is_solid:
            draw.rectangle(bbox, outline=stroke_color, width=3)
        else:
            self._draw_dashed_rect(
                draw,
                bbox,
                fill=stroke_color,
                width=3,
                dash_len=8.0,
                space_len=5.0,
            )

        pill_text = f"{region_id} (Q{quadrant})" if quadrant else region_id
        if is_blank:
            pill_text = f"{pill_text} [BLANK]"
        elif crop_readiness != CropReadinessStatus.CROP_READY and img_w >= 220:
            pill_text = f"{pill_text} [REVIEW]"

        self._draw_text_pill(
            draw=draw,
            pos=(10.0, 10.0),
            text=pill_text,
            border_color=stroke_color,
            font=self.font_small,
        )

        composited = Image.alpha_composite(img_rgb.convert("RGBA"), overlay_layer).convert("RGB")
        buf = io.BytesIO()
        composited.save(buf, format="PNG")
        return buf.getvalue()

    def _draw_crop_region(
        self,
        draw: ImageDraw.ImageDraw,
        box: Any,
        region: Any,
        page_payload: PreviewPagePayload,
    ) -> None:
        """Render a single crop region boundary, fill, and label."""
        is_ready = (page_payload.crop_readiness == CropReadinessStatus.CROP_READY)
        is_blank = region.is_blank

        # Determine styles based on readiness & blank state
        if is_blank:
            fill_color = self.COLOR_BLANK_FILL
            stroke_color = self.COLOR_BLANK_STROKE
            is_solid = False
        elif is_ready:
            fill_color = self.COLOR_CROP_READY_FILL
            stroke_color = self.COLOR_CROP_READY_STROKE
            is_solid = True
        else:
            fill_color = self.COLOR_REVIEW_FILL
            stroke_color = self.COLOR_REVIEW_STROKE
            is_solid = False

        # Fill rectangle
        draw.rectangle(
            (box.x_min, box.y_min, box.x_max, box.y_max),
            fill=fill_color,
        )

        # Border stroke
        if is_solid:
            draw.rectangle(
                (box.x_min, box.y_min, box.x_max, box.y_max),
                outline=stroke_color,
                width=2,
            )
        else:
            self._draw_dashed_rect(
                draw,
                (box.x_min, box.y_min, box.x_max, box.y_max),
                fill=stroke_color,
                width=2,
                dash_len=7.0,
                space_len=4.0,
            )

        # Region Information Pill
        pill_x = box.x_min + 14
        pill_y = box.y_min + 14

        line1 = f"{region.label}"
        line2 = f"Target: {region.target_width_px}×{region.target_height_px} px @ {region.dpi} DPI"
        if not is_ready:
            line3 = "[MANUAL REVIEW REQUIRED]"
            pill_lines = [line1, line2, line3]
        else:
            pill_lines = [line1, line2]

        self._draw_multiline_pill(
            draw=draw,
            pos=(pill_x, pill_y),
            lines=pill_lines,
            border_color=stroke_color,
            font=self.font_body,
        )

    def _draw_spine_exclusion_zone(
        self,
        draw: ImageDraw.ImageDraw,
        box: Any,
        label: str,
    ) -> None:
        """Render the protected spine exclusion zone on Cover Spread."""
        # 1. Translucent amber fill
        draw.rectangle(
            (box.x_min, box.y_min, box.x_max, box.y_max),
            fill=self.COLOR_SPINE_ZONE_FILL,
        )

        # 2. Diagonal amber hatching
        self._draw_hatch_rect(
            draw=draw,
            bbox=(box.x_min, box.y_min, box.x_max, box.y_max),
            fill=self.COLOR_SPINE_HATCH,
            step=14,
            width=1,
        )

        # 3. Solid vertical boundary lines
        draw.line([(box.x_min, box.y_min), (box.x_min, box.y_max)], fill=self.COLOR_SPINE_STROKE, width=2)
        draw.line([(box.x_max, box.y_min), (box.x_max, box.y_max)], fill=self.COLOR_SPINE_STROKE, width=2)

        # 4. Center Spine Pill Badge
        center_x = (box.x_min + box.x_max) / 2.0
        center_y = (box.y_min + box.y_max) / 2.0
        self._draw_text_pill(
            draw=draw,
            pos=(center_x - 80, center_y - 12),
            text="PROTECTED SPINE ZONE",
            border_color=self.COLOR_SPINE_STROKE,
            font=self.font_small,
        )

    def _draw_status_badge(
        self,
        draw: ImageDraw.ImageDraw,
        page_payload: PreviewPagePayload,
    ) -> None:
        """Render a prominent accessibility-compliant status badge in top corner."""
        badge = page_payload.status_badge
        status_text = badge.badge_text
        layout_name = page_payload.layout_type.value if page_payload.layout_type else "UNKNOWN"

        if page_payload.crop_readiness == CropReadinessStatus.CROP_READY:
            border_color = self.COLOR_CROP_READY_STROKE
            accent_symbol = "✓ [AUTO-CROP READY]"
        elif page_payload.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED:
            border_color = self.COLOR_REVIEW_STROKE
            accent_symbol = "⚠ [MANUAL REVIEW REQUIRED]"
        else:
            border_color = self.COLOR_REJECTED_STROKE
            accent_symbol = "✗ [REJECTED]"

        lines = [
            f"PAGE {page_payload.pdf_page_number} | {layout_name}",
            f"{accent_symbol} - {status_text}",
        ]

        self._draw_multiline_pill(
            draw=draw,
            pos=(20, 20),
            lines=lines,
            border_color=border_color,
            font=self.font_title,
        )

    def _draw_warning_banner(
        self,
        draw: ImageDraw.ImageDraw,
        page_payload: PreviewPagePayload,
        img_w: int,
        img_h: int,
    ) -> None:
        """Render a high-contrast warning banner at the bottom edge."""
        banner_h = 36
        banner_y = img_h - banner_h

        draw.rectangle(
            (0, banner_y, img_w, img_h),
            fill=self.COLOR_BANNER_AMBER_BG,
        )

        warning_texts = []
        if not page_payload.is_auto_crop_allowed:
            warning_texts.append("AUTO-CROP DISABLED")
        if page_payload.warnings:
            warning_texts.append("; ".join(page_payload.warnings))
        elif page_payload.review_flags:
            warning_texts.append("; ".join(page_payload.review_flags))

        banner_msg = " | ".join(warning_texts) if warning_texts else "HELD FOR OPERATOR MANUAL REVIEW"
        msg = f"⚠ MANUAL REVIEW: {banner_msg}"

        # Truncate if exceeds image width
        draw.text(
            (16, banner_y + 10),
            msg,
            fill=self.COLOR_TEXT_WHITE,
            font=self.font_body,
        )

    def _draw_text_pill(
        self,
        draw: ImageDraw.ImageDraw,
        pos: tuple[float, float],
        text: str,
        border_color: tuple[int, int, int, int],
        font: ImageFont.ImageFont,
    ) -> None:
        """Render a single-line high contrast text pill."""
        x, y = pos
        tb = draw.textbbox((x, y), text, font=font)
        pad_x, pad_y = 6, 4
        rect = (tb[0] - pad_x, tb[1] - pad_y, tb[2] + pad_x, tb[3] + pad_y)

        draw.rounded_rectangle(rect, radius=4, fill=self.COLOR_PILL_BG, outline=border_color, width=1)
        draw.text((x, y), text, fill=self.COLOR_TEXT_WHITE, font=font)

    def _draw_multiline_pill(
        self,
        draw: ImageDraw.ImageDraw,
        pos: tuple[float, float],
        lines: list[str],
        border_color: tuple[int, int, int, int],
        font: ImageFont.ImageFont,
    ) -> None:
        """Render a multi-line high contrast text pill."""
        x, y = pos
        pad_x, pad_y = 8, 6
        line_spacing = 4

        # Calculate bounding boxes
        total_w = 0.0
        line_heights = []
        for line in lines:
            tb = draw.textbbox((0, 0), line, font=font)
            lw = tb[2] - tb[0]
            lh = tb[3] - tb[1]
            if lw > total_w:
                total_w = lw
            line_heights.append(lh)

        total_h = sum(line_heights) + line_spacing * (len(lines) - 1)
        rect = (x - pad_x, y - pad_y, x + total_w + pad_x, y + total_h + pad_y)

        draw.rounded_rectangle(rect, radius=5, fill=self.COLOR_PILL_BG, outline=border_color, width=1)

        curr_y = y
        for i, line in enumerate(lines):
            draw.text((x, curr_y), line, fill=self.COLOR_TEXT_WHITE, font=font)
            curr_y += line_heights[i] + line_spacing

    @staticmethod
    def _draw_dashed_line(
        draw: ImageDraw.ImageDraw,
        p1: tuple[float, float],
        p2: tuple[float, float],
        fill: tuple[int, int, int, int],
        width: int = 2,
        dash_len: float = 8.0,
        space_len: float = 4.0,
    ) -> None:
        """Draw a dashed line segment between two points."""
        x1, y1 = p1
        x2, y2 = p2
        dx = x2 - x1
        dy = y2 - y1
        dist = math.hypot(dx, dy)
        if dist == 0:
            return
        ux = dx / dist
        uy = dy / dist
        curr = 0.0
        while curr < dist:
            start_x = x1 + ux * curr
            start_y = y1 + uy * curr
            end_dist = min(curr + dash_len, dist)
            end_x = x1 + ux * end_dist
            end_y = y1 + uy * end_dist
            draw.line([(start_x, start_y), (end_x, end_y)], fill=fill, width=width)
            curr += dash_len + space_len

    def _draw_dashed_rect(
        self,
        draw: ImageDraw.ImageDraw,
        bbox: tuple[float, float, float, float],
        fill: tuple[int, int, int, int],
        width: int = 2,
        dash_len: float = 8.0,
        space_len: float = 4.0,
    ) -> None:
        """Draw a rectangle with dashed borders."""
        x_min, y_min, x_max, y_max = bbox
        self._draw_dashed_line(draw, (x_min, y_min), (x_max, y_min), fill, width, dash_len, space_len)
        self._draw_dashed_line(draw, (x_max, y_min), (x_max, y_max), fill, width, dash_len, space_len)
        self._draw_dashed_line(draw, (x_max, y_max), (x_min, y_max), fill, width, dash_len, space_len)
        self._draw_dashed_line(draw, (x_min, y_max), (x_min, y_min), fill, width, dash_len, space_len)

    @staticmethod
    def _draw_hatch_rect(
        draw: ImageDraw.ImageDraw,
        bbox: tuple[float, float, float, float],
        fill: tuple[int, int, int, int],
        step: int = 14,
        width: int = 1,
    ) -> None:
        """Draw 45-degree diagonal hatching clipped inside a bounding box."""
        x_min, y_min, x_max, y_max = bbox
        c_start = int(x_min - y_max)
        c_end = int(x_max - y_min)

        for c in range(c_start, c_end, step):
            pts: list[tuple[float, float]] = []
            # Check left edge (x = x_min)
            y = x_min - c
            if y_min <= y <= y_max:
                pts.append((x_min, float(y)))
            # Check right edge (x = x_max)
            y = x_max - c
            if y_min <= y <= y_max:
                pts.append((x_max, float(y)))
            # Check top edge (y = y_min)
            x = y_min + c
            if x_min <= x <= x_max and (float(x), y_min) not in pts:
                pts.append((float(x), y_min))
            # Check bottom edge (y = y_max)
            x = y_max + c
            if x_min <= x <= x_max and (float(x), y_max) not in pts:
                pts.append((float(x), y_max))

            if len(pts) >= 2:
                draw.line([pts[0], pts[1]], fill=fill, width=width)

