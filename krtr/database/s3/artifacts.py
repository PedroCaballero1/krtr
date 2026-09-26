"""Defines the structured values produced and consumed by the S3 client.

Exists to keep the S3 client's contracts (what an S3 path means, what a
download returns) discoverable apart from its implementation. Consumed by
`krtr/database/s3/client.py` and `krtr/cli/database/s3/handler.py`.
"""

from pathlib import Path

from pydantic import BaseModel

S3_URI_SCHEME = "s3://"


class S3Location(BaseModel):
    """A parsed `s3://bucket/key-or-prefix` path.

    Exists so bucket and key are separated once, at the boundary, instead of
    every method re-splitting strings. Consumed by `S3Client`.
    """

    bucket: str
    key: str

    @classmethod
    def parse(cls, s3_path: str) -> "S3Location":
        """Parses an `s3://bucket/key` string into an S3Location.

        Exists to fail fast on malformed paths before any network call.

        Args:
            s3_path: The path to parse, e.g. `s3://my-bucket/data/file.csv`.

        Returns:
            S3Location: the bucket and (possibly empty) key.

        Raises:
            ValueError: if the path lacks the `s3://` scheme or a bucket name.
        """
        if not s3_path.startswith(S3_URI_SCHEME):
            raise ValueError(f"Invalid S3 path '{s3_path}': it must start with '{S3_URI_SCHEME}'")
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
