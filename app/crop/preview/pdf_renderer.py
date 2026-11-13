"""PDF Page Rendering via PyMuPDF (Phase 1.2.2.5).

Renders PDF pages into in-memory raster images (PIL Image or PNG bytes)
at configurable preview resolutions (default 100 DPI) for visual preview overlays.

Guarantees:
1. Strict read-only operation: never modifies, alters, or saves to the source PDF.
2. Aspect ratio preservation: renders pages at their native physical aspect ratio.
3. In-memory operation: does not require writing intermediate files to disk.
4. Production isolation: preview rendering is completely distinct from production cropping.
   Never crops or slices the source PDF.
"""

from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
from typing import Generator, Union

from PIL import Image
import pymupdf


class PDFPageRenderer:
    """Renders PDF pages into raster preview images using PyMuPDF."""

    def __init__(self, default_dpi: int = 100) -> None:
        """Initialize PDF renderer.

        Args:
            default_dpi: Default rasterization resolution for preview images (default: 100 DPI).
        """
        if default_dpi <= 0:
            raise ValueError(f"Preview DPI must be positive. Got: {default_dpi}")
        self.default_dpi = default_dpi

    @contextlib.contextmanager
    def open_pdf(
        self,
        source: Union[pymupdf.Document, str, Path, bytes],
    ) -> Generator[pymupdf.Document, None, None]:
        """Safely open a PDF document from an existing Document, file path, or bytes.

        Ensures resources are cleaned up if opened internally, while preserving
        external Document instances without modification or closure.
        """
        if isinstance(source, pymupdf.Document):
            yield source
        elif isinstance(source, (str, Path)):
            path_obj = Path(source)
            if not path_obj.exists():
                raise FileNotFoundError(f"PDF source file not found: {source}")
            doc = pymupdf.open(str(path_obj))
            try:
                yield doc
            finally:
                doc.close()
        elif isinstance(source, bytes):
            if len(source) == 0:
                raise ValueError("PDF source bytes cannot be empty")
            doc = pymupdf.open(stream=source, filetype="pdf")
            try:
                yield doc
            finally:
                doc.close()
        else:
            raise TypeError(
                f"Unsupported PDF source type: {type(source).__name__}. "
                f"Expected pymupdf.Document, str, Path, or bytes."
            )

    def get_page_count(self, source: Union[pymupdf.Document, str, Path, bytes]) -> int:
        """Return the total number of pages in the PDF document."""
        with self.open_pdf(source) as doc:
            return len(doc)

    def get_page_dimensions_pt(
        self,
        source: Union[pymupdf.Document, str, Path, bytes],
        page_index: int,
    ) -> tuple[float, float]:
        """Return the physical width and height of a PDF page in points (pt).

        Args:
            source: PDF document, path, or bytes.
            page_index: Zero-based page index.

        Returns:
            (width_pt, height_pt) tuple in points.
        """
        with self.open_pdf(source) as doc:
            self._validate_page_index(doc, page_index)
            page = doc[page_index]
            rect = page.rect
            return (float(rect.width), float(rect.height))

    def get_page_rotation(
        self,
        source: Union[pymupdf.Document, str, Path, bytes],
        page_index: int,
    ) -> int:
        """Return the page rotation in degrees (0, 90, 180, 270)."""
        with self.open_pdf(source) as doc:
            self._validate_page_index(doc, page_index)
            return int(doc[page_index].rotation)

    def render_page_to_image(
        self,
        source: Union[pymupdf.Document, str, Path, bytes],
        page_index: int,
        dpi: int | None = None,
    ) -> Image.Image:
        """Render a single PDF page into an in-memory PIL Image (RGB).

        Strictly preserves aspect ratio and does not perform any cropping or slicing.

        Args:
            source: PDF Document, file path, or bytes.
            page_index: Zero-based page index to render.
            dpi: Resolution for rasterization. If None, uses default_dpi.

        Returns:
            PIL.Image.Image in RGB mode.
        """
        render_dpi = dpi if dpi is not None else self.default_dpi
        if render_dpi <= 0:
            raise ValueError(f"DPI must be positive. Got: {render_dpi}")

        with self.open_pdf(source) as doc:
            self._validate_page_index(doc, page_index)
            page = doc[page_index]
            pix = page.get_pixmap(dpi=render_dpi, alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            return img

    def render_page_to_bytes(
        self,
        source: Union[pymupdf.Document, str, Path, bytes],
        page_index: int,
        dpi: int | None = None,
        image_format: str = "PNG",
    ) -> bytes:
        """Render a single PDF page into raw image bytes (default PNG format).

        Args:
            source: PDF Document, file path, or bytes.
            page_index: Zero-based page index to render.
            dpi: Resolution for rasterization. If None, uses default_dpi.
            image_format: Format string ('PNG'). Note: Previews must never be production JPGs.

        Returns:
            Bytes representing the encoded image.
        """
        img = self.render_page_to_image(source=source, page_index=page_index, dpi=dpi)
        buffer = io.BytesIO()
        img.save(buffer, format=image_format)
        return buffer.getvalue()

    def render_region_to_image(
        self,
        source: Union[pymupdf.Document, str, Path, bytes],
        page_index: int,
        clip_rect_pt: tuple[float, float, float, float],
        dpi: int | None = None,
    ) -> Image.Image:
        """Render a clipped crop region of a PDF page into an in-memory PIL Image (RGB).

        Strictly read-only and preserves exact physical region aspect ratio.
        """
        render_dpi = dpi if dpi is not None else self.default_dpi
        if render_dpi <= 0:
            raise ValueError(f"DPI must be positive. Got: {render_dpi}")

        x_min, y_min, x_max, y_max = clip_rect_pt
        if x_max <= x_min or y_max <= y_min:
            raise ValueError(f"Invalid clip rectangle in points: {clip_rect_pt}")

        with self.open_pdf(source) as doc:
            self._validate_page_index(doc, page_index)
            page = doc[page_index]
            clip = pymupdf.Rect(x_min, y_min, x_max, y_max)
            pix = page.get_pixmap(dpi=render_dpi, clip=clip, alpha=False)
            return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    @staticmethod
    def _validate_page_index(doc: pymupdf.Document, page_index: int) -> None:
        """Verify that page_index is within valid range."""
        if not (0 <= page_index < len(doc)):
            raise IndexError(
                f"Page index {page_index} out of range for document with {len(doc)} pages (0..{len(doc)-1})"
            )

