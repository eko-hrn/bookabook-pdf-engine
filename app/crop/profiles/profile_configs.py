"""Layout-specific crop profile configurations.

Provides factory functions that return pre-configured ProjectTrimProfile
instances for each layout type. All numeric values are from the specification.

NOTE: These profiles define project-level trim parameters. They do NOT
compute crop coordinates (that is Phase 1.2.2.2 scope).
"""

from __future__ import annotations

from app.crop.models.enums import CropStrategyType, ProductionBasis
from app.crop.models.project_profile import (
    CoverDimensions,
    CoverReferenceDimensions,
    OuterMarginConfig,
    ProjectTrimProfile,
)


def create_default_profile() -> ProjectTrimProfile:
    """Create the default Bookabook Comic A5 project trim profile.

    All values are from Spec §10.A JSON config and §17 reconciliation table.
    This profile covers all three crop strategies.
    """
    return ProjectTrimProfile(
        profile_id="bookabook_comic_a5_default",
        profile_name="Bookabook Comic A5 Standard",
        production_basis=ProductionBasis.OPTION_B_EXACT_TARGET,
        dpi=300,
        # Content target dimensions (Spec §8.B.2, §17)
        target_content_width_px=1773,
        target_content_height_px=2538,
        target_content_width_pt=425.52,
        target_content_height_pt=609.12,
        # Cover dimensions (Spec §8.A)
        cover_dimensions=CoverDimensions(
            target_backcover_width_px=1890,
            target_backcover_height_px=2657,
            target_backcover_dpi=300,
            target_cover_width_px=630,
            target_cover_height_px=886,
            target_cover_dpi=100,
            frontcover_height_discrepancy_note=(
                "100dpi 3x scaling yields 2658 px; vector 300dpi render "
                "yields 2657 px (1 px discrepancy, status UNRESOLVED_ROUNDING_1PX)"
            ),
        ),
        cover_auto_crop_enabled=False,
        # Outer margin config (Spec §10.A, §17)
        outer_margin=OuterMarginConfig(
            horizontal_pt=13.85,
            vertical_pt=14.50,
            horizontal_mm=4.886,
            vertical_mm=5.115,
        ),
        # Tick deviation tolerance (Spec §6.B)
        tick_deviation_tolerance_mm=1.0,
        # Spine config (Spec §8.B.1)
        spine_width_mm=15.02,
        spine_excluded=True,
        # All strategies apply
        applicable_strategies=[
            CropStrategyType.COVER,
            CropStrategyType.IMPOSITION_4UP,
            CropStrategyType.SINGLE_PAGE,
        ],
    )


def create_cover_profile() -> ProjectTrimProfile:
    """Create a profile specialized for Cover Spread processing.

    Cover auto-crop is always disabled (Spec §8.B.1, §15.A.6).
    Status is always MANUAL_REVIEW_REQUIRED.
    """
    return ProjectTrimProfile(
        profile_id="bookabook_cover_spread",
        profile_name="Bookabook Cover Spread (Manual Review Only)",
        production_basis=ProductionBasis.OPTION_B_EXACT_TARGET,
        dpi=300,
        target_content_width_px=1773,
        target_content_height_px=2538,
        target_content_width_pt=425.52,
        target_content_height_pt=609.12,
        cover_dimensions=CoverDimensions(
            target_backcover_width_px=1890,
            target_backcover_height_px=2657,
            target_backcover_dpi=300,
            target_cover_width_px=630,
            target_cover_height_px=886,
            target_cover_dpi=100,
            frontcover_height_discrepancy_note=(
                "100dpi 3x scaling yields 2658 px; vector 300dpi render "
                "yields 2657 px (1 px discrepancy, status UNRESOLVED_ROUNDING_1PX)"
            ),
        ),
        cover_auto_crop_enabled=False,
        outer_margin=OuterMarginConfig(
            horizontal_pt=13.85,
            vertical_pt=14.50,
            horizontal_mm=4.886,
            vertical_mm=5.115,
        ),
        tick_deviation_tolerance_mm=1.0,
        spine_width_mm=15.02,
        spine_excluded=True,
        applicable_strategies=[CropStrategyType.COVER],
    )


