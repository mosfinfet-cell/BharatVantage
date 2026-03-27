"""
storage.py — Cloudflare R2 file storage abstraction (S3-compatible).

Usage:
    url = await storage.upload(file_bytes, key="sessions/abc123/swiggy.csv")
    data = await storage.download(key)
    await storage.delete(key)
"""
import asyncio
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
import logging
import io
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_client():
    """Create S3-compatible client pointed at Cloudflare R2."""
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL if settings.R2_ENDPOINT_URL else f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


class StorageClient:

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = _get_client()
        return self._client

    def _key(self, session_id: str, filename: str) -> str:
        """Deterministic storage key: sessions/{session_id}/{filename}"""
        return f"sessions/{session_id}/{filename}"

    async def upload(
        self,
        content: bytes,
        session_id: str,
        filename: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload file bytes to R2. Returns the storage key."""
        key = self._key(session_id, filename)
        try:
            # boto3 is synchronous — run in a thread to avoid blocking the async event loop
            await asyncio.to_thread(
                self.client.put_object,
                Bucket=settings.R2_BUCKET_NAME,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
            logger.info(f"Uploaded {key} ({len(content)} bytes)")
            return key
        except ClientError as e:
            logger.error(f"R2 upload failed for {key}: {e}")
            raise RuntimeError(f"File storage failed: {e}") from e

    async def download(self, key: str) -> bytes:
        """Download file bytes from R2 by key."""
        try:
            response = await asyncio.to_thread(
                self.client.get_object,
                Bucket=settings.R2_BUCKET_NAME,
                Key=key,
            )
            return response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"File not found in storage: {key}")
            raise RuntimeError(f"File download failed: {e}") from e

    async def delete(self, key: str) -> None:
        """Delete a file from R2."""
        try:
            await asyncio.to_thread(
                self.client.delete_object,
                Bucket=settings.R2_BUCKET_NAME,
                Key=key,
            )
            logger.info(f"Deleted {key} from R2")
        except ClientError as e:
            logger.warning(f"R2 delete failed for {key}: {e}")

    async def exists(self, key: str) -> bool:
        """Check if a key exists in R2."""
        try:
            await asyncio.to_thread(
                self.client.head_object,
                Bucket=settings.R2_BUCKET_NAME,
                Key=key,
            )
            return True
        except ClientError:
            return False

    def get_content_type(self, filename: str) -> str:
        ext = filename.rsplit(".", 1)[-1].lower()
        return {
            "csv":  "text/csv",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xls":  "application/vnd.ms-excel",
        }.get(ext, "application/octet-stream")


# Singleton
storage = StorageClient()
