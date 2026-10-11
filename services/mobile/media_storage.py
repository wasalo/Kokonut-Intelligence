"""Private object storage adapter for S3-compatible providers such as R2."""

from __future__ import annotations

import os
from typing import Protocol
from urllib.parse import urlsplit

MAX_MEDIA_BYTES = 2_000_000
ALLOWED_CONTENT_TYPES = frozenset({"image/jpeg"})


class MediaStorageNotConfigured(RuntimeError):
    """Raised when private object storage is not configured safely."""


class PrivateMediaStore(Protocol):
    def put_private(self, key: str, body: bytes, content_type: str) -> None: ...
    def head_private(self, key: str) -> dict: ...
    def delete_private(self, key: str) -> None: ...


class S3CompatibleMediaStore:
    """Small provider-neutral adapter around an S3-compatible private bucket."""

    def __init__(self, client, bucket: str):
        self._client = client
        self._bucket = bucket

    def put_private(self, key: str, body: bytes, content_type: str) -> None:
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ValueError("Unsupported private media type")
        if not body or len(body) > MAX_MEDIA_BYTES:
            raise ValueError("Private media size is outside the allowed range")
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )

    def head_private(self, key: str) -> dict:
        return self._client.head_object(Bucket=self._bucket, Key=key)

    def delete_private(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)


def _default_client_factory(**kwargs):
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise MediaStorageNotConfigured("S3-compatible object storage client is unavailable") from exc
    return boto3.client("s3", config=Config(signature_version="s3v4"), **kwargs)


def create_media_store(environ=None, *, client_factory=None) -> PrivateMediaStore:
    """Build the adapter from explicit S3-compatible private-bucket settings."""
    source = os.environ if environ is None else environ
    provider = source.get("MOBILE_MEDIA_PROVIDER", "s3").strip().lower()
    if provider == "local":
        from services.mobile.local_media import LocalMediaStore

        directory = source.get("MOBILE_MEDIA_LOCAL_DIRECTORY", "").strip()
        key = source.get("MOBILE_MEDIA_LOCAL_KEY", "").strip()
        if not directory or not key:
            raise MediaStorageNotConfigured("Local media directory and encryption key are required")
        return LocalMediaStore(directory, key)
    if provider != "s3":
        raise MediaStorageNotConfigured("Unknown private media provider")
    names = (
        "MOBILE_MEDIA_S3_ENDPOINT",
        "MOBILE_MEDIA_S3_BUCKET",
        "MOBILE_MEDIA_S3_ACCESS_KEY_ID",
        "MOBILE_MEDIA_S3_SECRET_ACCESS_KEY",
        "MOBILE_MEDIA_S3_REGION",
    )
    values = {name: str(source.get(name, "")).strip() for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise MediaStorageNotConfigured("Private media storage is not configured")

    endpoint = urlsplit(values["MOBILE_MEDIA_S3_ENDPOINT"])
    local_http = endpoint.scheme == "http" and endpoint.hostname in {"localhost", "127.0.0.1", "::1"}
    if not endpoint.netloc or (endpoint.scheme != "https" and not local_http):
        raise MediaStorageNotConfigured("Private media storage endpoint must use HTTPS")

    factory = client_factory or _default_client_factory
    client = factory(
        endpoint_url=values["MOBILE_MEDIA_S3_ENDPOINT"],
        region_name=values["MOBILE_MEDIA_S3_REGION"],
        aws_access_key_id=values["MOBILE_MEDIA_S3_ACCESS_KEY_ID"],
        aws_secret_access_key=values["MOBILE_MEDIA_S3_SECRET_ACCESS_KEY"],
    )
    return S3CompatibleMediaStore(client, values["MOBILE_MEDIA_S3_BUCKET"])
