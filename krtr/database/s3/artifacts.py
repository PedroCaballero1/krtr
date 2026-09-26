"""Defines the structured values produced and consumed by the S3 client.

Exists to keep the S3 client's contracts (what an S3 path means, what a
download returns) discoverable apart from its implementation. Consumed by
`krtr/database/s3/client.py` and `krtr/cli/database/s3/handler.py`.
"""

from datetime import date
from enum import StrEnum
from pathlib import Path, PurePosixPath

from pydantic import BaseModel

S3_URI_SCHEME = "s3://"


class DatasetFormat(StrEnum):
    """The non-extension formats a dataset can have in the catalog.

    Exists so the catalog never hardcodes these labels. Files use their own
    extension (`.csv`, `.parquet`) as format. Consumed by `DatasetSummary`.
    """

    DIRECTORY = "directory"  # A folder of date-partitioned files.
    UNKNOWN = "unknown"  # A single file without an extension.


class S3Location(BaseModel):
    """A parsed `s3://bucket/key-or-prefix` path.

    Exists so bucket and key are separated once, at the boundary, instead of
    every method re-splitting strings. Consumed by `S3Client`.
    """

    bucket: str
    key: str

    @classmethod
    def parse(cls, s3_path: str, default_bucket: str | None = None) -> "S3Location":
        """Parses an S3 path into an S3Location, using a default bucket if needed.

        Exists to fail fast on malformed paths before any network call and to
        let callers omit the bucket when a default one is configured. A bucket
        written in the path always overrides the default.

        Args:
            s3_path: Either `s3://my-bucket/data/file.csv` or, when a default
                bucket is given, a bare key such as `data/file.csv`.
            default_bucket: Bucket used when the path has no `s3://` scheme.

        Returns:
            S3Location: the bucket and (possibly empty) key.

        Raises:
            ValueError: if the path has no scheme and no default bucket is set,
                or if the scheme is present but the bucket name is missing.
        """
        if not s3_path.startswith(S3_URI_SCHEME):
            if not default_bucket:
                raise ValueError(
                    f"Invalid S3 path '{s3_path}': it must start with '{S3_URI_SCHEME}' "
                    "unless a default bucket is configured"
                )
            return cls(bucket=default_bucket, key=s3_path.lstrip("/"))
        bucket, _, key = s3_path.removeprefix(S3_URI_SCHEME).partition("/")
        if not bucket:
            raise ValueError(f"Invalid S3 path '{s3_path}': the bucket name is missing")
        return cls(bucket=bucket, key=key)


class DownloadResult(BaseModel):
    """The outcome of a download operation.

    Exists so callers know exactly which local files were written. Returned by
    `S3Client` download methods and reported by the CLI.
    """

    downloaded_files: list[Path]


class DatasetSummary(BaseModel):
    """What is available to download for one dataset (concept) in a bucket.

    Exists so the catalog of datasets is a typed result instead of loose
    tuples. Returned by `summarize_datasets` and shown by the `datasets` CLI
    command.
    """

    name: str
    is_partitioned: bool
    file_count: int
    first_date: date | None = None
    last_date: date | None = None
    missing_dates: list[date] = []

    @property
    def concept(self) -> str:
        """Returns the dataset's concept: its name without any file extension.

        Exists so the catalog lists `customers` for `customers.csv` and
        `complaints` for the partitioned `complaints/` folder.

        Returns:
            str: the concept name.
        """
        if self.is_partitioned:
            return self.name
        return PurePosixPath(self.name).with_suffix("").as_posix()

    @property
    def format(self) -> str:
        """Returns the dataset's format: `directory` or the file extension.

        Exists so the catalog says how each concept is stored, e.g. `directory`,
        `.csv` or `.parquet`.

        Returns:
            str: `directory` for partitioned datasets, else the extension
                (`unknown` when the file has none).
        """
        if self.is_partitioned:
            return DatasetFormat.DIRECTORY
        return PurePosixPath(self.name).suffix or DatasetFormat.UNKNOWN
