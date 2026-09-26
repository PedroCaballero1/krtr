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
