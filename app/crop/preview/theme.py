"""Preview Visual Styles and Theme Configuration (Phase 1.2.2.4).

Defines the styling rules, color palettes, border patterns, and text badges
for preview visualization.

Accessibility requirement:
"Do not use color alone. Include text labels."
Every status style incorporates text badges, pattern types, stroke dash arrays,
and accessible ARIA labels.
"""

from __future__ import annotations

from typing import Final
from pydantic import BaseModel, Field

from app.crop.models.enums import CropReadinessStatus


class PreviewVisualStyle(BaseModel):
    """Visual style specification for preview overlay elements."""

    status_name: str = Field(..., description="Machine-readable status name")
    badge_text: str = Field(..., description="Human-readable text badge (never use color alone)")
    accessibility_label: str = Field(..., description="Screen-reader descriptive label")
    stroke_color: str = Field(..., description="Border/line stroke hex color")
    fill_color: str = Field(..., description="Fill hex or rgba color with transparency")
    stroke_width: float = Field(default=2.0, description="Stroke line width in preview units")
    stroke_dasharray: str = Field(default="none", description="SVG stroke dasharray pattern")
    pattern_type: str = Field(default="solid", description="Pattern descriptor: solid, dashed, dotted, dash-dot")


# =============================================================================
# STATUS PALETTES & TEXT BADGES (Spec §11, Decision Table v1.3.4)
# =============================================================================

STYLE_CROP_READY: Final[PreviewVisualStyle] = PreviewVisualStyle(
    status_name="CROP_READY",
    badge_text="[READY] CROP_READY",
    accessibility_label="Status: Ready for automatic cropping. Formulas verified.",
    stroke_color="#10B981",          # Emerald Green
    fill_color="rgba(16, 185, 129, 0.12)",
    stroke_width=2.0,
    stroke_dasharray="none",
    pattern_type="solid",
)

STYLE_MANUAL_REVIEW_REQUIRED: Final[PreviewVisualStyle] = PreviewVisualStyle(
    status_name="MANUAL_REVIEW_REQUIRED",
    badge_text="[HOLD] MANUAL_REVIEW_REQUIRED",
    accessibility_label="Status: Hold for manual admin review. Auto-crop strictly disabled.",
    stroke_color="#F59E0B",          # Amber / Orange
    fill_color="rgba(245, 158, 11, 0.15)",
    stroke_width=2.5,
    stroke_dasharray="8,4",
    pattern_type="dashed",
)

STYLE_UNKNOWN_LAYOUT: Final[PreviewVisualStyle] = PreviewVisualStyle(
    status_name="UNKNOWN_LAYOUT",
    badge_text="[UNKNOWN] UNKNOWN_LAYOUT",
    accessibility_label="Status: Layout unrecognized. No crop strategy available.",
    stroke_color="#6B7280",          # Slate Gray
    fill_color="rgba(107, 114, 128, 0.10)",
    stroke_width=2.0,
    stroke_dasharray="3,3",
    pattern_type="dotted",
)

STYLE_REJECTED: Final[PreviewVisualStyle] = PreviewVisualStyle(
    status_name="REJECTED",
    badge_text="[REJECTED] REJECTED_UNKNOWN_LAYOUT",
    accessibility_label="Status: Document rejected due to unknown layout or security violation.",
    stroke_color="#EF4444",          # Crimson Red
    fill_color="rgba(239, 68, 68, 0.18)",
    stroke_width=3.0,
    stroke_dasharray="10,4,2,4",
    pattern_type="dash-dot",
)


# =============================================================================
# STRUCTURAL OVERLAY GUIDELINE STYLES
# =============================================================================

STYLE_MIDPOINT_CUT: Final[PreviewVisualStyle] = PreviewVisualStyle(
    status_name="MIDPOINT_CUT_LINE",
    badge_text="[CUT] MIDPOINT CUT LINE",
    accessibility_label="Midpoint interior cut dividing line (0.00 pt margin flush cut)",
    stroke_color="#2563EB",          # Royal Blue
    fill_color="none",
    stroke_width=1.5,
    stroke_dasharray="5,3",
    pattern_type="dashed",
)

STYLE_OUTER_TRIM: Final[PreviewVisualStyle] = PreviewVisualStyle(
    status_name="OUTER_TRIM_BOUNDARY",
    badge_text="[TRIM] OUTER TRIM MARGIN",
    accessibility_label="Outer sheet trim margin boundary (13.85 pt horizontal / 14.50 pt vertical)",
    stroke_color="#8B5CF6",          # Violet
    fill_color="rgba(139, 92, 246, 0.05)",
    stroke_width=1.0,
    stroke_dasharray="3,3",
    pattern_type="dotted",
)

STYLE_SPINE_EXCLUSION: Final[PreviewVisualStyle] = PreviewVisualStyle(
    status_name="SPINE_EXCLUSION_ZONE",
    badge_text="[SPINE] EXCLUSION ZONE (15.02 mm)",
    accessibility_label="Protected central spine exclusion zone (15.02 mm / 42.57 pt). No crop region may enter.",
    stroke_color="#DC2626",          # Red
    fill_color="rgba(220, 38, 38, 0.20)",
    stroke_width=2.0,
    stroke_dasharray="4,2",
    pattern_type="dashed-hatch",
)


def get_status_style(status: CropReadinessStatus | str) -> PreviewVisualStyle:
    """Return the visual style and accessible badges for a given readiness or document status."""
    raw = status.value if isinstance(status, CropReadinessStatus) else str(status)
    raw = raw.upper()

    if raw in ("CROP_READY", "AUTO_READY_FOR_PREVIEW"):
        return STYLE_CROP_READY
    elif raw in ("MANUAL_REVIEW_REQUIRED", "HOLD"):
        return STYLE_MANUAL_REVIEW_REQUIRED
    elif raw in ("REJECTED_UNKNOWN_LAYOUT", "REJECTED"):
        return STYLE_REJECTED
    elif raw in ("UNKNOWN_LAYOUT", "NOT_APPLICABLE"):
        return STYLE_UNKNOWN_LAYOUT
    else:
        return STYLE_UNKNOWN_LAYOUT

