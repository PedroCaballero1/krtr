"""Implements an S3 client that downloads single files or whole directories.

Exists so the rest of the repository never touches boto3 directly and always
gets credentials from `S3Config`. Consumed by `krtr/cli/database/s3/handler.py`
and any script that needs data from S3.
"""

import logging
from pathlib import Path

import boto3

from krtr.database.s3.artifacts import DownloadResult, S3Location
from krtr.database.s3.config import S3Config

logger = logging.getLogger(__name__)


class S3Client:
    """Downloads files and directories from S3 to the local filesystem.

    Exists to wrap boto3 behind a small interface addressed by `s3://` paths
    and local paths. Consumed by the S3 CLI commands.
    """

    def __init__(self, config: S3Config | None = None) -> None:
        """Creates the client and its underlying boto3 S3 connection.

        Args:
            config: S3Config with credentials and settings. When None, it is
                loaded from the environment / `.env` via `S3Config.from_environment`.
                Its `bucket`, if set, is the default for paths without `s3://`.
        """
        resolved_config = config or S3Config.from_environment()
        self._default_bucket = resolved_config.bucket
        self._boto_client = boto3.client(
            "s3",
            aws_access_key_id=resolved_config.access_key_id,
            aws_secret_access_key=resolved_config.secret_access_key.get_secret_value(),
            aws_session_token=(
                resolved_config.session_token.get_secret_value()
                if resolved_config.session_token
                else None
            ),
            region_name=resolved_config.region,
            endpoint_url=resolved_config.endpoint_url,
        )

    def download_file(self, s3_path: str, local_path: Path) -> DownloadResult:
        """Downloads a single S3 object to a local file path.

        Exists for fetching one known object; useful when only a specific file
        is needed rather than a whole prefix.

        Args:
            s3_path: `s3://bucket/key` path of the object, or just the key when a
                default bucket is configured (a bucket in the path overrides it).
            local_path: Local file path to write. Parent directories are created.

        Returns:
            DownloadResult: containing the single file written.

        Raises:
            ValueError: if `s3_path` is malformed or has no object key.
        """
        location = S3Location.parse(s3_path, self._default_bucket)
        if not location.key or location.key.endswith("/"):
            raise ValueError(
                f"S3 path '{s3_path}' does not point to a file; use a directory download"
            )
        self._download_object(location.bucket, location.key, local_path)
        return DownloadResult(downloaded_files=[local_path])

    def download_directory(self, s3_path: str, local_path: Path) -> DownloadResult:
        """Downloads every object under an S3 prefix into a local directory.

        Exists for fetching a whole "directory" while preserving its structure;
        useful for datasets split across many objects.

        Args:
            s3_path: `s3://bucket/prefix` path of the directory, or just the prefix when
                a default bucket is configured (a bucket in the path overrides it).
                An empty prefix means the entire bucket.
            local_path: Local directory to write into; created if missing.

        Returns:
            DownloadResult: containing every file written.

        Raises:
            ValueError: if `s3_path` is malformed.
            FileNotFoundError: if no objects exist under the prefix.
        """
        location = S3Location.parse(s3_path, self._default_bucket)
        prefix = self._as_directory_prefix(location.key)
        keys = self._list_file_keys(location.bucket, prefix)
        if not keys:
            raise FileNotFoundError(f"No objects found under '{s3_path}'")
        logger.info("Downloading %d objects from %s to %s", len(keys), s3_path, local_path)
        downloaded_files = [
            self._download_object(
                location.bucket, key, self._resolve_destination(local_path, key, prefix)
            )
            for key in keys
        ]
        return DownloadResult(downloaded_files=downloaded_files)

    def list_files(self, s3_path: str) -> list[str]:
        """Lists the names of all files under an S3 directory.

        Exists to let callers inspect what a directory contains before (or
        instead of) downloading it; useful for picking specific files.

        Args:
            s3_path: `s3://bucket/prefix` path of the directory, or just the
                prefix when a default bucket is configured (a bucket in the
                path overrides it). An empty prefix means the entire bucket.

        Returns:
            list[str]: file names relative to the directory, including any
                sub-directory (e.g. `sub/file.csv`); empty if none exist.

        Raises:
            ValueError: if `s3_path` is malformed.
        """
        location = S3Location.parse(s3_path, self._default_bucket)
        prefix = self._as_directory_prefix(location.key)
        keys = self._list_file_keys(location.bucket, prefix)
        logger.info("Found %d files under %s", len(keys), s3_path)
        return [key.removeprefix(prefix) for key in keys]

    @staticmethod
    def _as_directory_prefix(key: str) -> str:
        """Normalizes a key so it only matches entries inside that directory.

        Exists so `data` does not also match `data2/...`.

        Args:
            key: The raw key or prefix from the S3 path.

        Returns:
            str: the key with a trailing slash, or empty for the bucket root.
        """
        return f"{key.rstrip('/')}/" if key.rstrip("/") else ""

    def _list_keys(self, bucket: str, prefix: str) -> list[str]:
        """Lists all object keys under a prefix, following pagination.

        Exists because S3 returns at most 1000 keys per request.

        Args:
            bucket: Bucket name.
            prefix: Key prefix to list.

        Returns:
            list[str]: every matching object key.
        """
        paginator = self._boto_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
        return [item["Key"] for page in pages for item in page.get("Contents", [])]

    def _list_file_keys(self, bucket: str, prefix: str) -> list[str]:
        """Lists object keys under a prefix, excluding folder marker keys.

        Exists so listing and downloading agree on what counts as a file.

        Args:
            bucket: Bucket name.
            prefix: Key prefix to list.

        Returns:
            list[str]: every matching key that does not end with `/`.
        """
        return [key for key in self._list_keys(bucket, prefix) if not key.endswith("/")]

    @staticmethod
    def _resolve_destination(local_directory: Path, key: str, prefix: str) -> Path:
        """Maps an S3 key to its destination inside the local directory.

        Exists to guarantee downloads never escape `local_directory`, even for
        keys containing `..` segments.

        Args:
            local_directory: Root local directory.
            key: Full S3 object key.
            prefix: Directory prefix removed from the key.

        Returns:
            Path: the destination file path.

        Raises:
            ValueError: if the key would resolve outside `local_directory`.
        """
        destination = local_directory / key.removeprefix(prefix)
        if not destination.resolve().is_relative_to(local_directory.resolve()):
            raise ValueError(f"Refusing to write key '{key}' outside of '{local_directory}'")
        return destination

    def _download_object(self, bucket: str, key: str, destination: Path) -> Path:
        """Downloads one object to `destination`, creating parent directories.

        Exists as the single place where bytes are fetched and written.

        Args:
            bucket: Bucket name.
            key: Object key.
            destination: Local file path to write.

        Returns:
            Path: the destination that was written.
        """
        destination.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Downloading s3://%s/%s to %s", bucket, key, destination)
        self._boto_client.download_file(bucket, key, str(destination))
        return destination
