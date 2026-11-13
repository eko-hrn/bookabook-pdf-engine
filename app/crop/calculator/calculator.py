"""CropCoordinateCalculator — Unified coordinator for crop coordinate calculation.

Dispatches page-level crop planning to the layout-specific strategy:
1. CoverCropStrategy (Layout A)
2. Imposition4UpCropStrategy (Layout B)
3. SinglePageCropStrategy (Layout C)

Integrates directly with:
- ProjectTrimProfile configuration
- PageCropPlan & DocumentCropPlan models
- CropValidationResult safety validator
"""

from __future__ import annotations

from typing import Optional, Sequence

from app.crop.calculator.base import BaseCropStrategy
from app.crop.calculator.cover_strategy import CoverCropMarks, CoverCropStrategy
from app.crop.calculator.imposition_4up_strategy import (
    Imposition4UpCropStrategy,
    TickMarkCoordinates,
)
from app.crop.calculator.single_page_strategy import SinglePageCropStrategy
from app.crop.models.crop_region import CropRegion
from app.crop.models.crop_validation import CropValidationResult
from app.crop.models.document_crop_plan import DocumentCropPlan, DocumentStatus
from app.crop.models.enums import (
    BlankPageStatus,
    ClassificationStatus,
    CropReadinessStatus,
    CropStrategyType,
    LayoutType,
    Orientation,
)
from app.crop.models.page_crop_plan import PageCropPlan
from app.crop.models.project_profile import ProjectTrimProfile
from app.crop.profiles.profile_configs import create_default_profile


