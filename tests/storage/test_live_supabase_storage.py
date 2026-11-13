"""Live integration tests for Supabase Storage (CRUD, public URL direct browser fetch, ZIP)."""

from __future__ import annotations

import httpx
import pytest

from app.api.config import get_settings
from app.storage.base import normalize_object_key
from app.storage.factory import create_storage_adapter
from app.storage.supabase import SupabaseStorageAdapter


@pytest.fixture
def live_supabase_adapter() -> SupabaseStorageAdapter:
    settings = get_settings()
    if not (settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY):
        pytest.skip("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are not configured in root .env")
    return SupabaseStorageAdapter(
        supabase_url=settings.SUPABASE_URL,
        service_role_key=settings.SUPABASE_SERVICE_ROLE_KEY,
        bucket_name=settings.SUPABASE_STORAGE_BUCKET or "bookabook-images",
    )


def test_live_supabase_storage_crud_and_public_browser_access(
    live_supabase_adapter: SupabaseStorageAdapter,
) -> None:
    adapter = live_supabase_adapter
    test_key = "books/live_test_harness/PAGE-01.jpg"
    test_content = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00test_live_supabase_jpg_bytes"

    # 1. Put (Upload)
    stored_key = adapter.put_bytes(test_key, test_content, content_type="image/jpeg")
    assert stored_key == test_key

    try:
        # 2. Exists
        assert adapter.exists(test_key) is True

        # 3. Read via adapter (Backend server-side read for ZIP creation)
        retrieved = adapter.get_bytes(test_key)
        assert retrieved == test_content

        # 4. Public URL direct browser access (WITHOUT any auth headers or api keys)
        public_url = adapter.get_public_or_signed_url(test_key)
        assert public_url is not None
        assert "storage/v1/object/public" in public_url
        assert adapter.service_role_key not in public_url

        with httpx.Client(timeout=30.0) as browser_client:
            # Emulate pure unauthenticated browser GET request
            res = browser_client.get(public_url)
            assert res.status_code == 200, (
                f"Public URL '{public_url}' returned HTTP {res.status_code}. "
                f"Ensure bucket '{adapter.bucket_name}' is set to Public."
            )
            assert res.content == test_content
            assert "image/jpeg" in res.headers.get("content-type", "")

    finally:
        # 5. Delete (Clean up)
        deleted = adapter.delete(test_key)
        assert deleted is True
        assert adapter.exists(test_key) is False

