"""SVG Preview Overlay Generator (Phase 1.2.2.4).

Renders a PreviewPagePayload or PreviewDocumentPayload into standard,
well-formed, accessible SVG markup.

Features:
- Pure vector rendering with zero PDF/image rasterization dependencies.
- Distinct visual patterns: solid lines for CROP_READY, dashed for MANUAL_REVIEW_REQUIRED,
  dotted for UNKNOWN_LAYOUT, dash-dot for REJECTED.
- Accessible text badges and guidelines (never relying on color alone).
- Clean layering:
  1. PDF Page Background (white canvas with drop shadow/border).
  2. Outer Trim Boundaries (if applicable).
  3. Midpoint Cut Dividing Lines.
  4. Spine Exclusion Zone (hatched pattern).
  5. Crop Region Bounding Boxes.
  6. Region Labels (PAGE-01, COVER, etc.) & Dimensions.
  7. Status Badges & Warning Banners.
"""

from __future__ import annotations

import html
from app.crop.preview.models import PreviewBox, PreviewLine, PreviewPagePayload, PreviewRegion, PreviewSpineZone


class SVGRenderer:
    """Generates accessible, standards-compliant SVG markup from preview payloads."""

    def render_page_svg(
        self,
        payload: PreviewPagePayload,
        include_xml_declaration: bool = False,
    ) -> str:
        """Render a single PreviewPagePayload into an SVG string."""
        w = payload.canvas_width
        h = payload.canvas_height

        parts: list[str] = []
        if include_xml_declaration:
            parts.append('<?xml version="1.0" encoding="UTF-8"?>')

        # SVG root with accessibility title and desc
        parts.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-labelledby="title-p{payload.pdf_page_index} desc-p{payload.pdf_page_index}">'
        )
        parts.append(
            f'  <title id="title-p{payload.pdf_page_index}">'
            f'Preview Page {payload.pdf_page_number} ({payload.crop_readiness.value})</title>'
        )
        parts.append(
            f'  <desc id="desc-p{payload.pdf_page_index}">'
            f'{html.escape(payload.status_badge.accessibility_label)}</desc>'
        )

        # SVG Defs (patterns for accessible fills)
        parts.append('  <defs>')
        parts.append('    <!-- Hatched pattern for Spine Exclusion Zone -->')
        parts.append('    <pattern id="spine-hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">')
        parts.append('      <line x1="0" y1="0" x2="0" y2="8" stroke="#DC2626" stroke-width="2" stroke-opacity="0.6"/>')
        parts.append('    </pattern>')
        parts.append('    <!-- Dotted pattern for Unknown Layout -->')
        parts.append('    <pattern id="unknown-dots" width="10" height="10" patternUnits="userSpaceOnUse">')
        parts.append('      <circle cx="2" cy="2" r="1.5" fill="#6B7280" fill-opacity="0.4"/>')
        parts.append('    </pattern>')
        parts.append('    <!-- Drop shadow filter -->')
        parts.append('    <filter id="page-shadow" x="-5%" y="-5%" width="110%" height="110%">')
        parts.append('      <feDropShadow dx="2" dy="3" stdDeviation="4" flood-opacity="0.15"/>')
        parts.append('    </filter>')
        parts.append('  </defs>')

        # Layer 1: Canvas Background
        parts.append('  <!-- Canvas Background -->')
        parts.append(f'  <rect width="{w}" height="{h}" fill="#F8FAFC" />')

        # Layer 2: Rendered PDF Page Sheet
        sheet = payload.rendered_page_box
        parts.append('  <!-- PDF Sheet Representation -->')
        parts.append(
            f'  <rect x="{sheet.x:.2f}" y="{sheet.y:.2f}" '
            f'width="{sheet.width:.2f}" height="{sheet.height:.2f}" '
            f'fill="#FFFFFF" stroke="#94A3B8" stroke-width="1.5" filter="url(#page-shadow)" />'
        )

        # Layer 3: Outer Trim Boundary Box (if 4-Up)
        if payload.outer_trim_box:
            tb = payload.outer_trim_box
            parts.append('  <!-- Outer Trim Boundary (Margin) -->')
            parts.append(
                f'  <rect x="{tb.x:.2f}" y="{tb.y:.2f}" '
                f'width="{tb.width:.2f}" height="{tb.height:.2f}" '
                f'fill="rgba(139, 92, 246, 0.04)" stroke="#8B5CF6" '
                f'stroke-width="1.2" stroke-dasharray="3,3" />'
            )
            parts.append(
                f'  <text x="{tb.x + 6:.2f}" y="{tb.y + 14:.2f}" '
                f'font-family="monospace, sans-serif" font-size="10" fill="#7C3AED" font-weight="bold">'
                f'[TRIM MARGIN] 13.85 pt x 14.50 pt</text>'
            )

        # Layer 4: Cut / Dividing Lines (Midpoint lines for 4-Up)
        for line in payload.cut_lines:
            parts.append(
                f'  <!-- {html.escape(line.label)} -->'
            )
            parts.append(
                f'  <line x1="{line.x1:.2f}" y1="{line.y1:.2f}" '
                f'x2="{line.x2:.2f}" y2="{line.y2:.2f}" '
                f'stroke="{line.stroke_color}" stroke-width="{line.stroke_width}" '
                f'stroke-dasharray="{line.stroke_dasharray}" />'
            )

        # Layer 5: Spine Exclusion Zone (Cover Spread)
        if payload.spine_zone:
            sz = payload.spine_zone
            sb = sz.box_preview
            parts.append('  <!-- Protected Spine Exclusion Zone -->')
            parts.append(
                f'  <rect x="{sb.x:.2f}" y="{sb.y:.2f}" '
                f'width="{sb.width:.2f}" height="{sb.height:.2f}" '
                f'fill="url(#spine-hatch)" stroke="#DC2626" stroke-width="2.0" stroke-dasharray="4,2" />'
            )
            # Vertical text label for spine
            center_x = sb.x + (sb.width / 2.0)
            center_y = sb.y + (sb.height / 2.0)
            parts.append(
                f'  <text x="{center_x:.2f}" y="{center_y:.2f}" '
                f'font-family="sans-serif" font-size="10" font-weight="bold" fill="#B91C1C" '
                f'text-anchor="middle" transform="rotate(-90 {center_x:.2f} {center_y:.2f})">'
                f'{html.escape(sz.label)}</text>'
            )

        # Layer 6: Crop Regions
        for r in payload.regions:
            b = r.bbox_preview
            style = r.visual_style
            parts.append(f'  <!-- Crop Region: {html.escape(r.region_id)} -->')
            # Region rectangle
            parts.append(
                f'  <rect x="{b.x:.2f}" y="{b.y:.2f}" '
                f'width="{b.width:.2f}" height="{b.height:.2f}" '
                f'fill="{style.fill_color}" stroke="{style.stroke_color}" '
                f'stroke-width="{style.stroke_width}" stroke-dasharray="{style.stroke_dasharray}" />'
            )

            # Region label banner (Top-left inside region)
            lbl_bg_w = min(b.width - 8, 160.0)
            parts.append(
                f'  <rect x="{b.x + 4:.2f}" y="{b.y + 4:.2f}" width="{lbl_bg_w:.2f}" height="22" '
                f'rx="3" fill="#1E293B" fill-opacity="0.85" />'
            )
            parts.append(
                f'  <text x="{b.x + 8:.2f}" y="{b.y + 19:.2f}" '
                f'font-family="monospace, sans-serif" font-size="11" font-weight="bold" fill="#FFFFFF">'
                f'{html.escape(r.region_id)}'
                f'{" (Q" + str(r.quadrant) + ")" if r.quadrant else ""}</text>'
            )

            # Dimension info text (Bottom-left inside region)
            dim_text = f"{r.target_width_px}x{r.target_height_px} px @ {r.dpi} DPI"
            dim_bg_w = min(b.width - 8, 175.0)
            parts.append(
                f'  <rect x="{b.x + 4:.2f}" y="{b.y + b.height - 22:.2f}" width="{dim_bg_w:.2f}" height="18" '
                f'rx="3" fill="#0F172A" fill-opacity="0.75" />'
            )
            parts.append(
                f'  <text x="{b.x + 8:.2f}" y="{b.y + b.height - 9:.2f}" '
                f'font-family="monospace, sans-serif" font-size="9" fill="#94A3B8">'
                f'{dim_text}</text>'
            )

        # Layer 7: Page Header Badge & Warnings
        badge = payload.status_badge
        parts.append('  <!-- Page Status Badge -->')
        parts.append(
            f'  <rect x="20" y="15" width="260" height="28" rx="4" '
            f'fill="{badge.background_color}" stroke="{badge.color}" stroke-width="1.5" />'
        )
        parts.append(
            f'  <text x="30" y="34" font-family="sans-serif" font-size="12" font-weight="bold" fill="{badge.color}">'
            f'{html.escape(badge.badge_text)}</text>'
        )

        # Page index / dimension banner
        parts.append(
            f'  <text x="{w - 20:.2f}" y="32" text-anchor="end" '
            f'font-family="monospace, sans-serif" font-size="11" fill="#475569">'
            f'Sheet {payload.pdf_page_number} | {payload.width_pt:.1f} x {payload.height_pt:.1f} pt '
            f'({payload.orientation})</text>'
        )

        # Warning banner if manual review required or warnings exist
        y_warn = h - 30
        if payload.warnings or payload.review_flags or payload.unresolved_discrepancies:
            warn_msg = ""
            if payload.unresolved_discrepancies:
                warn_msg = f"[DISCREPANCY] {payload.unresolved_discrepancies[0][:80]}"
            elif payload.review_flags:
                warn_msg = f"[HOLD REASON] {', '.join(payload.review_flags)}"
            elif payload.warnings:
                warn_msg = f"[WARNING] {payload.warnings[0][:80]}"

            if warn_msg:
                parts.append('  <!-- Warning Banner -->')
                parts.append(
                    f'  <rect x="20" y="{y_warn - 15:.2f}" width="{w - 40:.2f}" height="26" rx="4" '
                    f'fill="#FEF3C7" stroke="#D97706" stroke-width="1.0" />'
                )
                parts.append(
                    f'  <text x="30" y="{y_warn + 2:.2f}" font-family="monospace, sans-serif" '
                    f'font-size="10" font-weight="bold" fill="#B45309">'
                    f'{html.escape(warn_msg)}</text>'
                )

        parts.append('</svg>')
        return "\n".join(parts)

