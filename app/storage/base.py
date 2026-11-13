"""Storage adapter interface for Bookabook JPG object storage."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


def normalize_object_key(object_key: str) -> str:
    """Validate and normalize an object key, preventing path traversal."""
    cleaned = object_key.replace("\\", "/").strip().lstrip("/")
    if not cleaned:
        raise ValueError("Object key cannot be empty.")
    parts = [part for part in cleaned.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise ValueError(f"Invalid object key contains path traversal: '{object_key}'")
    return "/".join(parts)


class StorageAdapter(ABC):
    """Abstract binary object store for book JPGs (Local dev or Cloudflare R2)."""

    backend_name: str = "abstract"

    @abstractmethod
    def put_bytes(
        self,
        object_key: str,
        data: bytes,
        content_type: str = "image/jpeg",
    ) -> str:
        """Persist raw bytes under object_key and return normalized object_key."""

    @abstractmethod
    def get_bytes(self, object_key: str) -> bytes:
        """Retrieve stored raw bytes for object_key, raising FileNotFoundError if absent."""

    @abstractmethod
    def exists(self, object_key: str) -> bool:
        """Return True if object_key exists in storage."""

    @abstractmethod
    def delete(self, object_key: str) -> bool:
        """Delete object_key if present; return True if deleted."""

    @abstractmethod
    def get_public_or_signed_url(
        self,
        object_key: str,
        expires_in: int = 3600,
    ) -> Optional[str]:
        """Return external URL if configured (e.g. R2 CDN/presigned) or None for API proxy."""

