"""ProjectTrimProfile model — project-level trim & output configuration.

All numeric values are derived from Layout Classifier Specification v1.3.4,
Section 10.A (JSON Config) and Section 17 (Reconciliation Table).
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from app.crop.models.enums import CropStrategyType, LayoutType, ProductionBasis


class CoverReferenceDimensions(BaseModel):
    """Reference dimensions for cover files from designer ground truth (Spec §8.A).

    These are observed values from the reference raster files.
    """

    width_px: int = Field(..., gt=0, description="Width in pixels")
    height_px: int = Field(..., gt=0, description="Height in pixels")
    dpi: int = Field(..., gt=0, description="Resolution in DPI")


class CoverDimensions(BaseModel):
    """Cover target dimensions per specification (Spec §8.A, §14.A.4, §16.1).

    Specification defines distinct output dimensions:
    - BACKCOVER.jpg: 1890 × 2657 px @ 300 DPI
    - COVER.jpg: 630 × 886 px @ 100 DPI
    """

    target_backcover_width_px: int = Field(
        ..., gt=0,
        description="BACKCOVER.jpg target width at 300 DPI (Spec §8.A: 1890 px)"
    )
    target_backcover_height_px: int = Field(
        ..., gt=0,
        description="BACKCOVER.jpg target height at 300 DPI (Spec §8.A: 2657 px)"
    )
    target_backcover_dpi: int = Field(
        default=300, gt=0,
        description="BACKCOVER.jpg resolution in DPI (Spec §8.A: 300 DPI)"
    )
    target_cover_width_px: int = Field(
        ..., gt=0,
        description="COVER.jpg target width at 100 DPI (Spec §8.A, §14.A.4: 630 px)"
    )
    target_cover_height_px: int = Field(
        ..., gt=0,
        description="COVER.jpg target height at 100 DPI (Spec §8.A, §14.A.4: 886 px)"
    )
    target_cover_dpi: int = Field(
        default=100, gt=0,
        description="COVER.jpg resolution in DPI (Spec §8.A: 100 DPI)"
    )
    frontcover_height_discrepancy_note: str = Field(
        ...,
        description=(
            "Documents the 1 px discrepancy between 3x scaling (2658 px) "
            "and vector 300 DPI render (2657 px). Status: UNRESOLVED_ROUNDING_1PX"
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _migrate_frontcover_fields(cls, data: Any) -> Any:
        """Allow backwards-compatible input dictionaries."""
        if isinstance(data, dict):
            if "target_cover_width_px" not in data:
                if "frontcover_reference_100dpi" in data and isinstance(data["frontcover_reference_100dpi"], dict):
                    data["target_cover_width_px"] = data["frontcover_reference_100dpi"].get("width_px", 630)
                elif "target_frontcover_width_px" in data:
                    data["target_cover_width_px"] = data["target_frontcover_width_px"]
            if "target_cover_height_px" not in data:
                if "frontcover_reference_100dpi" in data and isinstance(data["frontcover_reference_100dpi"], dict):
                    data["target_cover_height_px"] = data["frontcover_reference_100dpi"].get("height_px", 886)
                elif "target_frontcover_height_px" in data:
                    data["target_cover_height_px"] = data["target_frontcover_height_px"]
        return data

    @model_validator(mode="after")
    def _validate_not_identical(self) -> "CoverDimensions":
        """Enforce BACKCOVER and COVER do not have identical output dimensions."""
        if (
            self.target_backcover_width_px == self.target_cover_width_px
            and self.target_backcover_height_px == self.target_cover_height_px
            and self.target_backcover_dpi == self.target_cover_dpi
        ):
            raise ValueError(
                "BACKCOVER and COVER cannot have identical output dimensions and resolution. "
                "Specification v1.3.4 explicitly requires BACKCOVER (1890x2657 @ 300 DPI) "
                "and COVER (630x886 @ 100 DPI)."
            )
        return self

    @property
    def target_frontcover_width_px(self) -> int:
        return self.target_cover_width_px

    @property
    def target_frontcover_height_px(self) -> int:
        return self.target_cover_height_px

    @property
    def frontcover_reference_100dpi(self) -> CoverReferenceDimensions:
        return CoverReferenceDimensions(
            width_px=self.target_cover_width_px,
            height_px=self.target_cover_height_px,
            dpi=self.target_cover_dpi,
        )


class OuterMarginConfig(BaseModel):
    """Outer margin trimming parameters for 4-Up imposition (Spec §10.A, §17).

    These are the digital margins trimmed from the 4 outer edges of the
    imposition sheet to yield the clean A5 book page dimensions.
    """

    horizontal_pt: float = Field(
        ..., gt=0,
        description="Horizontal outer margin in points (Spec §10.A: 13.85 pt)"
    )
    vertical_pt: float = Field(
        ..., gt=0,
        description="Vertical outer margin in points (Spec §10.A: 14.50 pt)"
    )
    horizontal_mm: float = Field(
        ..., gt=0,
        description="Horizontal outer margin in mm (Spec §10.A: 4.886 mm)"
    )
    vertical_mm: float = Field(
        ..., gt=0,
        description="Vertical outer margin in mm (Spec §10.A: 5.115 mm)"
    )


class ProjectTrimProfile(BaseModel):
    """Project-level trim configuration profile (Spec §10.A, §15.A).

    Defines target output dimensions, margin parameters, and production rules
    for the entire project. This is the top-level configuration that governs
    all crop operations.

    All dimension values originate from the specification's reconciliation
    table (§17) and JSON config example (§10.A).
    """

    profile_id: str = Field(
        ...,
        min_length=1,
        pattern=r"^[a-z0-9_]+$",
        description="Unique profile identifier (lowercase, underscores only)",
    )
    profile_name: str = Field(
        ...,
        min_length=1,
        description="Human-readable profile name",
    )
    production_basis: ProductionBasis = Field(
        ...,
        description="Production output dimension basis (Spec §15.A.5)",
    )
    dpi: int = Field(
        default=300,
        gt=0,
        description="Output resolution in DPI (Spec §8.B: 300 DPI)",
    )

    # --- Content page target dimensions (4-Up & Single Page) ---
    target_content_width_px: int = Field(
        ..., gt=0,
        description="Target content page width at 300 DPI (Spec §8.B.2: 1773 px)",
    )
    target_content_height_px: int = Field(
        ..., gt=0,
        description="Target content page height at 300 DPI (Spec §8.B.2: 2538 px)",
    )
    target_content_width_pt: float = Field(
        ..., gt=0,
        description="Target content page width in points (Spec §8.B.2: 425.52 pt)",
    )
    target_content_height_pt: float = Field(
        ..., gt=0,
        description="Target content page height in points (Spec §8.B.2: 609.12 pt)",
    )

    # --- Cover dimensions ---
    cover_dimensions: CoverDimensions = Field(
        ...,
        description="Cover target dimensions and discrepancy tracking",
    )
    cover_auto_crop_enabled: bool = Field(
        default=False,
        description=(
            "Cover auto-crop production flag (Spec §8.B.1: ALWAYS False). "
            "Cover sheets must remain MANUAL_REVIEW_REQUIRED."
        ),
    )

    # --- Outer margin config (4-Up) ---
    outer_margin: OuterMarginConfig = Field(
        ...,
        description="Outer margin trimming parameters for 4-Up imposition",
    )

    # --- Tick mark tolerance ---
    tick_deviation_tolerance_mm: float = Field(
        ..., gt=0,
        description="Maximum tick mark deviation tolerance in mm (Spec §6.B: 1.0 mm)",
    )
    tick_deviation_tolerance_pt: float = Field(
        default=None,
        description=(
            "Computed: tick_deviation_tolerance_mm converted to points. "
            "1 mm = 2.835 pt (Spec §6.B)."
        ),
    )

    # --- Spine config (Cover) ---
    spine_width_mm: float = Field(
        ..., gt=0,
        description="Spine width in mm (Spec §8.B.1: 15.02 mm)",
    )
    spine_excluded: bool = Field(
        default=True,
        description="Whether spine zone is excluded from cover crop (Spec §8.B.1)",
    )

    # --- Applicable strategies ---
    applicable_strategies: list[CropStrategyType] = Field(
        default_factory=lambda: list(CropStrategyType),
        description="Crop strategies this profile applies to",
    )

    @model_validator(mode="after")
    def _compute_tick_tolerance_pt(self) -> "ProjectTrimProfile":
        """Convert tick deviation tolerance from mm to points (1 mm = 2.835 pt)."""
        if self.tick_deviation_tolerance_pt is None:
            # 1 mm = 72 / 25.4 pt ≈ 2.8346 pt
            self.tick_deviation_tolerance_pt = round(
                self.tick_deviation_tolerance_mm * (72.0 / 25.4), 3
            )
        return self

    @model_validator(mode="after")
    def _validate_cover_auto_crop_disabled(self) -> "ProjectTrimProfile":
        """Enforce cover auto-crop is disabled (Spec §8.B.1, §15.A.6)."""
        if self.cover_auto_crop_enabled:
            raise ValueError(
                "cover_auto_crop_enabled must be False. "
                "Cover auto-crop is prohibited per Spec §8.B.1 and §15.A.6 "
                "until cover formula is validated by designer/admin."
            )
        return self

    @model_validator(mode="after")
    def _validate_content_pixel_dimensions(self) -> "ProjectTrimProfile":
        """Validate that pt-to-px conversion matches declared pixel targets.

        Formula: px = round(pt × dpi / 72) — Spec §8.B.2, §15.B.3.
        """
        expected_w = round(self.target_content_width_pt * self.dpi / 72.0)
        expected_h = round(self.target_content_height_pt * self.dpi / 72.0)

        if self.target_content_width_px != expected_w:
            raise ValueError(
                f"target_content_width_px={self.target_content_width_px} does not "
                f"match round({self.target_content_width_pt} × {self.dpi}/72) = "
                f"{expected_w}"
            )
        if self.target_content_height_px != expected_h:
            raise ValueError(
                f"target_content_height_px={self.target_content_height_px} does not "
                f"match round({self.target_content_height_pt} × {self.dpi}/72) = "
                f"{expected_h}"
            )
        return self

    @model_validator(mode="after")
    def _validate_no_stretching(self) -> "ProjectTrimProfile":
        """Validate aspect ratio consistency to prevent image stretching.

        The aspect ratio of pt dimensions must match the aspect ratio of
        pixel dimensions within floating-point tolerance.
        """
        pt_ratio = self.target_content_width_pt / self.target_content_height_pt
        px_ratio = self.target_content_width_px / self.target_content_height_px
        if abs(pt_ratio - px_ratio) > 0.001:
            raise ValueError(
                f"Aspect ratio mismatch (no stretching allowed): "
                f"pt ratio={pt_ratio:.6f}, px ratio={px_ratio:.6f}"
            )
        return self

