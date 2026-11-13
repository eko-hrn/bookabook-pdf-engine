"""Factory for selecting object storage adapter (Local dev, Supabase Storage, or Cloudflare R2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.storage.base import StorageAdapter
from app.storage.local import LocalStorageAdapter
from app.storage.r2 import CloudflareR2StorageAdapter
from app.storage.supabase import SupabaseStorageAdapter

if TYPE_CHECKING:
    from app.api.config import Settings


def create_storage_adapter(settings: "Settings") -> StorageAdapter:
    """Instantiate configured StorageAdapter based on STORAGE_BACKEND setting."""
    backend = (settings.STORAGE_BACKEND or "local").strip().lower()
    if backend == "local":
        return LocalStorageAdapter(settings.LOCAL_STORAGE_DIR)
    if backend in ("supabase", "supabase_storage"):
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required when STORAGE_BACKEND=supabase."
            )
        return SupabaseStorageAdapter(
            supabase_url=settings.SUPABASE_URL,
            service_role_key=settings.SUPABASE_SERVICE_ROLE_KEY,
            bucket_name=settings.SUPABASE_STORAGE_BUCKET or "bookabook-images",
        )
    if backend in ("r2", "cloudflare_r2"):
        return CloudflareR2StorageAdapter(
            bucket_name=settings.R2_BUCKET_NAME or "",
            endpoint_url=settings.R2_ENDPOINT_URL,
            access_key_id=settings.R2_ACCESS_KEY_ID,
            secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            public_base_url=settings.R2_PUBLIC_BASE_URL,
        )
    raise ValueError(f"Unsupported STORAGE_BACKEND: '{settings.STORAGE_BACKEND}'")
