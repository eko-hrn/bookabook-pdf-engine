"""Preview generation service.

Coordinates between CropCoordinateCalculator, CropPlanValidator,
and PreviewVisualizationEngine to generate structured preview payloads
and composite preview PNG images.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException
import pymupdf as fitz

from app.api.config import Settings, get_settings
from app.api.schemas.previews import DocumentPreviewResponse, PagePreviewInfo, PreviewRegionInfo
from app.api.services.document_service import DocumentService
from app.crop.calculator.calculator import CropCoordinateCalculator
from app.crop.calculator.unresolved import (
    UNRESOLVED_COVER_WIDTH_DISCREPANCY,
    UNRESOLVED_ROUNDING_1PX,
    UNRESOLVED_SINGLE_PAGE_NORMALIZATION_POLICY,
)
from app.crop.models.document_crop_plan import DocumentCropPlan
from app.crop.models.enums import LayoutType
from app.crop.models.page_crop_plan import PageCropPlan
from app.crop.preview.engine import PreviewVisualizationEngine
from app.crop.preview.models import PreviewDocumentPayload
from app.crop.preview.theme import get_status_style
from app.crop.validator.crop_plan_validator import CropPlanValidator
from app.crop.validator.report import DocumentValidationReport


class PreviewService:
    """Service responsible for preview calculations, validation, and raster rendering."""

    def __init__(
        self,
        document_service: Optional[DocumentService] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.doc_service = document_service or DocumentService(self.settings)
        self.calculator = CropCoordinateCalculator()
        self.validator = CropPlanValidator()
        self.preview_engine = PreviewVisualizationEngine(default_dpi=self.settings.PREVIEW_DPI)

        # In-memory cache: doc_id -> (DocumentCropPlan, DocumentValidationReport, PreviewDocumentPayload)
        self._cache: Dict[str, Tuple[DocumentCropPlan, DocumentValidationReport, PreviewDocumentPayload]] = {}

    def get_or_build_preview_pipeline(
        self, document_id: str
    ) -> Tuple[DocumentCropPlan, DocumentValidationReport, PreviewDocumentPayload]:
        """Retrieve cached preview data for document or calculate and validate from PDF."""
        if document_id in self._cache:
            return self._cache[document_id]

        pdf_path = self.doc_service.get_pdf_path(document_id)
        if pdf_path is None or not pdf_path.is_file():
            raise HTTPException(
                status_code=404,
                detail=f"Document with ID '{document_id}' was not found.",
            )

        # Build DocumentCropPlan from PDF
        doc_plan = self._build_document_crop_plan(document_id, pdf_path)

        # Validate Crop Plan
        validation_report = self.validator.validate_document(doc_plan)

        # Generate structured preview payload
        preview_payload = self.preview_engine.generate_document_preview(doc_plan)

        self._cache[document_id] = (doc_plan, validation_report, preview_payload)
        return doc_plan, validation_report, preview_payload

    def _build_document_crop_plan(self, document_id: str, pdf_path: Path) -> DocumentCropPlan:
        """Inspect PDF pages and dispatch to appropriate calculator strategies."""
        try:
            doc = fitz.open(str(pdf_path))
            page_count = doc.page_count
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to read PDF for crop planning: {str(exc)}",
            )

        page_plans: List[PageCropPlan] = []

        for i in range(page_count):
            page = doc.load_page(i)
            rect = page.rect
            w = round(float(rect.width), 2)
            h = round(float(rect.height), 2)
            rotation = page.rotation

            # Layout heuristic dispatch per Spec v1.3.4
            # Cover Spread (Landscape, ~1220-1270 pt x ~860-900 pt)
            if 1220.0 <= w <= 1270.0 and 860.0 <= h <= 900.0:
                try:
                    plan = self.calculator.calculate_cover(
                        pdf_page_index=i,
                        page_width_pt=w,
                        page_height_pt=h,
                        rotation=rotation,
                    )
                except ValueError:
                    plan = self.calculator.calculate_for_layout(
                        layout_type=None,
                        pdf_page_index=i,
                        page_width_pt=w,
                        page_height_pt=h,
                        rotation=rotation,
                    )
            # 4-Up Imposition (Portrait, ~860-900 pt x ~1220-1270 pt)
            elif 860.0 <= w <= 900.0 and 1220.0 <= h <= 1270.0:
                # Standard sequence offset if sheet 0 was cover
                start_page = (i - 1) * 4 + 1 if i >= 1 else 1
                plan = self.calculator.calculate_imposition_4up(
                    pdf_page_index=i,
                    page_width_pt=w,
                    page_height_pt=h,
                    rotation=rotation,
                    start_page_number=start_page,
                )
            # Single Page (Portrait, ~415-450 pt x ~590-640 pt)
            elif 415.0 <= w <= 450.0 and 590.0 <= h <= 640.0:
                plan = self.calculator.calculate_single_page(
                    pdf_page_index=i,
                    page_width_pt=w,
                    page_height_pt=h,
                    rotation=rotation,
                    page_number=i + 1,
                )
            else:
                # Unrecognized geometry
                plan = self.calculator.calculate_for_layout(
                    layout_type=None,
                    pdf_page_index=i,
                    page_width_pt=w,
                    page_height_pt=h,
                    rotation=rotation,
                )

            page_plans.append(plan)

        doc.close()

        # Assemble into complete DocumentCropPlan
        return self.calculator.create_document_crop_plan(
            source_filename=pdf_path.name,
            page_plans=page_plans,
        )

    def get_document_preview(self, document_id: str) -> DocumentPreviewResponse:
        """Return full structured preview metadata for the document."""
        doc_plan, val_report, preview_payload = self.get_or_build_preview_pipeline(document_id)

        meta = self.doc_service.get_document_metadata(document_id)
        source_name = meta.filename if meta else doc_plan.source_filename

        page_infos: List[PagePreviewInfo] = []
        for p_plan, p_prev in zip(doc_plan.page_plans, preview_payload.pages):
            warnings = [f.value for f in p_plan.manual_review_flags]
            discrepancies: List[str] = []

            if p_plan.layout_type == LayoutType.COVER_SPREAD:
                discrepancies.append(UNRESOLVED_COVER_WIDTH_DISCREPANCY)
                discrepancies.append(UNRESOLVED_ROUNDING_1PX)
            elif p_plan.layout_type == LayoutType.SINGLE_PAGE:
                if round(p_plan.width_pt, 2) != 425.52 or round(p_plan.height_pt, 2) != 609.12:
                    discrepancies.append(UNRESOLVED_SINGLE_PAGE_NORMALIZATION_POLICY)

            style = get_status_style(p_plan.crop_readiness.value)
            status_badge = {
                "status": p_plan.crop_readiness.value,
                "badge_text": style.badge_text,
                "accessibility_label": style.accessibility_label,
                "stroke_color": style.stroke_color,
                "fill_color": style.fill_color,
                "pattern_type": style.pattern_type,
            }

            preview_url = f"{self.settings.API_V1_STR}/documents/{document_id}/pages/{p_plan.pdf_page_number}/preview.png"
            region_infos = [
                PreviewRegionInfo(
                    region_id=reg.region_id,
                    quadrant=reg.quadrant,
                    width_pt=round(reg.width_pt, 3),
                    height_pt=round(reg.height_pt, 3),
                    target_width_px=reg.target_width_px,
                    target_height_px=reg.target_height_px,
                    blank_page_status=reg.blank_page_status.value,
                    preview_image_url=(
                        f"{self.settings.API_V1_STR}/documents/{document_id}"
                        f"/pages/{p_plan.pdf_page_number}/regions/{reg.region_id}/preview.png"
                    ),
                )
                for reg in p_plan.crop_regions
            ]

            page_infos.append(
                PagePreviewInfo(
                    page_number=p_plan.pdf_page_number,
                    pdf_page_index=p_plan.pdf_page_index,
                    width_pt=p_plan.width_pt,
                    height_pt=p_plan.height_pt,
                    orientation=p_plan.orientation.value,
                    layout_type=p_plan.layout_type.value if p_plan.layout_type else None,
                    crop_readiness=p_plan.crop_readiness.value,
                    expected_page_yield=p_plan.expected_page_yield,
                    preview_image_url=preview_url,
                    status_badge=status_badge,
                    warnings=warnings,
                    unresolved_discrepancies=discrepancies,
                    regions=region_infos,
                )
            )

        val_summary = {
            "is_valid": val_report.is_valid,
            "overall_status": val_report.document_status.document_status,
            "total_regions": val_report.total_regions,
            "valid_regions_count": val_report.valid_regions_count,
            "invalid_regions_count": val_report.invalid_regions_count,
            "errors": val_report.errors,
            "warnings": val_report.warnings,
        }

        return DocumentPreviewResponse(
            document_id=document_id,
            source_filename=source_name,
            total_pages=doc_plan.total_pdf_pages,
            expected_book_pages=doc_plan.expected_total_book_pages,
            document_status=doc_plan.document_status.document_status,
            has_unknown_layout=doc_plan.document_status.has_unknown_layout,
            has_manual_review_required=doc_plan.document_status.has_manual_review_required,
            pages=page_infos,
            validation_summary=val_summary,
        )

    def _resolve_page_and_pdf_path(
        self,
        document_id: str,
        page_number: int,
    ) -> Tuple[PageCropPlan, Path]:
        """Resolve validated PageCropPlan and source PDF path or raise HTTP 404."""
        doc_plan, _, _ = self.get_or_build_preview_pipeline(document_id)

        if page_number < 1 or page_number > len(doc_plan.page_plans):
            raise HTTPException(
                status_code=404,
                detail=f"Page {page_number} does not exist in document '{document_id}' (total pages: {len(doc_plan.page_plans)}).",
            )

        page_plan = doc_plan.page_plans[page_number - 1]
        pdf_path = self.doc_service.get_pdf_path(document_id)
        if pdf_path is None or not pdf_path.is_file():
            raise HTTPException(
                status_code=404,
                detail=f"PDF file for document '{document_id}' was not found.",
            )

        return page_plan, pdf_path

    def render_page_preview_png(
        self,
        document_id: str,
        page_number: int,
        overlay: bool = True,
    ) -> bytes:
        """Render and return preview PNG image bytes for a specific page."""
        page_plan, pdf_path = self._resolve_page_and_pdf_path(document_id, page_number)

        if not overlay:
            return self.preview_engine.render_clean_page_png(
                page_plan=page_plan,
                pdf_source=str(pdf_path),
                dpi=self.settings.PREVIEW_DPI,
            )

        preview_output = self.preview_engine.compose_page_preview(
            page_plan=page_plan,
            pdf_source=str(pdf_path),
            dpi=self.settings.PREVIEW_DPI,
        )

        return preview_output.image_bytes

    def render_region_preview_png(
        self,
        document_id: str,
        page_number: int,
        region_id: str,
        overlay: bool = True,
    ) -> bytes:
        """Render and return preview PNG image bytes for a single crop region."""
        page_plan, pdf_path = self._resolve_page_and_pdf_path(document_id, page_number)

        try:
            return self.preview_engine.render_region_preview_png(
                page_plan=page_plan,
                pdf_source=str(pdf_path),
                region_id=region_id,
                dpi=self.settings.PREVIEW_DPI,
                overlay=overlay,
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=404,
                detail=f"Region '{region_id}' does not exist on page {page_number} of document '{document_id}'.",
            ) from exc