def create_imposition_4up_profile() -> ProjectTrimProfile:
    """Create a profile specialized for 4-Up Imposition processing.

    Uses midpoint tick anchors with Opsi B dimensions (1773×2538 px).
    """
    return ProjectTrimProfile(
        profile_id="bookabook_imposition_4up",
        profile_name="Bookabook 4-Up Imposition (Option B)",
        production_basis=ProductionBasis.OPTION_B_EXACT_TARGET,
        dpi=300,
        target_content_width_px=1773,
        target_content_height_px=2538,
        target_content_width_pt=425.52,
        target_content_height_pt=609.12,
        cover_dimensions=CoverDimensions(
            target_backcover_width_px=1890,
            target_backcover_height_px=2657,
            target_backcover_dpi=300,
            target_cover_width_px=630,
            target_cover_height_px=886,
            target_cover_dpi=100,
            frontcover_height_discrepancy_note=(
                "100dpi 3x scaling yields 2658 px; vector 300dpi render "
                "yields 2657 px (1 px discrepancy, status UNRESOLVED_ROUNDING_1PX)"
            ),
        ),
        cover_auto_crop_enabled=False,
        outer_margin=OuterMarginConfig(
            horizontal_pt=13.85,
            vertical_pt=14.50,
            horizontal_mm=4.886,
            vertical_mm=5.115,
        ),
        tick_deviation_tolerance_mm=1.0,
        spine_width_mm=15.02,
        spine_excluded=True,
        applicable_strategies=[CropStrategyType.IMPOSITION_4UP],
    )


def create_single_page_profile() -> ProjectTrimProfile:
    """Create a profile specialized for Single Page processing.

    Target: 1773×2538 px at 300 DPI (Spec §8.B.3).
    Non-nominal dimensions → MANUAL_REVIEW_REQUIRED until normalization
    policy is determined.
    """
    return ProjectTrimProfile(
        profile_id="bookabook_single_page",
        profile_name="Bookabook Single Page (A5 Direct Export)",
        production_basis=ProductionBasis.OPTION_B_EXACT_TARGET,
        dpi=300,
        target_content_width_px=1773,
        target_content_height_px=2538,
        target_content_width_pt=425.52,
        target_content_height_pt=609.12,
        cover_dimensions=CoverDimensions(
            target_backcover_width_px=1890,
            target_backcover_height_px=2657,
            target_backcover_dpi=300,
            target_cover_width_px=630,
            target_cover_height_px=886,
            target_cover_dpi=100,
            frontcover_height_discrepancy_note=(
                "100dpi 3x scaling yields 2658 px; vector 300dpi render "
                "yields 2657 px (1 px discrepancy, status UNRESOLVED_ROUNDING_1PX)"
            ),
        ),
        cover_auto_crop_enabled=False,
        outer_margin=OuterMarginConfig(
            horizontal_pt=13.85,
            vertical_pt=14.50,
            horizontal_mm=4.886,
            vertical_mm=5.115,
        ),
        tick_deviation_tolerance_mm=1.0,
        spine_width_mm=15.02,
        spine_excluded=True,
        applicable_strategies=[CropStrategyType.SINGLE_PAGE],
    )


def write_profile_configs_to_directory(output_dir: Path | str | None = None) -> list[Path]:
    """Write all profile configurations as JSON files to the specified directory.

    If output_dir is None, writes to the directory where this file resides.
    """
    import json
    from pathlib import Path

    if output_dir is None:
        target_dir = Path(__file__).parent
    else:
        target_dir = Path(output_dir)

    target_dir.mkdir(parents=True, exist_ok=True)

    profiles = {
        "profile_default.json": create_default_profile(),
        "profile_cover.json": create_cover_profile(),
        "profile_imposition_4up.json": create_imposition_4up_profile(),
        "profile_single_page.json": create_single_page_profile(),
    }

    written: list[Path] = []
    for filename, profile in profiles.items():
        filepath = target_dir / filename
        filepath.write_text(
            profile.model_dump_json(indent=2),
            encoding="utf-8",
        )
        written.append(filepath)

    return written


if __name__ == "__main__":
    for p in write_profile_configs_to_directory():
        print(f"Written profile config: {p}")

