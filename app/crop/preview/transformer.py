"""Coordinate Transformation and Aspect Ratio Preservation (Phase 1.2.2.4).

Converts PDF points (pt) into preview canvas coordinates while strictly
preserving page aspect ratio (no stretching allowed).

PyMuPDF Coordinate Convention:
- Origin (0, 0) is at top-left.
- X axis increases to the right.
- Y axis increases downward.
- Units are points (1 pt = 1/72 inch).

Transformation Guarantees:
- Uniform scaling: s = min(canvas_width / page_width_pt, canvas_height / page_height_pt)
- Centered viewport placement with equal horizontal or vertical margins.
- Aspect ratio distortion is exactly 0.00%.
- Exact round-trip invertibility (preview_to_pt(pt_to_preview(p)) == p).
"""

from __future__ import annotations

from typing import NamedTuple


class PreviewPoint(NamedTuple):
    """A 2D point in preview canvas space."""

    x: float
    y: float


class PreviewBoundingBox(NamedTuple):
    """A 2D bounding box in preview canvas space."""

    x: float
    y: float
    width: float
    height: float
    x_min: float
    y_min: float
    x_max: float
    y_max: float


class CoordinateTransformer:
    """Transforms coordinates from PDF point space to preview viewport space."""

    def __init__(
        self,
        page_width_pt: float,
        page_height_pt: float,
        canvas_width: float = 800.0,
        canvas_height: float = 600.0,
        margin_padding_px: float = 20.0,
    ) -> None:
        """Initialize transformer with page dimensions and preview canvas boundaries.

        Args:
            page_width_pt: Physical page width in PDF points.
            page_height_pt: Physical page height in PDF points.
            canvas_width: Width of preview canvas in pixels/units.
            canvas_height: Height of preview canvas in pixels/units.
            margin_padding_px: Padding around page within the canvas.
        """
        if page_width_pt <= 0 or page_height_pt <= 0:
            raise ValueError(f"Page dimensions must be positive. Got: {page_width_pt}x{page_height_pt} pt")
        if canvas_width <= 0 or canvas_height <= 0:
            raise ValueError(f"Canvas dimensions must be positive. Got: {canvas_width}x{canvas_height}")

        self.page_width_pt = page_width_pt
        self.page_height_pt = page_height_pt
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.margin_padding_px = margin_padding_px

        # Usable canvas area after padding
        usable_w = max(10.0, canvas_width - 2.0 * margin_padding_px)
        usable_h = max(10.0, canvas_height - 2.0 * margin_padding_px)

        # Uniform scale factor: never stretch or distort
        self.scale_factor: float = min(usable_w / page_width_pt, usable_h / page_height_pt)

        # Transformed page dimensions
        self.rendered_page_width: float = self.page_width_pt * self.scale_factor
        self.rendered_page_height: float = self.page_height_pt * self.scale_factor

        # Centering offsets
        self.offset_x: float = (canvas_width - self.rendered_page_width) / 2.0
        self.offset_y: float = (canvas_height - self.rendered_page_height) / 2.0

    @property
    def page_aspect_ratio_pt(self) -> float:
        """Original PDF page aspect ratio (width / height)."""
        return self.page_width_pt / self.page_height_pt

    @property
    def rendered_page_aspect_ratio(self) -> float:
        """Transformed preview page aspect ratio (rendered width / rendered height)."""
        return self.rendered_page_width / self.rendered_page_height

    def verify_no_stretching(self, tolerance: float = 1e-6) -> bool:
        """Assert that page aspect ratio in preview matches physical page with zero distortion."""
        diff = abs(self.page_aspect_ratio_pt - self.rendered_page_aspect_ratio)
        distortion_percent = (diff / self.page_aspect_ratio_pt) * 100.0
        return distortion_percent <= tolerance

    def pt_to_preview_x(self, x_pt: float) -> float:
        """Convert an X coordinate from PDF points to preview canvas space."""
        return self.offset_x + (x_pt * self.scale_factor)

    def pt_to_preview_y(self, y_pt: float) -> float:
        """Convert a Y coordinate from PDF points to preview canvas space."""
        return self.offset_y + (y_pt * self.scale_factor)

    def pt_to_preview_dim(self, length_pt: float) -> float:
        """Scale a scalar dimension (width/height/margin) from points to preview units."""
        return length_pt * self.scale_factor

    def preview_to_pt_x(self, x_preview: float) -> float:
        """Inverse convert an X coordinate from preview canvas space to PDF points."""
        return (x_preview - self.offset_x) / self.scale_factor

    def preview_to_pt_y(self, y_preview: float) -> float:
        """Inverse convert a Y coordinate from preview canvas space to PDF points."""
        return (y_preview - self.offset_y) / self.scale_factor

    def transform_point(self, x_pt: float, y_pt: float) -> PreviewPoint:
        """Transform a 2D point from points to preview coordinates."""
        return PreviewPoint(
            x=self.pt_to_preview_x(x_pt),
            y=self.pt_to_preview_y(y_pt),
        )

    def transform_bbox(
        self,
        x_min_pt: float,
        y_min_pt: float,
        x_max_pt: float,
        y_max_pt: float,
    ) -> PreviewBoundingBox:
        """Transform a bounding box from PDF points to preview canvas coordinates."""
        x_min_prev = self.pt_to_preview_x(x_min_pt)
        y_min_prev = self.pt_to_preview_y(y_min_pt)
        x_max_prev = self.pt_to_preview_x(x_max_pt)
        y_max_prev = self.pt_to_preview_y(y_max_pt)

        width_prev = x_max_prev - x_min_prev
        height_prev = y_max_prev - y_min_prev

        return PreviewBoundingBox(
            x=x_min_prev,
            y=y_min_prev,
            width=width_prev,
            height=height_prev,
            x_min=x_min_prev,
            y_min=y_min_prev,
            x_max=x_max_prev,
            y_max=y_max_prev,
        )

    def transform_line(
        self,
        x1_pt: float,
        y1_pt: float,
        x2_pt: float,
        y2_pt: float,
    ) -> tuple[float, float, float, float]:
        """Transform a line segment from points to preview coordinates."""
        return (
            self.pt_to_preview_x(x1_pt),
            self.pt_to_preview_y(y1_pt),
            self.pt_to_preview_x(x2_pt),
            self.pt_to_preview_y(y2_pt),
        )

    def get_rendered_page_box(self) -> PreviewBoundingBox:
        """Return the preview bounding box representing the full PDF sheet boundary."""
        return self.transform_bbox(0.0, 0.0, self.page_width_pt, self.page_height_pt)

