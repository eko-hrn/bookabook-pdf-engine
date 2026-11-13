"""Bookabook object storage adapters (Local dev, Supabase Storage, and Cloudflare R2)."""

from app.storage.base import StorageAdapter, normalize_object_key
from app.storage.factory import create_storage_adapter
from app.storage.local import LocalStorageAdapter
from app.storage.r2 import CloudflareR2StorageAdapter
from app.storage.supabase import SupabaseStorageAdapter

__all__ = [
    "CloudflareR2StorageAdapter",
    "LocalStorageAdapter",
    "StorageAdapter",
    "SupabaseStorageAdapter",
    "create_storage_adapter",
    "normalize_object_key",
]
