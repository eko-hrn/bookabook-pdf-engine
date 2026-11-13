"""Adaptive 300 DPI RGB JPEG compression engine with per-category size caps and quality protection."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
from typing import Iterable, Optional

from PIL import Image, ImageFile

# Ensure libjpeg has ample buffer when writing high-entropy 300 DPI progressive JPEGs
ImageFile.MAXBLOCK = max(getattr(ImageFile, "MAXBLOCK", 65536), 16 * 1024 * 1024)

from app.crop.exporter.models import (
    CompressionFailureDetail,
    CompressionStatus,
    CompressionTier,
    PageKind,
)

# Binary size limits per book category (FINAL JPEG SIZE POLICY)
COVER_MAX_BYTES = 400 * 1024            # 409,600 bytes (400 KB)
INSIDE_PAGE_MAX_BYTES = 400 * 1024      # 409,600 bytes (400 KB)
BACKCOVER_MAX_BYTES = 1024 * 1024       # 1,048,576 bytes (1 MB)

TARGET_MIN_BYTES = 300 * 1024           # 307,200 bytes (300 KB)
TARGET_MAX_BYTES = COVER_MAX_BYTES      # 409,600 bytes
COMPLEX_MIN_BYTES = COVER_MAX_BYTES     # 409,600 bytes
HARD_MAX_BYTES = BACKCOVER_MAX_BYTES    # 1,048,576 bytes

INITIAL_HIGH_QUALITY = 95
DEFAULT_MIN_QUALITY_COVER = 40
DEFAULT_MIN_QUALITY_INSIDE = 40
DEFAULT_MIN_QUALITY_BACKCOVER = 65

_SUBSAMPLING_LABELS = {
    0: "4:4:4",
    1: "4:2:2",
    2: "4:2:0",
}


@dataclass(frozen=True)
class CompressionProfile:
    """Category-specific JPEG compression policy."""

    page_kind: PageKind
    max_bytes: int
    initial_quality: int = INITIAL_HIGH_QUALITY
    min_quality: int = DEFAULT_MIN_QUALITY_INSIDE
    high_chroma_floor_444: int = 82
    mid_chroma_floor_422: int = 74


class CompressionLimitExceededError(ValueError):
    """Raised when an image exceeds its byte limit even at the minimum JPEG quality threshold."""

    def __init__(self, failure: CompressionFailureDetail) -> None:
        super().__init__(failure.reason)
        self.failure = failure


@dataclass
class CompressedImageCandidate:
    """Compressed 300 DPI JPEG result for one cropped book page."""

    page_key: str
    page_kind: PageKind
    image: Image.Image
    dpi: int
    jpeg_bytes: bytes
    quality_used: int
    subsampling_int: int
    baseline_complex_score: int
    max_allowed_bytes: int = COVER_MAX_BYTES
    min_quality_threshold: int = DEFAULT_MIN_QUALITY_INSIDE
    compression_status: CompressionStatus = CompressionStatus.PASSED

    @property
    def file_size_bytes(self) -> int:
        return len(self.jpeg_bytes)

    @property
    def subsampling_label(self) -> str:
        return _SUBSAMPLING_LABELS.get(self.subsampling_int, "4:2:0")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.jpeg_bytes).hexdigest()

    @property
    def compression_tier(self) -> CompressionTier:
        size = self.file_size_bytes
        if size > COVER_MAX_BYTES:
            return CompressionTier.BACKCOVER_WITHIN_1MB
        if size >= TARGET_MIN_BYTES:
            return CompressionTier.WITHIN_400KB_LIMIT
        return CompressionTier.COMPACT_HIGH_QUALITY


def get_compression_profile(
    page_kind: PageKind,
    *,
    max_bytes: Optional[int] = None,
    min_quality: Optional[int] = None,
    initial_quality: int = INITIAL_HIGH_QUALITY,
) -> CompressionProfile:
    """Build the compression profile for COVER, INSIDE PAGES (CONTENT), or BACKCOVER."""
    init_q = max(1, min(95, int(initial_quality)))

    if page_kind == PageKind.BACKCOVER:
        resolved_max = max_bytes if max_bytes is not None else BACKCOVER_MAX_BYTES
        resolved_min = min_quality if min_quality is not None else DEFAULT_MIN_QUALITY_BACKCOVER
        resolved_min = max(1, min(init_q, int(resolved_min)))
        return CompressionProfile(
            page_kind=page_kind,
            max_bytes=int(resolved_max),
            initial_quality=init_q,
            min_quality=resolved_min,
            high_chroma_floor_444=max(80, resolved_min),
            mid_chroma_floor_422=max(74, resolved_min),
        )

    default_min = (
        DEFAULT_MIN_QUALITY_COVER if page_kind == PageKind.COVER else DEFAULT_MIN_QUALITY_INSIDE
    )
    resolved_max = max_bytes if max_bytes is not None else COVER_MAX_BYTES
    resolved_min = min_quality if min_quality is not None else default_min
    resolved_min = max(1, min(init_q, int(resolved_min)))
    return CompressionProfile(
        page_kind=page_kind,
        max_bytes=int(resolved_max),
        initial_quality=init_q,
        min_quality=resolved_min,
        high_chroma_floor_444=max(82, resolved_min),
        mid_chroma_floor_422=max(74, resolved_min),
    )


def encode_jpeg_rgb(
    image: Image.Image,
    quality: int,
    subsampling: int,
    dpi: int = 300,
) -> bytes:
    """Encode an RGB PIL Image into progressive/optimized JPEG preserving exact dimensions."""
    rgb_image = _ensure_rgb(image)
    buf = io.BytesIO()
    try:
        rgb_image.save(
            buf,
            format="JPEG",
            quality=int(quality),
            optimize=True,
            progressive=True,
            subsampling=int(subsampling),
            dpi=(int(dpi), int(dpi)),
        )
    except OSError:
        # Fallback to baseline optimized JPEG if libjpeg progressive scan suspends on dense entropy
        buf = io.BytesIO()
        rgb_image.save(
            buf,
            format="JPEG",
            quality=int(quality),
            optimize=True,
            progressive=False,
            subsampling=int(subsampling),
            dpi=(int(dpi), int(dpi)),
        )
    return buf.getvalue()


def _ensure_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[3])
        return background
    return image.convert("RGB")


def verify_compressed_jpeg(
    jpeg_bytes: bytes,
    *,
    expected_width: int,
    expected_height: int,
    expected_dpi: int,
    max_bytes: int,
    filename: str,
) -> None:
    """Reopen and validate the compressed JPEG stream, dimensions, RGB mode, 300 DPI, and size cap."""
    actual_size = len(jpeg_bytes)
    if actual_size <= 0 or actual_size > max_bytes:
        raise ValueError(
            f"{filename}: Final JPEG size {actual_size:,} bytes violates max limit {max_bytes:,} bytes."
        )

    with Image.open(io.BytesIO(jpeg_bytes)) as reopened:
        if reopened.format != "JPEG":
            raise ValueError(f"{filename}: Expected JPEG format after encoding, got {reopened.format}.")
        if reopened.mode != "RGB":
            raise ValueError(f"{filename}: Expected RGB color mode, got {reopened.mode}.")
        if reopened.size != (expected_width, expected_height):
            raise ValueError(
                f"{filename}: Expected dimensions {(expected_width, expected_height)}, got {reopened.size}."
            )
        dpi_info = reopened.info.get("dpi")
        if dpi_info != (expected_dpi, expected_dpi):
            raise ValueError(
                f"{filename}: Expected DPI {(expected_dpi, expected_dpi)}, got {dpi_info}."
            )
        # Decode full scanlines to confirm readability with no truncated stream
        reopened.load()


def _binary_search_quality_under_limit(
    image: Image.Image,
    max_bytes: int,
    subsampling: int,
    min_quality: int,
    max_quality: int,
    dpi: int,
) -> tuple[bytes, int] | None:
    """Find highest JPEG quality in [min_quality, max_quality] such that len(bytes) <= max_bytes."""
    if min_quality > max_quality:
        return None

    # Test min_quality first: if even min_quality exceeds max_bytes, the entire range fails in 1 encode!
    low_bytes = encode_jpeg_rgb(image, min_quality, subsampling, dpi=dpi)
    if len(low_bytes) > max_bytes:
        return None

    if min_quality == max_quality:
        return low_bytes, min_quality

    high_bytes = encode_jpeg_rgb(image, max_quality, subsampling, dpi=dpi)
    if len(high_bytes) <= max_bytes:
        return high_bytes, max_quality

    best_bytes = low_bytes
    best_quality = min_quality
    lo = min_quality + 1
    hi = max_quality - 1

    while lo <= hi:
        mid = (lo + hi) // 2
        payload = encode_jpeg_rgb(image, mid, subsampling, dpi=dpi)
        if len(payload) <= max_bytes:
            best_bytes = payload
            best_quality = mid
            lo = mid + 1
        else:
            hi = mid - 1

    return best_bytes, best_quality


def compress_single_page(
    page_key: str,
    page_kind: PageKind,
    image: Image.Image,
    dpi: int = 300,
    prefer_target_max_bytes: Optional[int] = None,
    *,
    filename: Optional[str] = None,
    max_bytes: Optional[int] = None,
    min_quality: Optional[int] = None,
    initial_quality: int = INITIAL_HIGH_QUALITY,
) -> CompressedImageCandidate:
    """Compress one page using its category profile without changing resolution or aspect ratio.

    Raises CompressionLimitExceededError if the image still exceeds max_bytes at min_quality.
    """
    resolved_max_override = max_bytes if max_bytes is not None else prefer_target_max_bytes
    profile = get_compression_profile(
        page_kind,
        max_bytes=resolved_max_override,
        min_quality=min_quality,
        initial_quality=initial_quality,
    )
    resolved_filename = filename or f"{page_key}.jpg"
    rgb_image = _ensure_rgb(image)

    # Measure initial high-quality JPEG at 4:4:4 first
    initial_444 = encode_jpeg_rgb(
        rgb_image, quality=profile.initial_quality, subsampling=0, dpi=dpi
    )
    baseline_score = len(initial_444)

    selected_payload: Optional[bytes] = None
    selected_quality = profile.initial_quality
    selected_subsampling = 0

    if len(initial_444) <= profile.max_bytes:
        selected_payload = initial_444
        selected_quality = profile.initial_quality
        selected_subsampling = 0
    else:
        # Step 1: Try 4:4:4 adaptive reduction down to profile high chroma floor
        # If baseline is > 1.65x the budget, 4:4:4 at q=82 cannot fit
        if baseline_score <= int(profile.max_bytes * 1.65):
            found_444 = _binary_search_quality_under_limit(
                rgb_image,
                max_bytes=profile.max_bytes,
                subsampling=0,
                min_quality=min(profile.high_chroma_floor_444, profile.initial_quality),
                max_quality=profile.initial_quality - 1,
                dpi=dpi,
            )
            if found_444 is not None:
                selected_payload, selected_quality = found_444
                selected_subsampling = 0

        # Step 2: Try 4:2:2 down to mid chroma floor (preserves sharper text/line-art edges than 4:2:0)
        # If baseline is > 2.35x the budget, 4:2:2 at q=74 cannot fit
        if selected_payload is None and baseline_score <= int(profile.max_bytes * 2.35):
            found_422 = _binary_search_quality_under_limit(
                rgb_image,
                max_bytes=profile.max_bytes,
                subsampling=1,
                min_quality=min(profile.mid_chroma_floor_422, profile.initial_quality),
                max_quality=profile.initial_quality,
                dpi=dpi,
            )
            if found_422 is not None:
                selected_payload, selected_quality = found_422
                selected_subsampling = 1

        # Step 3: Adaptive 4:2:0 down to configurable min_quality threshold
        if selected_payload is None:
            found_420 = _binary_search_quality_under_limit(
                rgb_image,
                max_bytes=profile.max_bytes,
                subsampling=2,
                min_quality=profile.min_quality,
                max_quality=profile.initial_quality,
                dpi=dpi,
            )
            if found_420 is not None:
                selected_payload, selected_quality = found_420
                selected_subsampling = 2

    if selected_payload is None:
        # Do NOT accept oversized file and do NOT reduce resolution below min_quality
        min_attempt_bytes = len(
            encode_jpeg_rgb(rgb_image, quality=profile.min_quality, subsampling=2, dpi=dpi)
        )
        reason = (
            f"{resolved_filename} compressed to {min_attempt_bytes:,} bytes at minimum quality "
            f"q={profile.min_quality} (4:2:0), which still exceeds the {profile.page_kind.value} "
            f"limit of {profile.max_bytes:,} bytes without downscaling resolution."
        )
        raise CompressionLimitExceededError(
            CompressionFailureDetail(
                filename=resolved_filename,
                page_key=page_key,
                page_kind=profile.page_kind,
                actual_size_bytes=min_attempt_bytes,
                max_allowed_bytes=profile.max_bytes,
                min_quality_threshold=profile.min_quality,
                quality_attempted=profile.min_quality,
                reason=reason,
            )
        )

    # Step 7: Reopen and validate the final JPEG stream before returning
    verify_compressed_jpeg(
        selected_payload,
        expected_width=rgb_image.width,
        expected_height=rgb_image.height,
        expected_dpi=dpi,
        max_bytes=profile.max_bytes,
        filename=resolved_filename,
    )

    return CompressedImageCandidate(
        page_key=page_key,
        page_kind=profile.page_kind,
        image=rgb_image,
        dpi=dpi,
        jpeg_bytes=selected_payload,
        quality_used=selected_quality,
        subsampling_int=selected_subsampling,
        baseline_complex_score=baseline_score,
        max_allowed_bytes=profile.max_bytes,
        min_quality_threshold=profile.min_quality,
        compression_status=CompressionStatus.PASSED,
    )


def enforce_book_compression_budget(
    candidates: Iterable[CompressedImageCandidate],
) -> tuple[list[CompressedImageCandidate], list[str]]:
    """Validate that every image in a book satisfies its strict category byte limit."""
    items = list(candidates)
    warnings: list[str] = []

    for idx, item in enumerate(items):
        limit = item.max_allowed_bytes
        if item.file_size_bytes > limit:
            recompressed = compress_single_page(
                page_key=item.page_key,
                page_kind=item.page_kind,
                image=item.image,
                dpi=item.dpi,
                filename=f"{item.page_key}.jpg",
                max_bytes=limit,
                min_quality=item.min_quality_threshold,
            )
            items[idx] = recompressed

    return items, warnings
