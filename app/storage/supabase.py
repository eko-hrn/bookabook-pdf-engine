"""Supabase Storage adapter for Bookabook image storage."""

from __future__ import annotations

import logging
from typing import Optional
import urllib.parse

import httpx

from app.storage.base import StorageAdapter, normalize_object_key

logger = logging.getLogger(__name__)


class SupabaseStorageAdapter(StorageAdapter):
    """Stores exported JPG artifacts in Supabase Storage using the Service Role Key.

    - Uploads/updates/deletes are authenticated via the Supabase Service Role Key.
    - Public URLs are generated directly pointing to Supabase Storage public CDN
      (`{SUPABASE_URL}/storage/v1/object/public/{bucket}/{object_key}`).
    - The Service Role Key is strictly confined to the backend and NEVER exposed to frontend.
    """

    backend_name = "supabase"

    def __init__(
        self,
        *,
        supabase_url: str,
        service_role_key: str,
        bucket_name: str = "bookabook-images",
        timeout: float = 60.0,
        client: Optional[httpx.Client] = None,
        auto_create_bucket: bool = True,
    ) -> None:
        if not supabase_url or not supabase_url.strip():
            raise ValueError("SUPABASE_URL is required when STORAGE_BACKEND=supabase.")
        if not service_role_key or not service_role_key.strip():
            raise ValueError(
                "SUPABASE_SERVICE_ROLE_KEY is required when STORAGE_BACKEND=supabase."
            )
        if not bucket_name or not bucket_name.strip():
            raise ValueError("SUPABASE_STORAGE_BUCKET is required.")

        self.supabase_url = supabase_url.strip().rstrip("/")
        self.service_role_key = service_role_key.strip()
        self.bucket_name = bucket_name.strip()
        self.timeout = timeout

        self._headers = {
            "Authorization": f"Bearer {self.service_role_key}",
            "apikey": self.service_role_key,
        }

        self._client = client or httpx.Client(
            headers=self._headers,
            timeout=self.timeout,
            follow_redirects=True,
        )

        if auto_create_bucket:
            try:
                self.ensure_bucket_exists()
            except Exception as exc:
                logger.warning(
                    "Could not verify/create Supabase Storage bucket '%s': %s",
                    self.bucket_name,
                    exc,
                )

    def ensure_bucket_exists(self) -> None:
        """Verify that the bucket exists; create as public bucket if absent."""
        check_url = f"{self.supabase_url}/storage/v1/bucket/{self.bucket_name}"
        res = self._client.get(check_url)
        if res.status_code == 200:
            return

        if res.status_code == 404:
            create_url = f"{self.supabase_url}/storage/v1/bucket"
            payload = {
                "id": self.bucket_name,
                "name": self.bucket_name,
                "public": True,
                "file_size_limit": 52428800,  # 50 MB
                "allowed_mime_types": ["image/jpeg", "image/jpg"],
            }
            create_res = self._client.post(create_url, json=payload)
            if create_res.status_code not in (200, 201):
                logger.warning(
                    "Bucket creation returned status %d: %s",
                    create_res.status_code,
                    create_res.text,
                )

    def _object_url(self, object_key: str, public: bool = False) -> str:
        norm = normalize_object_key(object_key)
        mode = "public" if public else "authenticated"
        # Encode key segments while preserving slashes
        quoted_key = "/".join(urllib.parse.quote(part, safe="") for part in norm.split("/"))
        return f"{self.supabase_url}/storage/v1/object/{mode}/{self.bucket_name}/{quoted_key}"

    def put_bytes(
        self,
        object_key: str,
        data: bytes,
        content_type: str = "image/jpeg",
    ) -> str:
        """Upload raw bytes to Supabase Storage with upsert enabled."""
        norm = normalize_object_key(object_key)
        quoted_key = "/".join(urllib.parse.quote(part, safe="") for part in norm.split("/"))
        upload_url = f"{self.supabase_url}/storage/v1/object/{self.bucket_name}/{quoted_key}"

        upload_headers = {
            **self._headers,
            "Content-Type": content_type,
            "x-upsert": "true",
        }

        res = self._client.post(upload_url, content=data, headers=upload_headers)
        if res.status_code not in (200, 201):
            raise RuntimeError(
                f"Failed to upload '{norm}' to Supabase Storage: "
                f"HTTP {res.status_code} - {res.text}"
            )
        return norm

    def get_bytes(self, object_key: str) -> bytes:
        """Retrieve binary bytes for object_key from Supabase Storage."""
        norm = normalize_object_key(object_key)
        # Use authenticated endpoint with Service Role Key for reliable server-side retrieval
        quoted_key = "/".join(urllib.parse.quote(part, safe="") for part in norm.split("/"))
        get_url = f"{self.supabase_url}/storage/v1/object/authenticated/{self.bucket_name}/{quoted_key}"

        res = self._client.get(get_url)
        if res.status_code == 404:
            raise FileNotFoundError(
                f"Object '{norm}' not found in Supabase Storage bucket '{self.bucket_name}'."
            )
        if res.status_code != 200:
            raise RuntimeError(
                f"Failed to retrieve '{norm}' from Supabase Storage: "
                f"HTTP {res.status_code} - {res.text}"
            )
        return res.content

    def exists(self, object_key: str) -> bool:
        """Check if object_key exists in Supabase Storage."""
        try:
            norm = normalize_object_key(object_key)
            quoted_key = "/".join(urllib.parse.quote(part, safe="") for part in norm.split("/"))
            get_url = f"{self.supabase_url}/storage/v1/object/authenticated/{self.bucket_name}/{quoted_key}"
            res = self._client.head(get_url)
            if res.status_code == 200:
                return True
            if res.status_code == 404:
                return False
            # Fallback to GET check if HEAD is restricted
            res_get = self._client.get(get_url)
            return res_get.status_code == 200
        except Exception:
            return False

    def delete(self, object_key: str) -> bool:
        """Delete object_key from Supabase Storage."""
        try:
            norm = normalize_object_key(object_key)
            quoted_key = "/".join(urllib.parse.quote(part, safe="") for part in norm.split("/"))
            del_url = f"{self.supabase_url}/storage/v1/object/{self.bucket_name}/{quoted_key}"
            res = self._client.delete(del_url)
            if res.status_code in (200, 204):
                return True
            # Try bulk prefix delete API supported by Supabase
            bulk_url = f"{self.supabase_url}/storage/v1/object/{self.bucket_name}"
            bulk_res = self._client.request(
                "DELETE",
                bulk_url,
                json={"prefixes": [norm]},
            )
            return bulk_res.status_code in (200, 204)
        except Exception as exc:
            logger.warning("Error deleting object '%s' from Supabase Storage: %s", object_key, exc)
            return False

    def get_public_or_signed_url(
        self,
        object_key: str,
        expires_in: int = 3600,
    ) -> Optional[str]:
        """Return direct public URL for the image on Supabase Storage.

        This URL does NOT contain the Service Role Key and is safe for browser rendering.
        """
        norm = normalize_object_key(object_key)
        quoted_key = "/".join(urllib.parse.quote(part, safe="") for part in norm.split("/"))
        return f"{self.supabase_url}/storage/v1/object/public/{self.bucket_name}/{quoted_key}"

