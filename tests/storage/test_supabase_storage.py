"""Unit tests for SupabaseStorageAdapter and storage factory integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from app.api.config import Settings
from app.storage.base import normalize_object_key
from app.storage.factory import create_storage_adapter
from app.storage.supabase import SupabaseStorageAdapter


@pytest.fixture
def mock_supabase_adapter() -> tuple[SupabaseStorageAdapter, MagicMock]:
    mock_client = MagicMock()
    # Mock ensure_bucket_exists get returning 200
    mock_client.get.return_value.status_code = 200
    adapter = SupabaseStorageAdapter(
        supabase_url="https://mockref.supabase.co",
        service_role_key="mock-service-role-key-secret",
        bucket_name="bookabook-images",
        client=mock_client,
        auto_create_bucket=False,
    )
    return adapter, mock_client


def test_supabase_adapter_initialization_validation() -> None:
    with pytest.raises(ValueError, match="SUPABASE_URL is required"):
        SupabaseStorageAdapter(supabase_url="", service_role_key="secret")

    with pytest.raises(ValueError, match="SUPABASE_SERVICE_ROLE_KEY is required"):
        SupabaseStorageAdapter(supabase_url="https://example.supabase.co", service_role_key="")

    with pytest.raises(ValueError, match="SUPABASE_STORAGE_BUCKET is required"):
        SupabaseStorageAdapter(
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
            bucket_name="",
        )


def test_supabase_public_url_generation_never_exposes_service_key(
    mock_supabase_adapter: tuple[SupabaseStorageAdapter, MagicMock],
) -> None:
    adapter, _ = mock_supabase_adapter
    object_key = "books/book_a1b2c3d4/COVER.jpg"
    public_url = adapter.get_public_or_signed_url(object_key)

    expected = "https://mockref.supabase.co/storage/v1/object/public/bookabook-images/books/book_a1b2c3d4/COVER.jpg"
    assert public_url == expected
    assert "mock-service-role-key-secret" not in public_url
    assert "Bearer" not in public_url
    assert "apikey" not in public_url


def test_supabase_put_bytes_sends_correct_headers_and_payload(
    mock_supabase_adapter: tuple[SupabaseStorageAdapter, MagicMock],
) -> None:
    adapter, mock_client = mock_supabase_adapter
    mock_resp = MagicMock(status_code=200, text="OK")
    mock_client.post.return_value = mock_resp

    test_data = b"\xff\xd8\xff\xe0testjpegdata"
    stored_key = adapter.put_bytes("books/book_1/PAGE-01.jpg", test_data, content_type="image/jpeg")

    assert stored_key == "books/book_1/PAGE-01.jpg"
    assert mock_client.post.call_count == 1
    call_args, call_kwargs = mock_client.post.call_args
    assert call_args[0] == "https://mockref.supabase.co/storage/v1/object/bookabook-images/books/book_1/PAGE-01.jpg"
    assert call_kwargs["content"] == test_data
    assert call_kwargs["headers"]["Authorization"] == "Bearer mock-service-role-key-secret"
    assert call_kwargs["headers"]["apikey"] == "mock-service-role-key-secret"
    assert call_kwargs["headers"]["Content-Type"] == "image/jpeg"
    assert call_kwargs["headers"]["x-upsert"] == "true"


def test_supabase_put_bytes_raises_on_failure(
    mock_supabase_adapter: tuple[SupabaseStorageAdapter, MagicMock],
) -> None:
    adapter, mock_client = mock_supabase_adapter
    mock_client.post.return_value = MagicMock(status_code=500, text="Internal Server Error")

    with pytest.raises(RuntimeError, match="Failed to upload 'books/book_1/PAGE-01.jpg'"):
        adapter.put_bytes("books/book_1/PAGE-01.jpg", b"bad_data")


def test_supabase_get_bytes_success_and_404(
    mock_supabase_adapter: tuple[SupabaseStorageAdapter, MagicMock],
) -> None:
    adapter, mock_client = mock_supabase_adapter

    # 1. Success
    mock_client.get.return_value = MagicMock(status_code=200, content=b"retrieved_bytes")
    data = adapter.get_bytes("books/book_1/COVER.jpg")
    assert data == b"retrieved_bytes"

    # 2. 404 Not Found
    mock_client.get.return_value = MagicMock(status_code=404, text="Not found")
    with pytest.raises(FileNotFoundError, match="Object 'books/book_1/MISSING.jpg' not found"):
        adapter.get_bytes("books/book_1/MISSING.jpg")


def test_supabase_exists(
    mock_supabase_adapter: tuple[SupabaseStorageAdapter, MagicMock],
) -> None:
    adapter, mock_client = mock_supabase_adapter

    mock_client.head.return_value = MagicMock(status_code=200)
    assert adapter.exists("books/book_1/COVER.jpg") is True

    mock_client.head.return_value = MagicMock(status_code=404)
    assert adapter.exists("books/book_1/MISSING.jpg") is False


def test_supabase_delete(
    mock_supabase_adapter: tuple[SupabaseStorageAdapter, MagicMock],
) -> None:
    adapter, mock_client = mock_supabase_adapter

    mock_client.delete.return_value = MagicMock(status_code=200)
    assert adapter.delete("books/book_1/COVER.jpg") is True


def test_supabase_ensure_bucket_exists_creates_public_bucket(
    mock_supabase_adapter: tuple[SupabaseStorageAdapter, MagicMock],
) -> None:
    adapter, mock_client = mock_supabase_adapter
    # Simulate bucket missing (404) then create succeeds (201)
    mock_client.get.return_value = MagicMock(status_code=404)
    mock_client.post.return_value = MagicMock(status_code=201, text="Created")

    adapter.ensure_bucket_exists()

    assert mock_client.get.call_count == 1
    assert mock_client.post.call_count == 1
    create_args, create_kwargs = mock_client.post.call_args
    assert create_args[0] == "https://mockref.supabase.co/storage/v1/bucket"
    assert create_kwargs["json"]["id"] == "bookabook-images"
    assert create_kwargs["json"]["public"] is True


def test_create_storage_adapter_factory() -> None:
    # 1. Local
    local_settings = Settings(STORAGE_BACKEND="local", DATABASE_URL=None)
    local_adapter = create_storage_adapter(local_settings)
    assert local_adapter.backend_name == "local"

    # 2. Supabase
    with patch.object(SupabaseStorageAdapter, "ensure_bucket_exists"):
        supabase_settings = Settings(
            STORAGE_BACKEND="supabase",
            SUPABASE_URL="https://testref.supabase.co",
            SUPABASE_SERVICE_ROLE_KEY="secret-key",
            SUPABASE_STORAGE_BUCKET="bookabook-images",
            DATABASE_URL=None,
        )
        sb_adapter = create_storage_adapter(supabase_settings)
        assert sb_adapter.backend_name == "supabase"
        assert sb_adapter.bucket_name == "bookabook-images"

    # 3. Missing Supabase credentials raises ValueError
    bad_sb_settings = Settings(
        STORAGE_BACKEND="supabase",
        SUPABASE_URL=None,
        SUPABASE_SERVICE_ROLE_KEY=None,
        DATABASE_URL=None,
    )
    with pytest.raises(ValueError, match="SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required"):
        create_storage_adapter(bad_sb_settings)

