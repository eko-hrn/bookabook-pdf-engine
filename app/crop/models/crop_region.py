"""CropRegion model — defines a single rectangular crop area.

Represents the bounding box coordinates for one output page extracted
from a PDF sheet. Coordinates are in PDF points (pt) relative to the
page MediaBox origin (bottom-left in PDF spec, but PyMuPDF uses top-left).

All formulas and coordinate values are from Spec §8.B.2 (Opsi B).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.crop.models.enums import BlankPageStatus


class CropRegion(BaseModel):
    """A single rectangular crop region in PDF coordinate space.

    Defines the bounding box [x_min, y_min, x_max, y_max] in points for
    one output page, plus target pixel dimensions at the profile DPI.

    Coordinate system follows PyMuPDF convention (origin at top-left).
    """

    # --- Region identity ---
    region_id: str = Field(
        ...,
        min_length=1,
        description=(
            "Output filename stem for this region "
            "(e.g. 'PAGE-01', 'PAGE-02', 'COVER', 'BACKCOVER')"
        ),
    )
    quadrant: Optional[int] = Field(
        default=None,
        ge=1,
        le=4,
        description="Quadrant index for 4-Up layout (1=TL, 2=TR, 3=BL, 4=BR). None for non-4-Up.",
    )

    # --- Bounding box coordinates (points) ---
    x_min_pt: float = Field(
        ...,
        ge=0,
        description="Left edge of crop region in points",
    )
    y_min_pt: float = Field(
        ...,
        ge=0,
        description="Top edge of crop region in points",
    )
    x_max_pt: float = Field(
        ...,
        description="Right edge of crop region in points",
    )
    y_max_pt: float = Field(
        ...,
        description="Bottom edge of crop region in points",
    )

    # --- Target output dimensions (pixels) ---
    target_width_px: int = Field(
        ..., gt=0,
        description="Expected output width in pixels at render DPI",
    )
    target_height_px: int = Field(
        ..., gt=0,
        description="Expected output height in pixels at render DPI",
    )

    # --- Blank page detection metadata ---
    blank_page_status: BlankPageStatus = Field(
        default=BlankPageStatus.CONTENT_PRESENT,
        description="Blank page detection result (Spec §7.B). Non-blocking warning.",
    )

    @model_validator(mode="after")
    def _validate_bbox_order(self) -> "CropRegion":
        """Ensure bounding box coordinates are properly ordered."""
        if self.x_max_pt <= self.x_min_pt:
            raise ValueError(
                f"x_max_pt ({self.x_max_pt}) must be greater than "
                f"x_min_pt ({self.x_min_pt})"
            )
        if self.y_max_pt <= self.y_min_pt:
            raise ValueError(
                f"y_max_pt ({self.y_max_pt}) must be greater than "
                f"y_min_pt ({self.y_min_pt})"
            )
        return self

    @model_validator(mode="after")
    def _validate_positive_area(self) -> "CropRegion":
        """Ensure the crop region has non-zero area."""
        width = self.x_max_pt - self.x_min_pt
        height = self.y_max_pt - self.y_min_pt
        if width <= 0 or height <= 0:
            raise ValueError(
                f"Crop region must have positive area. "
                f"Width={width:.3f} pt, Height={height:.3f} pt"
            )
        return self

    @property
    def width_pt(self) -> float:
        """Width of the crop region in points."""
        return self.x_max_pt - self.x_min_pt

    @property
    def height_pt(self) -> float:
        """Height of the crop region in points."""
        return self.y_max_pt - self.y_min_pt

