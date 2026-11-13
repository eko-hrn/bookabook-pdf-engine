"""Cloudflare R2 (S3-compatible) storage adapter ready for production."""

from __future__ import annotations

from typing import Any, Optional

from app.storage.base import StorageAdapter, normalize_object_key


class CloudflareR2StorageAdapter(StorageAdapter):
    """Stores exported JPG artifacts in Cloudflare R2 via S3-compatible boto3 API."""

    backend_name = "r2"

    def __init__(
        self,
        *,
        bucket_name: str,
        endpoint_url: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        public_base_url: Optional[str] = None,
        region_name: str = "auto",
        s3_client: Optional[Any] = None,
    ) -> None:
        if not bucket_name or not bucket_name.strip():
            raise ValueError("R2 bucket_name is required.")
        self.bucket_name = bucket_name.strip()
        self.public_base_url = (
            public_base_url.rstrip("/") if public_base_url and public_base_url.strip() else None
        )

        if s3_client is not None:
            self.client = s3_client
        else:
            if not (endpoint_url and access_key_id and secret_access_key):
                raise ValueError(
                    "R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, and R2_SECRET_ACCESS_KEY are required when STORAGE_BACKEND=r2."
                )
            try:
                import boto3
                from botocore.config import Config
            except ImportError as exc:
                raise RuntimeError(
                    "boto3 is required for Cloudflare R2 storage backend. Install via requirements.txt."
                ) from exc

            self.client = boto3.client(
                "s3",
                endpoint_url=endpoint_url.strip(),
                aws_access_key_id=access_key_id.strip(),
                aws_secret_access_key=secret_access_key.strip(),
                region_name=region_name,
                config=Config(signature_version="s3v4"),
            )

    def put_bytes(
        self,
        object_key: str,
        data: bytes,
        content_type: str = "image/jpeg",
    ) -> str:
        norm = normalize_object_key(object_key)
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=norm,
            Body=data,
            ContentType=content_type,
        )
        return norm

    def get_bytes(self, object_key: str) -> bytes:
        norm = normalize_object_key(object_key)
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=norm)
        except Exception as exc:
            err_code = getattr(getattr(exc, "response", None), "get", lambda *_: None)("Error")
            if isinstance(err_code, dict) and err_code.get("Code") in ("NoSuchKey", "404"):
                raise FileNotFoundError(f"Object not found in R2: '{norm}'") from exc
            if isinstance(exc, FileNotFoundError):
                raise
            raise FileNotFoundError(f"Failed retrieving object '{norm}' from R2: {exc}") from exc

        body = response["Body"]
        return body.read() if hasattr(body, "read") else bytes(body)

    def exists(self, object_key: str) -> bool:
        norm = normalize_object_key(object_key)
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=norm)
            return True
        except Exception:
            return False

    def delete(self, object_key: str) -> bool:
        norm = normalize_object_key(object_key)
        existed = self.exists(norm)
        self.client.delete_object(Bucket=self.bucket_name, Key=norm)
        return existed

    def get_public_or_signed_url(
        self,
        object_key: str,
        expires_in: int = 3600,
    ) -> Optional[str]:
        norm = normalize_object_key(object_key)
        if self.public_base_url:
            return f"{self.public_base_url}/{norm}"
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": norm},
                ExpiresIn=expires_in,
            )
        except Exception:
            return None

