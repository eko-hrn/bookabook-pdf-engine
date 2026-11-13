"""CropValidationResult model — validation outcome for a crop operation.

Captures whether a computed crop region passes all safety guardrails
before actual cropping execution. This is the output of the validation
step, NOT the cropping itself (Phase 1.2.2.1 scope).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator


class CropValidationResult(BaseModel):
    """Result of validating a single crop region against safety rules.

    Used to report whether a proposed crop operation is safe to execute
    automatically or requires manual review.
    """

    # --- Identity ---
    region_id: str = Field(
        ...,
        min_length=1,
        description="Region identifier matching CropRegion.region_id",
    )
    pdf_page_index: int = Field(
        ..., ge=0,
        description="Zero-based page index of the source PDF page",
    )

    # --- Validation result ---
    is_valid: bool = Field(
        ...,
        description="Whether all validation checks passed",
    )

    # --- Dimension validation ---
    actual_width_px: Optional[int] = Field(
        default=None, gt=0,
        description="Actual rendered width in pixels (if computed)",
    )
    actual_height_px: Optional[int] = Field(
        default=None, gt=0,
        description="Actual rendered height in pixels (if computed)",
    )
    expected_width_px: int = Field(
        ..., gt=0,
        description="Expected width in pixels from profile target",
    )
    expected_height_px: int = Field(
        ..., gt=0,
        description="Expected height in pixels from profile target",
    )
    dimension_match: Optional[bool] = Field(
        default=None,
        description=(
            "Whether actual dimensions match expected "
            "(None if not yet computed)"
        ),
    )

    # --- Tick mark deviation (4-Up only) ---
    tick_deviation_x_mm: Optional[float] = Field(
        default=None, ge=0,
        description="Tick mark deviation on X axis in mm (4-Up only)",
    )
    tick_deviation_y_mm: Optional[float] = Field(
        default=None, ge=0,
        description="Tick mark deviation on Y axis in mm (4-Up only)",
    )
    tick_within_tolerance: Optional[bool] = Field(
        default=None,
        description=(
            "Whether tick deviations are within tolerance "
            "(≤ 1.0 mm per Spec §6.B)"
        ),
    )

    # --- Validation messages ---
    errors: list[str] = Field(
        default_factory=list,
        description="List of validation error messages",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="List of validation warning messages (non-blocking)",
    )

    @model_validator(mode="after")
    def _validate_consistency(self) -> "CropValidationResult":
        """Ensure is_valid is consistent with errors list."""
        if self.is_valid and self.errors:
            raise ValueError(
                "is_valid=True is inconsistent with non-empty errors list"
            )
        if not self.is_valid and not self.errors:
            raise ValueError(
                "is_valid=False requires at least one error message"
            )
        return self

    @model_validator(mode="after")
    def _validate_dimension_match(self) -> "CropValidationResult":
        """Compute dimension_match if actual dimensions are provided."""
        if self.actual_width_px is not None and self.actual_height_px is not None:
            match = (
                self.actual_width_px == self.expected_width_px
                and self.actual_height_px == self.expected_height_px
            )
            if self.dimension_match is not None and self.dimension_match != match:
                raise ValueError(
                    f"dimension_match={self.dimension_match} is inconsistent "
                    f"with actual ({self.actual_width_px}x{self.actual_height_px}) "
                    f"vs expected ({self.expected_width_px}x{self.expected_height_px})"
                )
            self.dimension_match = match
        return self

