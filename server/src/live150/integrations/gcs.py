"""Thin GCS wrapper over ADC. No signed URLs, no service accounts."""

import logging
from functools import lru_cache
from typing import TYPE_CHECKING, BinaryIO

from live150.config import settings

if TYPE_CHECKING:
    from google.cloud.storage import Client

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _client() -> "Client":
    from google.cloud import storage

    return storage.Client()


def bucket_name() -> str:
    return f"live150-docs-{settings.env}"


def object_path(user_id: str, document_id: str, extension: str) -> str:
    return f"users/{user_id}/{document_id}.{extension.lstrip('.')}"


def parse_gs_uri(gs_uri: str) -> tuple[str, str]:
    if not gs_uri.startswith("gs://"):
        raise ValueError(f"Malformed gs URI: {gs_uri!r}")
    rest = gs_uri[len("gs://") :]
    bucket, _, path = rest.partition("/")
    if not bucket or not path:
        raise ValueError(f"Malformed gs URI: {gs_uri!r}")
    return bucket, path


def upload(
    user_id: str,
    document_id: str,
    file: BinaryIO,
    mime_type: str,
    extension: str,
) -> str:
    """Stream-upload to GCS and return the gs:// URI."""
    bucket = _client().bucket(bucket_name())
    path = object_path(user_id, document_id, extension)
    blob = bucket.blob(path)
    blob.upload_from_file(file, content_type=mime_type, rewind=True)
    gs_uri = f"gs://{bucket_name()}/{path}"
    logger.info(
        "gcs.upload ok",
        extra={
            "gs_uri": gs_uri,
            "user_id": user_id,
            "document_id": document_id,
            "mime_type": mime_type,
            "size_bytes": blob.size,
        },
    )
    return gs_uri


def open_read(gs_uri: str) -> bytes:
    """Download object bytes. For small files (<=25MB)."""
    bucket_n, path = parse_gs_uri(gs_uri)
    blob = _client().bucket(bucket_n).blob(path)
    data = blob.download_as_bytes()
    logger.info(
        "gcs.download ok",
        extra={"gs_uri": gs_uri, "size_bytes": len(data)},
    )
    return data


def delete(gs_uri: str) -> None:
    """Hard-delete; idempotent on NotFound."""
    from google.cloud.exceptions import NotFound

    bucket_n, path = parse_gs_uri(gs_uri)
    blob = _client().bucket(bucket_n).blob(path)
    try:
        blob.delete()
    except NotFound:
        logger.info("gcs.delete missing", extra={"gs_uri": gs_uri})
        return
    logger.info("gcs.delete ok", extra={"gs_uri": gs_uri})
