"""Tests S3 path parsing, which every S3 operation relies on."""

import pytest

from krtr.database.s3.artifacts import S3Location


def test_parse_splits_bucket_and_nested_key() -> None:
    """Verifies bucket and full key are separated at the first slash."""
    location = S3Location.parse("s3://my-bucket/data/2024/file.csv")

    assert location.bucket == "my-bucket"
    assert location.key == "data/2024/file.csv"


def test_parse_bucket_only_yields_empty_key() -> None:
    """Verifies a bare bucket path means the bucket root (empty key)."""
    location = S3Location.parse("s3://my-bucket")

    assert (location.bucket, location.key) == ("my-bucket", "")


@pytest.mark.parametrize("bad_path", ["my-bucket/file.csv", "https://x/y", "s3://", "s3:///key"])
def test_parse_rejects_malformed_paths(bad_path: str) -> None:
    """Verifies missing scheme or bucket fails fast instead of hitting S3."""
    with pytest.raises(ValueError, match="Invalid S3 path"):
        S3Location.parse(bad_path)
