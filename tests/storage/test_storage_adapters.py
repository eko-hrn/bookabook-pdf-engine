"""Unit tests for Local and Cloudflare R2 StorageAdapter implementations."""

from __future__ import annotations

import io
from pathlib import Path
import pytest

from app.storage.base import normalize_object_key
from app.storage.local import LocalStorageAdapter
from app.storage.r2 import CloudflareR2StorageAdapter


class FakeR2Client:
    """In-memory mock mimicking boto3 S3 client interface for Cloudflare R2."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict] = {}

    def put_object(self, Bucket: str, Key: str, Body: bytes, ContentType: str) -> None:
        self.objects[(Bucket, Key)] = {"Body": Body, "ContentType": ContentType}

    def get_object(self, Bucket: str, Key: str) -> dict:
        if (Bucket, Key) not in self.objects:
            raise FileNotFoundError("NoSuchKey")
        item = self.objects[(Bucket, Key)]
        return {
            "Body": io.BytesIO(item["Body"]),
            "ContentType": item["ContentType"],
        }

    def head_object(self, Bucket: str, Key: str) -> dict:
        if (Bucket, Key) not in self.objects:
            raise FileNotFoundError("NoSuchKey")
        return {"ContentLength": len(self.objects[(Bucket, Key)]["Body"])}

    def delete_object(self, Bucket: str, Key: str) -> dict:
        self.objects.pop((Bucket, Key), None)
        return {}

    def generate_presigned_url(
        self,
        ClientMethod: str,
        Params: dict,
        ExpiresIn: int = 3600,
    ) -> str:
        return f"https://signed.r2.example/{Params['Bucket']}/{Params['Key']}?exp={ExpiresIn}"


def test_normalize_object_key_rejects_traversal() -> None:
    assert normalize_object_key("/books/b1/COVER.jpg") == "books/b1/COVER.jpg"
    assert normalize_object_key("books\\b1\\PAGE-01.jpg") == "books/b1/PAGE-01.jpg"
    with pytest.raises(ValueError, match="traversal"):
        normalize_object_key("../secret.txt")
    with pytest.raises(ValueError, match="empty"):
        normalize_object_key("   ")


def test_local_storage_adapter_roundtrip(tmp_path: Path) -> None:
    adapter = LocalStorageAdapter(tmp_path)
    key = adapter.put_bytes("books/book_1/COVER.jpg", b"jpeg-cover-bytes", "image/jpeg")
    assert key == "books/book_1/COVER.jpg"
    assert adapter.exists(key) is True
    assert adapter.get_bytes(key) == b"jpeg-cover-bytes"
    assert adapter.get_public_or_signed_url(key) is None

    assert adapter.delete(key) is True
    assert adapter.exists(key) is False
    assert adapter.delete(key) is False

    with pytest.raises(FileNotFoundError):
        adapter.get_bytes(key)


def test_cloudflare_r2_storage_adapter_roundtrip() -> None:
    fake_client = FakeR2Client()
    adapter = CloudflareR2StorageAdapter(
        bucket_name="bookabook-prod",
        public_base_url="https://cdn.bookabook.id/",
        s3_client=fake_client,
    )

    key = adapter.put_bytes("books/book_2/PAGE-01.jpg", b"r2-page-bytes", "image/jpeg")
    assert key == "books/book_2/PAGE-01.jpg"
    assert adapter.exists(key) is True
    assert adapter.get_bytes(key) == b"r2-page-bytes"
    assert adapter.get_public_or_signed_url(key) == "https://cdn.bookabook.id/books/book_2/PAGE-01.jpg"

    # Without public_base_url falls back to presigned URL
    adapter_signed = CloudflareR2StorageAdapter(
        bucket_name="bookabook-prod",
        s3_client=fake_client,
    )
    assert "signed.r2.example/bookabook-prod/books/book_2/PAGE-01.jpg" in (
        adapter_signed.get_public_or_signed_url(key, expires_in=900) or ""
    )

    assert adapter.delete(key) is True
    assert adapter.exists(key) is False
    with pytest.raises(FileNotFoundError):
        adapter.get_bytes(key)

