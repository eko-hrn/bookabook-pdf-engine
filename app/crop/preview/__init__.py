"""Preview Overlay & Visualization Engine — Phase 1.2.2.4 & Phase 1.2.2.5.

Provides coordinate transformations, accessible visual theming, structured
preview payloads, vector SVG preview generation, PyMuPDF PDF page rendering,
and raster overlay compositing.
"""

from app.crop.preview.compositor import PreviewCompositor
from app.crop.preview.engine import PreviewVisualizationEngine
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
    STYLE_CROP_READY,
    STYLE_MANUAL_REVIEW_REQUIRED,
    STYLE_MIDPOINT_CUT,
    STYLE_OUTER_TRIM,
    STYLE_REJECTED,
    STYLE_SPINE_EXCLUSION,
    STYLE_UNKNOWN_LAYOUT,
    PreviewVisualStyle,
    get_status_style,
)
from app.crop.preview.transformer import CoordinateTransformer, PreviewBoundingBox, PreviewPoint

__all__ = [
    # Engine, Renderer & Compositor
    "PreviewVisualizationEngine",
    "PDFPageRenderer",
    "PreviewCompositor",
    "SVGRenderer",
    # Coordinate Transformer
    "CoordinateTransformer",
    "PreviewPoint",
    "PreviewBoundingBox",
    # Payload Models
    "PreviewBox",
    "PreviewLine",
    "PreviewSpineZone",
    "PreviewStatusBadge",
    "PreviewRegion",
    "PreviewPagePayload",
    "PreviewDocumentPayload",
    "PreviewImageOutput",
    # Theme & Styles
    "PreviewVisualStyle",
    "get_status_style",
    "STYLE_CROP_READY",
    "STYLE_MANUAL_REVIEW_REQUIRED",
    "STYLE_UNKNOWN_LAYOUT",
    "STYLE_REJECTED",
    "STYLE_MIDPOINT_CUT",
    "STYLE_OUTER_TRIM",
    "STYLE_SPINE_EXCLUSION",
]


