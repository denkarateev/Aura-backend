"""
app/services/storage.py
=======================
S3-compatible storage abstraction with local fallback.

Usage
-----
    from app.services.storage import get_storage

    storage = get_storage()
    url = storage.upload("lounges/brand_cover.jpg", image_bytes, "image/jpeg")
    storage.delete("lounges/brand_cover.jpg")
    public_url = storage.public_url("lounges/brand_cover.jpg")

Environment variables
---------------------
STORAGE_BACKEND     "s3" | "local" (default: "local")
S3_ENDPOINT_URL     https://s3.storage.selcloud.ru
S3_ACCESS_KEY       Selectel S3 access key
S3_SECRET_KEY       Selectel S3 secret key
S3_BUCKET           Bucket name (e.g. "hooka3-media")
S3_PUBLIC_BASE_URL  Public URL prefix for served objects
                    (e.g. "https://hooka3-media.s3.storage.selcloud.ru")

Without S3 credentials the service falls back to LocalStorage transparently —
production will not break when these vars are absent.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    """Minimal interface every storage implementation must satisfy."""

    def upload(self, key: str, data: bytes, content_type: str) -> str:
        """Persist `data` under `key`. Returns public URL."""
        ...

    def delete(self, key: str) -> None:
        """Remove the object. Silently ignores missing keys."""
        ...

    def public_url(self, key: str) -> str:
        """Return the URL under which `key` is publicly accessible."""
        ...


# ---------------------------------------------------------------------------
# LocalStorage — writes to /opt/hooka-backend/static (or $STATIC_ROOT)
# ---------------------------------------------------------------------------

_DEFAULT_STATIC_ROOT = "/opt/hooka-backend/static"


class LocalStorage:
    """
    File-system backend. Mirrors the existing behaviour in main.py.

    The ``base_url`` should be the public URL prefix for the /static mount,
    e.g. ``http://188.253.19.166:8000/static``.  When not set it defaults to
    the relative path ``/static`` which the iOS client resolves via
    ``BackendEnvironment.baseURL``.
    """

    def __init__(
        self,
        root: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._root = root or os.getenv(
            "STATIC_ROOT",
            os.path.join(
                # Try to match the location already used by main.py at startup
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "static",
            ),
        )
        self._base_url = (base_url or os.getenv("STATIC_BASE_URL", "/static")).rstrip("/")

    # ------------------------------------------------------------------
    def upload(self, key: str, data: bytes, content_type: str) -> str:
        fpath = os.path.join(self._root, key.lstrip("/"))
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, "wb") as fh:
            fh.write(data)
        return self.public_url(key)

    def delete(self, key: str) -> None:
        fpath = os.path.join(self._root, key.lstrip("/"))
        try:
            os.remove(fpath)
        except FileNotFoundError:
            pass

    def public_url(self, key: str) -> str:
        return f"{self._base_url}/{key.lstrip('/')}"


# ---------------------------------------------------------------------------
# SelectelS3Storage — boto3 with Selectel S3-compatible endpoint
# ---------------------------------------------------------------------------


class SelectelS3Storage:
    """
    Selectel Object Storage backend using boto3.

    Required env vars:
        S3_ENDPOINT_URL   — https://s3.storage.selcloud.ru
        S3_ACCESS_KEY     — Selectel key id
        S3_SECRET_KEY     — Selectel secret key
        S3_BUCKET         — bucket name
        S3_PUBLIC_BASE_URL — public URL prefix

    Objects are uploaded with ``ACL='public-read'`` so they are directly
    accessible without pre-signed URLs.
    """

    def __init__(self) -> None:
        import boto3  # type: ignore
        from botocore.config import Config  # type: ignore

        self._bucket = os.environ["S3_BUCKET"]
        self._base_url = os.environ["S3_PUBLIC_BASE_URL"].rstrip("/")
        self._client = boto3.client(
            "s3",
            endpoint_url=os.environ["S3_ENDPOINT_URL"],
            aws_access_key_id=os.environ["S3_ACCESS_KEY"],
            aws_secret_access_key=os.environ["S3_SECRET_KEY"],
            region_name=os.getenv("S3_REGION", "ru-1"),
            config=Config(
                signature_version="s3v4",
                connect_timeout=10,
                read_timeout=30,
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )

    # ------------------------------------------------------------------
    def upload(self, key: str, data: bytes, content_type: str) -> str:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key.lstrip("/"),
            Body=data,
            ContentType=content_type,
            ACL="public-read",
        )
        return self.public_url(key)

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key.lstrip("/"))
        except Exception:
            pass

    def public_url(self, key: str) -> str:
        return f"{self._base_url}/{key.lstrip('/')}"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_instance: StorageBackend | None = None


def get_storage() -> StorageBackend:
    """
    Return the configured storage backend (singleton per process).

    Decision logic:
    1. STORAGE_BACKEND=s3  AND all S3_* vars present → SelectelS3Storage
    2. Otherwise → LocalStorage

    This ensures production never breaks when S3 credentials are absent.
    """
    global _instance
    if _instance is not None:
        return _instance

    backend_name = os.getenv("STORAGE_BACKEND", "local").lower()
    s3_ready = all(
        os.getenv(v) for v in (
            "S3_ENDPOINT_URL",
            "S3_ACCESS_KEY",
            "S3_SECRET_KEY",
            "S3_BUCKET",
            "S3_PUBLIC_BASE_URL",
        )
    )

    if backend_name == "s3" and s3_ready:
        try:
            _instance = SelectelS3Storage()
            print("[storage] Using SelectelS3Storage backend")
        except Exception as exc:
            print(f"[storage] S3 init failed ({exc}), falling back to local")
            _instance = LocalStorage()
    else:
        if backend_name == "s3" and not s3_ready:
            print("[storage] STORAGE_BACKEND=s3 but S3_* vars missing — using local fallback")
        _instance = LocalStorage()

    return _instance


def reset_storage_instance() -> None:
    """For tests: reset the singleton so the next call re-initialises."""
    global _instance
    _instance = None