class CropCoordinateCalculator:
    """Unified crop coordinate calculator for the Bookabook PDF Engine.

    Coordinates all layout strategies and safety guardrails according to
    Layout Classifier Specification v1.3.4.
    """

    def __init__(self, profile: Optional[ProjectTrimProfile] = None) -> None:
        """Initialize calculator with project trim profile.

        If profile is None, uses create_default_profile().
        """
        self.profile = profile or create_default_profile()
        self.cover_strategy = CoverCropStrategy(self.profile)
        self.imposition_4up_strategy = Imposition4UpCropStrategy(self.profile)
        self.single_page_strategy = SinglePageCropStrategy(self.profile)

        self._strategy_map: dict[LayoutType, BaseCropStrategy] = {
            LayoutType.COVER_SPREAD: self.cover_strategy,
            LayoutType.IMPOSITION_4UP: self.imposition_4up_strategy,
            LayoutType.SINGLE_PAGE: self.single_page_strategy,
        }

    def get_strategy(self, layout_type: LayoutType) -> BaseCropStrategy:
        """Retrieve the strategy implementation for a given layout type."""
        if layout_type not in self._strategy_map:
            raise ValueError(f"No crop strategy registered for layout type: {layout_type}")
        return self._strategy_map[layout_type]

    def calculate_cover(
        self,
        pdf_page_index: int = 0,
        page_width_pt: float = 1247.24,
        page_height_pt: float = 878.74,
        rotation: int = 0,
        marks: Optional[CoverCropMarks] = None,
        anchor_to_target_width: bool = False,
    ) -> PageCropPlan:
        """Calculate PageCropPlan for Cover Spread."""
        return self.cover_strategy.calculate(
            pdf_page_index=pdf_page_index,
            page_width_pt=page_width_pt,
            page_height_pt=page_height_pt,
            rotation=rotation,
            marks=marks,
            anchor_to_target_width=anchor_to_target_width,
        )

    def calculate_imposition_4up(
        self,
        pdf_page_index: int = 1,
        page_width_pt: float = 878.74,
        page_height_pt: float = 1247.24,
        rotation: int = 0,
        ticks: Optional[TickMarkCoordinates] = None,
        start_page_number: Optional[int] = None,
        blank_statuses: Optional[list[BlankPageStatus]] = None,
        is_flipped: bool = False,
    ) -> PageCropPlan:
        """Calculate PageCropPlan for 4-Up Imposition Grid."""
        return self.imposition_4up_strategy.calculate(
            pdf_page_index=pdf_page_index,
            page_width_pt=page_width_pt,
            page_height_pt=page_height_pt,
            rotation=rotation,
            ticks=ticks,
            start_page_number=start_page_number,
            blank_statuses=blank_statuses,
            is_flipped=is_flipped,
        )

    def calculate_single_page(
        self,
        pdf_page_index: int = 0,
        page_width_pt: float = 425.52,
        page_height_pt: float = 609.12,
        rotation: int = 0,
        crop_bbox_pt: Optional[tuple[float, float, float, float]] = None,
        page_number: Optional[int] = None,
        blank_status: BlankPageStatus = BlankPageStatus.CONTENT_PRESENT,
    ) -> PageCropPlan:
        """Calculate PageCropPlan for Single Page Layout."""
        return self.single_page_strategy.calculate(
            pdf_page_index=pdf_page_index,
            page_width_pt=page_width_pt,
            page_height_pt=page_height_pt,
            rotation=rotation,
            crop_bbox_pt=crop_bbox_pt,
            page_number=page_number,
            blank_status=blank_status,
        )

    def calculate_for_layout(
        self,
        layout_type: Optional[LayoutType],
        pdf_page_index: int,
        page_width_pt: float,
        page_height_pt: float,
        rotation: int = 0,
        **kwargs,
    ) -> PageCropPlan:
        """Dispatch calculation based on layout type.

        If layout_type is None or unrecognized, returns an UNKNOWN_LAYOUT plan
        with crop_readiness=NOT_APPLICABLE.
        """
        if layout_type is None:
            orientation = Orientation.LANDSCAPE if page_width_pt > page_height_pt else Orientation.PORTRAIT
            return PageCropPlan(
                pdf_page_index=pdf_page_index,
                pdf_page_number=pdf_page_index + 1,
                width_pt=page_width_pt,
                height_pt=page_height_pt,
                orientation=orientation,
                rotation=rotation,
                layout_type=None,
                classification_status=ClassificationStatus.UNKNOWN_LAYOUT,
                confidence_score=0.0,
                crop_strategy=None,
                crop_readiness=CropReadinessStatus.NOT_APPLICABLE,
                manual_review_flags=[],
                crop_regions=[],
                expected_page_yield=0,
            )

        strategy = self.get_strategy(layout_type)
        return strategy.calculate(
            pdf_page_index=pdf_page_index,
            page_width_pt=page_width_pt,
            page_height_pt=page_height_pt,
            rotation=rotation,
            **kwargs,
        )

    def validate_plan(
        self,
        plan: PageCropPlan,
        tick_deviation_x_mm: Optional[float] = None,
        tick_deviation_y_mm: Optional[float] = None,
    ) -> list[CropValidationResult]:
        """Validate all crop regions within a PageCropPlan against profile specifications.

        Returns a list of CropValidationResult instances (one per region).
        """
        results: list[CropValidationResult] = []

        if not plan.crop_regions:
            return results

        if plan.layout_type is not None:
            strategy = self.get_strategy(plan.layout_type)
        else:
            strategy = self.imposition_4up_strategy

        for region in plan.crop_regions:
            val_result = strategy.validate_region(
                region=region,
                pdf_page_index=plan.pdf_page_index,
                tick_deviation_x_mm=tick_deviation_x_mm,
                tick_deviation_y_mm=tick_deviation_y_mm,
            )
            results.append(val_result)

        return results

    def create_document_crop_plan(
        self,
        source_filename: str,
        page_plans: Sequence[PageCropPlan],
        validation_results: Optional[list[CropValidationResult]] = None,
    ) -> DocumentCropPlan:
        """Assemble individual PageCropPlan results into a full DocumentCropPlan.

        Enforces all document-level consistency constraints:
        - Total page count matching
        - Expected page yield sum
        - Page sequence signature matching
        - DocumentStatus determination (AUTO_READY_FOR_PREVIEW vs MANUAL_REVIEW_REQUIRED vs REJECTED_UNKNOWN_LAYOUT)
        """
        total_pages = len(page_plans)
        total_yield = sum(p.expected_page_yield for p in page_plans)
        signature = [p.layout_type.value if p.layout_type else p.classification_status.value for p in page_plans]

        # Determine document status per Spec §12
        has_unknown = any(
            p.classification_status == ClassificationStatus.UNKNOWN_LAYOUT
            for p in page_plans
        )
        has_manual_review = any(
            p.crop_readiness == CropReadinessStatus.MANUAL_REVIEW_REQUIRED
            for p in page_plans
        )
        all_crop_ready = not has_unknown and not has_manual_review

        if has_unknown:
            status_str = "REJECTED_UNKNOWN_LAYOUT"
        elif has_manual_review:
            status_str = "MANUAL_REVIEW_REQUIRED"
        else:
            status_str = "AUTO_READY_FOR_PREVIEW"

        doc_status = DocumentStatus(
            has_unknown_layout=has_unknown,
            has_manual_review_required=has_manual_review,
            all_pages_crop_ready=all_crop_ready,
            document_status=status_str,
        )

        return DocumentCropPlan(
            source_filename=source_filename,
            total_pdf_pages=total_pages,
            expected_total_book_pages=total_yield,
            profile=self.profile,
            page_sequence_signature=signature,
            document_status=doc_status,
            page_plans=list(page_plans),
            validation_results=validation_results or [],
        )
