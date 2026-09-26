"""Tests S3Client downloads against a fake in-memory boto3 client."""

from pathlib import Path
from typing import Any

import pytest

from krtr.database.s3 import client as client_module
from krtr.database.s3.client import S3Client
from krtr.database.s3.config import S3Config


class FakeBotoClient:
    """Serves objects from a dict and writes them to disk like boto3 would."""

    def __init__(self, objects: dict[str, bytes], page_size: int = 2) -> None:
        """Stores the fake bucket content and the listing page size."""
        self.objects = objects
        self.page_size = page_size

    def get_paginator(self, operation: str) -> "FakeBotoClient":
        """Returns itself as the paginator."""
        return self

    def paginate(self, Bucket: str, Prefix: str) -> list[dict[str, Any]]:
        """Returns matching keys split into several pages."""
        keys = [key for key in self.objects if key.startswith(Prefix)]
        pages = [keys[i : i + self.page_size] for i in range(0, len(keys), self.page_size)]
        return [{"Contents": [{"Key": key} for key in page]} for page in pages] or [{}]

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        """Writes the object's bytes to `filename`."""
        Path(filename).write_bytes(self.objects[key])


def make_client(monkeypatch: pytest.MonkeyPatch, objects: dict[str, bytes]) -> S3Client:
    """Builds an S3Client backed by a FakeBotoClient holding the given objects."""
    monkeypatch.setattr(client_module.boto3, "client", lambda *a, **k: FakeBotoClient(objects))
    return S3Client(S3Config(access_key_id="id", secret_access_key="secret"))


def test_download_file_writes_content_and_creates_parents(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies the object's bytes land at the requested nested local path."""
    target = tmp_path / "a" / "b" / "file.txt"

    client = make_client(monkeypatch, {"data/file.txt": b"hello"})

    result = client.download_file("s3://bkt/data/file.txt", target)

    assert target.read_bytes() == b"hello"
    assert result.downloaded_files == [target]


@pytest.mark.parametrize("s3_path", ["s3://bkt", "s3://bkt/data/"])
def test_download_file_rejects_paths_without_a_file_key(
    monkeypatch: pytest.MonkeyPatch, s3_path: str
) -> None:
    """Verifies bucket roots and directory paths are not treated as files."""
    with pytest.raises(ValueError, match="does not point to a file"):
        make_client(monkeypatch, {}).download_file(s3_path, Path("out"))


def test_download_directory_preserves_structure_across_pages(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies all paginated objects are saved relative to the prefix."""
    objects = {f"data/sub/{i}.txt": str(i).encode() for i in range(5)} | {"data/root.txt": b"r"}

    result = make_client(monkeypatch, objects).download_directory("s3://bkt/data", tmp_path)

    assert len(result.downloaded_files) == 6
    assert (tmp_path / "root.txt").read_bytes() == b"r"
    assert (tmp_path / "sub" / "4.txt").read_bytes() == b"4"


def test_download_directory_ignores_sibling_prefixes_and_folder_markers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies `data` does not pull in `data2/` and `data/` markers are skipped."""
    objects = {"data/": b"", "data/in.txt": b"in", "data2/out.txt": b"out"}

    result = make_client(monkeypatch, objects).download_directory("s3://bkt/data", tmp_path)

    assert result.downloaded_files == [tmp_path / "in.txt"]
    assert not (tmp_path / "out.txt").exists()


def test_download_directory_raises_when_prefix_is_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies a wrong prefix is an error rather than a silent no-op."""
    with pytest.raises(FileNotFoundError, match="No objects found"):
        make_client(monkeypatch, {"other/x.txt": b"x"}).download_directory(
            "s3://bkt/data", tmp_path
        )


def test_download_directory_blocks_path_traversal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies a malicious `..` key cannot write outside the local directory."""
    destination = tmp_path / "safe"

    with pytest.raises(ValueError, match="outside of"):
        make_client(monkeypatch, {"data/../../evil.txt": b"x"}).download_directory(
            "s3://bkt/data", destination
        )

    assert not (tmp_path / "evil.txt").exists()
