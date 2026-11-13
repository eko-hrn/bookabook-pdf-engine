"""Base abstract class for crop coordinate strategies.

Defines the interface that all layout-specific crop coordinate calculators must implement.
Uses existing Pydantic models from app.crop.models.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.crop.models.crop_region import CropRegion
from app.crop.models.crop_validation import CropValidationResult
from app.crop.models.enums import (
    ClassificationStatus,
    CropReadinessStatus,
    CropStrategyType,
    LayoutType,
    ManualReviewFlag,
    Orientation,
)
from app.crop.models.page_crop_plan import PageCropPlan
from app.crop.models.project_profile import ProjectTrimProfile


class BaseCropStrategy(ABC):
    """Abstract base class for crop coordinate calculation strategies."""

    def __init__(self, profile: ProjectTrimProfile) -> None:
        """Initialize with a project trim profile."""
        self.profile = profile

    @property
    @abstractmethod
    def strategy_type(self) -> CropStrategyType:
        """The strategy type enum member."""
        ...

    @property
    @abstractmethod
    def target_layout_type(self) -> LayoutType:
        """The target layout type enum member."""
        ...

    @abstractmethod
    def calculate(
        self,
        pdf_page_index: int,
        page_width_pt: float,
        page_height_pt: float,
        rotation: int = 0,
        **kwargs,
    ) -> PageCropPlan:
        """Calculate the PageCropPlan containing all CropRegion bounding boxes.

        Parameters:
            pdf_page_index: Zero-based PDF page index.
            page_width_pt: Measured page width in points.
            page_height_pt: Measured page height in points.
            rotation: PDF page rotation (0, 90, 180, 270).
            **kwargs: Strategy-specific parameters (e.g. tick marks, crop marks).

        Returns:
            Fully populated and validated PageCropPlan instance.
        """
        ...

    def validate_region(
        self,
        region: CropRegion,
        pdf_page_index: int,
        tick_deviation_x_mm: Optional[float] = None,
        tick_deviation_y_mm: Optional[float] = None,
    ) -> CropValidationResult:
        """Validate a single calculated crop region against profile requirements.

        Produces a CropValidationResult model instance.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Validate dimensions match expected targets
        actual_width_px = round(region.width_pt * (self.profile.dpi / 72.0))
        actual_height_px = round(region.height_pt * (self.profile.dpi / 72.0))

        # Check tick deviation if supplied
        tick_within_tolerance = None
        if tick_deviation_x_mm is not None and tick_deviation_y_mm is not None:
            tol = self.profile.tick_deviation_tolerance_mm
            tick_within_tolerance = (
                tick_deviation_x_mm <= tol + 1e-6
                and tick_deviation_y_mm <= tol + 1e-6
            )
            if not tick_within_tolerance:
                errors.append(
                    f"Tick mark deviation exceeds {tol} mm: "
                    f"dx={tick_deviation_x_mm:.3f} mm, dy={tick_deviation_y_mm:.3f} mm"
                )

        if region.target_width_px != actual_width_px or region.target_height_px != actual_height_px:
            # Check if this is the frontcover 100 DPI or 1px discrepancy
            if region.region_id == "COVER":
                warnings.append(
                    f"Front cover rendered dimensions ({actual_width_px}x{actual_height_px} @ {self.profile.dpi} DPI) "
                    f"vs target ({region.target_width_px}x{region.target_height_px} @ {self.profile.cover_dimensions.target_cover_dpi} DPI). "
                    f"Note: {self.profile.cover_dimensions.frontcover_height_discrepancy_note}"
                )
            else:
                errors.append(
                    f"Dimension mismatch for {region.region_id}: "
                    f"actual ({actual_width_px}x{actual_height_px}) vs expected ({region.target_width_px}x{region.target_height_px})"
                )

        is_valid = len(errors) == 0

        return CropValidationResult(
            region_id=region.region_id,
            pdf_page_index=pdf_page_index,
            is_valid=is_valid,
            actual_width_px=actual_width_px,
            actual_height_px=actual_height_px,
            expected_width_px=region.target_width_px,
            expected_height_px=region.target_height_px,
            tick_deviation_x_mm=tick_deviation_x_mm,
            tick_deviation_y_mm=tick_deviation_y_mm,
            tick_within_tolerance=tick_within_tolerance,
            errors=errors,
            warnings=warnings,
        )

