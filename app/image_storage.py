"""Persist generated moodboard images in S3 with a local, same-host fallback."""

import logging
import os
import re
from pathlib import Path

import boto3
from botocore.config import Config


LOGGER = logging.getLogger(__name__)
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "static" / "generated"
IMAGE_NAME = re.compile(r"[0-9a-f]{32}\.jpg\Z")


def _bucket() -> str:
    return os.getenv("SHOTCRAFT_IMAGE_S3_BUCKET", "").strip()


def _key(filename: str) -> str:
    prefix = os.getenv("SHOTCRAFT_IMAGE_S3_PREFIX", "generated/").strip("/")
    return f"{prefix}/{filename}" if prefix else filename


def _client():
    # Bound S3 failures so a generated tile can fall back promptly to local disk.
    return boto3.client(
        "s3",
        region_name=os.getenv("AWS_REGION") or None,
        config=Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 1}),
    )


def save_generated_image(filename: str, image_data: bytes) -> str:
    """Prefer S3 and mirror locally; require local storage if S3 is unavailable."""
    if not IMAGE_NAME.fullmatch(filename):
        raise ValueError("Invalid generated image filename")
    bucket = _bucket()
    uploaded = False
    if bucket:
        try:
            _client().put_object(Bucket=bucket, Key=_key(filename), Body=image_data, ContentType="image/jpeg")
            uploaded = True
        except Exception as exc:
            LOGGER.warning("S3 image upload failed; using local storage (%s)", type(exc).__name__)
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / filename).write_bytes(image_data)
    except OSError:
        if not uploaded:
            raise
        LOGGER.warning("Local image mirror failed; image remains in S3")
    return f"/generated/{filename}"


def load_generated_image(filename: str) -> bytes | None:
    """Read S3 first when configured, falling back to this server's local copy."""
    if not IMAGE_NAME.fullmatch(filename):
        return None
    bucket = _bucket()
    if bucket:
        try:
            return _client().get_object(Bucket=bucket, Key=_key(filename))["Body"].read()
        except Exception as exc:
            LOGGER.warning("S3 image read failed; trying local copy (%s)", type(exc).__name__)
    try:
        return (OUTPUT_DIR / filename).read_bytes()
    except FileNotFoundError:
        return None
