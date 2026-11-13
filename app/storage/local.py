"""Local filesystem storage adapter for Bookabook development environment."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.storage.base import StorageAdapter, normalize_object_key


class LocalStorageAdapter(StorageAdapter):
    """Stores exported JPG artifacts on the local filesystem inside base_dir."""

    backend_name = "local"

    def __init__(self, base_dir: Path | str) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, object_key: str) -> Path:
        norm = normalize_object_key(object_key)
        candidate = (self.base_dir / norm).resolve()
        if candidate != self.base_dir and self.base_dir not in candidate.parents:
            print(f"SAFE_PATH_MISMATCH: base_dir={self.base_dir!r}, candidate={candidate!r}, parents={candidate.parents!r}")
            raise ValueError(f"Unsafe object key escapes storage root: '{object_key}'")
        return candidate

    def put_bytes(
        self,
        object_key: str,
        data: bytes,
        content_type: str = "image/jpeg",
    ) -> str:
        norm = normalize_object_key(object_key)
        path = self._resolve_safe_path(norm)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return norm

    def get_bytes(self, object_key: str) -> bytes:
        path = self._resolve_safe_path(object_key)
        if not path.is_file():
            raise FileNotFoundError(f"Object not found in local storage: '{object_key}'")
        return path.read_bytes()

    def exists(self, object_key: str) -> bool:
        path = self._resolve_safe_path(object_key)
        return path.is_file()

    def delete(self, object_key: str) -> bool:
        path = self._resolve_safe_path(object_key)
        if not path.is_file():
            return False
        path.unlink()
        return True

    def get_public_or_signed_url(
        self,
        object_key: str,
        expires_in: int = 3600,
    ) -> Optional[str]:
        return None

