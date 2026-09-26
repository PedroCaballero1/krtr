"""Tests S3Client downloads against a fake in-memory boto3 client."""

from datetime import date
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
        self.buckets_used: list[str] = []

    def get_paginator(self, operation: str) -> "FakeBotoClient":
        """Returns itself as the paginator."""
        return self

    def paginate(self, Bucket: str, Prefix: str) -> list[dict[str, Any]]:
        """Returns matching keys split into several pages."""
        keys = [key for key in self.objects if key.startswith(Prefix)]
        pages = [keys[i : i + self.page_size] for i in range(0, len(keys), self.page_size)]
        return [{"Contents": [{"Key": key} for key in page]} for page in pages] or [{}]

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        """Records the bucket used and writes the object's bytes to `filename`."""
        self.buckets_used.append(bucket)
        Path(filename).write_bytes(self.objects[key])


def make_client(
    monkeypatch: pytest.MonkeyPatch, objects: dict[str, bytes], bucket: str | None = None
) -> S3Client:
    """Builds an S3Client backed by a FakeBotoClient holding the given objects."""
    monkeypatch.setattr(client_module.boto3, "client", lambda *a, **k: FakeBotoClient(objects))
    return S3Client(S3Config(access_key_id="id", secret_access_key="secret", bucket=bucket))


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


def test_download_file_uses_default_bucket_for_bare_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies the configured bucket is used when the path has no `s3://bucket`."""
    client = make_client(monkeypatch, {"data/f.txt": b"x"}, bucket="env-bkt")

    client.download_file("data/f.txt", tmp_path / "f.txt")

    assert client._boto_client.buckets_used == ["env-bkt"]


def test_download_file_bucket_in_path_overrides_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies a bucket written in the path wins over the configured one."""
    client = make_client(monkeypatch, {"data/f.txt": b"x"}, bucket="env-bkt")

    client.download_file("s3://manual-bkt/data/f.txt", tmp_path / "f.txt")

    assert client._boto_client.buckets_used == ["manual-bkt"]


def test_download_directory_uses_default_bucket_for_bare_prefix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies directory downloads also fall back to the configured bucket."""
    client = make_client(monkeypatch, {"data/a.txt": b"a"}, bucket="env-bkt")

    result = client.download_directory("data", tmp_path)

    assert result.downloaded_files == [tmp_path / "a.txt"]
    assert client._boto_client.buckets_used == ["env-bkt"]


def test_list_files_returns_names_relative_to_directory_across_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies nested files are listed relative to the prefix, skipping markers and siblings."""
    objects = {
        "data/": b"",
        "data/a.txt": b"",
        "data/sub/b.txt": b"",
        "data/sub/c.txt": b"",
        "data2/x.txt": b"",
    }

    files = make_client(monkeypatch, objects).list_files("s3://bkt/data")

    assert files == ["a.txt", "sub/b.txt", "sub/c.txt"]


def test_list_files_returns_empty_list_for_missing_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies an empty directory yields no files instead of an error."""
    assert make_client(monkeypatch, {"other/x.txt": b""}).list_files("s3://bkt/data") == []


def test_list_files_uses_default_bucket_for_bare_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies listing resolves a bare prefix inside the configured bucket."""
    client = make_client(monkeypatch, {"data/a.txt": b""}, bucket="env-bkt")

    assert client.list_files("data") == ["a.txt"]


def test_save_file_list_writes_one_name_per_line_in_named_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies the .txt is named after bucket and prefix and holds the complete list."""
    client = make_client(monkeypatch, {})

    output = client.save_file_list("s3://bkt/data/sub/", ["a.txt", "x/b.txt"], tmp_path / "out")

    assert output == tmp_path / "out" / "bkt_data_sub_files.txt"
    assert output.read_text(encoding="utf-8") == "a.txt\nx/b.txt\n"


def test_save_file_list_names_bucket_root_and_default_bucket(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies an empty prefix and a bare path produce distinct, sensible names."""
    client = make_client(monkeypatch, {}, bucket="env-bkt")

    root = client.save_file_list("s3://bkt", [], tmp_path)
    default = client.save_file_list("data", ["a.txt"], tmp_path)

    assert root.name == "bkt_files.txt"
    assert root.read_text(encoding="utf-8") == ""
    assert default.name == "env-bkt_data_files.txt"


DAILY = {
    f"ds/year=2024/month=01/day={day:02d}/ds_202401{day:02d}.csv": str(day).encode()
    for day in (1, 2, 4)
} | {"customers.csv": b"c"}


def test_list_datasets_summarizes_bucket_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies datasets are derived from the bucket listing, including the missing day."""
    summaries = make_client(monkeypatch, DAILY, bucket="bkt").list_datasets()

    assert [summary.name for summary in summaries] == ["customers.csv", "ds"]
    assert summaries[1].file_count == 3
    assert [day.isoformat() for day in summaries[1].missing_dates] == ["2024-01-03"]


def test_download_dataset_keeps_partition_folders_within_range(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies only in-range days are fetched and saved under their partition folders."""
    client = make_client(monkeypatch, DAILY, bucket="bkt")

    result = client.download_dataset("ds", tmp_path, start_date=date(2024, 1, 2), end_date=None)

    expected = tmp_path / "ds/year=2024/month=01/day=02/ds_20240102.csv"
    assert expected in result.downloaded_files
    assert len(result.downloaded_files) == 2
    assert expected.read_bytes() == b"2"
    assert not (tmp_path / "ds/year=2024/month=01/day=01").exists()


def test_download_dataset_raises_when_nothing_matches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies an unknown dataset or empty range is an error, not a silent no-op."""
    client = make_client(monkeypatch, DAILY, bucket="bkt")

    with pytest.raises(FileNotFoundError, match="ds"):
        client.download_dataset("ds", tmp_path, start_date=date(2030, 1, 1))


def test_save_catalog_writes_one_concept_and_format_per_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies the catalog lists each concept once, without dates, with its format."""
    client = make_client(monkeypatch, DAILY, bucket="bkt")

    output = client.save_catalog("", client.list_datasets(), tmp_path)

    assert output == tmp_path / "bkt_catalog.txt"
    assert output.read_text(encoding="utf-8").splitlines() == ["customers | .csv", "ds | directory"]
