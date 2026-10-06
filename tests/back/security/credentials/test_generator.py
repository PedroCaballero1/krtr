"""Tests the credentials generator (task 3.4): every customer, the samples, and no leaked password.

The hash cost is lowered so the tests run fast; the format is the one Keycloak verifies.
"""

import base64
import csv
import json
import stat
from pathlib import Path

import polars as pl
import pytest

from krtr.back.security.credentials.config import Argon2Parameters, CredentialsConfig, SampleGroup
from krtr.back.security.credentials.generator import (
    choose_samples,
    generate_credentials,
    load_customers,
    new_password,
)
from tests.back.security.credentials.test_keycloak_format import recompute

CHEAP = Argon2Parameters(iterations=1, memory_kib=8)
STATUSES = ["Active", "Active", "Inactive", "Active", "Closed"]  # 15 Active of 25.


def write_customers(directory: Path, count: int = 25) -> Path:
    """Writes a customers Parquet file with `count` customers, cycling through STATUSES."""
    path = directory / "customers.parquet"
    pl.DataFrame(
        {
            "customer_id": [f"CLI-{number:012d}" for number in range(count)],
            "customer_status": [STATUSES[number % len(STATUSES)] for number in range(count)],
        }
    ).write_parquet(path)
    return path


def make_config(tmp_path: Path, **overrides: object) -> CredentialsConfig:
    """Builds a small, cheap run: batches of 10, 3 jury and 3 QA customers, 2 processes."""
    settings = {
        "source": write_customers(tmp_path),
        "output_directory": tmp_path / "credentials",
        "batch_size": 10,
        "sample_sizes": {SampleGroup.JURY: 3, SampleGroup.QA: 3},
        "workers": 2,
        "argon2": CHEAP,
        **overrides,
    }
    return CredentialsConfig(**settings)


def read_users(config: CredentialsConfig) -> dict[str, dict]:
    """Reads every generated Keycloak user, by username."""
    users = {}
    for path in sorted(config.import_directory.glob("krtr-users-*.json")):
        body = json.loads(path.read_text())
        assert body["realm"] == "krtr"
        users.update({user["username"]: user for user in body["users"]})
    return users


def read_sample(path: Path) -> dict[str, str]:
    """Reads a sample CSV as {customer_id: password}."""
    with path.open() as file:
        return {row["customer_id"]: row["password"] for row in csv.DictReader(file)}


def verifies(user: dict, password: str) -> bool:
    """Checks a clear password against a user's stored hash, as Keycloak would."""
    secret = json.loads(user["credentials"][0]["secretData"])
    return secret["value"] == recompute(password, base64.b64decode(secret["salt"]), CHEAP)


def test_every_customer_becomes_one_user_in_files_of_the_batch_size(tmp_path: Path) -> None:
    """25 customers in batches of 10: 3 files named for kc.sh / partialImport, nobody twice."""
    config = make_config(tmp_path)

    summary = generate_credentials(config, seed=7)

    files = sorted(path.name for path in config.import_directory.iterdir())
    assert files == ["krtr-users-0.json", "krtr-users-1.json", "krtr-users-2.json"]
    assert sorted(read_users(config)) == [f"CLI-{number:012d}" for number in range(25)]
    assert (summary.users, summary.user_files) == (25, 3)


def test_sample_passwords_open_their_accounts(tmp_path: Path) -> None:
    """The jury's CSV is useful only if each password matches that customer's hash."""
    config = make_config(tmp_path)
    generate_credentials(config, seed=7)
    users = read_users(config)

    for group in SampleGroup:
        sample = read_sample(config.sample_file(group))
        assert len(sample) == 3
        assert all(
            verifies(users[customer_id], password) for customer_id, password in sample.items()
        )


def test_samples_are_active_and_never_shared(tmp_path: Path) -> None:
    """G6: only Active customers; D4: QA never uses a jury account."""
    config = make_config(tmp_path)
    generate_credentials(config, seed=7)
    statuses = dict(pl.read_parquet(config.source).iter_rows())

    jury = set(read_sample(config.sample_file(SampleGroup.JURY)))
    qa = set(read_sample(config.sample_file(SampleGroup.QA)))

    assert jury.isdisjoint(qa)
    assert {statuses[customer_id] for customer_id in jury | qa} == {"Active"}


def test_the_seed_makes_the_draw_reproducible(tmp_path: Path) -> None:
    """With the recorded seed, the same customers are chosen again (G6)."""
    config = make_config(tmp_path)
    customers = load_customers(config.source)

    assert choose_samples(customers, config, 7) == choose_samples(customers, config, 7)
    assert choose_samples(customers, config, 7) != choose_samples(customers, config, 8)


def test_the_manifest_records_the_seed_and_no_password(tmp_path: Path) -> None:
    """The run is auditable without exposing anything."""
    config = make_config(tmp_path)
    generate_credentials(config, seed=7)
    passwords = set(read_sample(config.sample_file(SampleGroup.JURY)).values())

    manifest = (config.output_directory / "manifest.json").read_text()

    assert json.loads(manifest)["seed"] == 7
    assert not any(password in manifest for password in passwords)


def test_no_password_is_kept_in_clear_outside_the_samples(tmp_path: Path) -> None:
    """G6(f): the user files hold hashes only, and only the two CSVs hold clear passwords."""
    config = make_config(tmp_path)
    generate_credentials(config, seed=7)
    samples = {**read_sample(config.sample_file(SampleGroup.JURY))}
    samples.update(read_sample(config.sample_file(SampleGroup.QA)))

    user_files = "".join(path.read_text() for path in config.import_directory.iterdir())
    written = sorted(path.name for path in config.output_directory.rglob("*") if path.is_file())

    assert not any(f'"{password}"' in user_files for password in samples.values())
    assert written == [
        "jury_credentials.csv",
        "krtr-users-0.json",
        "krtr-users-1.json",
        "krtr-users-2.json",
        "manifest.json",
        "qa_credentials.csv",
    ]


def test_every_file_is_readable_by_its_owner_only(tmp_path: Path) -> None:
    """Hashes and the jury's passwords must not be readable by other users of the machine."""
    config = make_config(tmp_path)
    generate_credentials(config, seed=7)

    modes = {stat.S_IMODE(path.stat().st_mode) for path in config.output_directory.rglob("*.*")}

    assert modes == {0o600}


def test_an_earlier_run_is_not_replaced_by_accident(tmp_path: Path) -> None:
    """Regenerating changes the jury's passwords; it needs an explicit --overwrite."""
    config = make_config(tmp_path)
    generate_credentials(config, seed=7)
    first_jury = read_sample(config.sample_file(SampleGroup.JURY))

    with pytest.raises(FileExistsError):
        generate_credentials(config, seed=7)
    generate_credentials(config, seed=7, overwrite=True)

    assert read_sample(config.sample_file(SampleGroup.JURY)) != first_jury


def test_too_few_active_customers_fail_fast(tmp_path: Path) -> None:
    """Asking for more samples than eligible customers must stop before hashing anything."""
    config = make_config(tmp_path, sample_sizes={SampleGroup.JURY: 10, SampleGroup.QA: 10})

    with pytest.raises(ValueError, match="Active"):
        generate_credentials(config, seed=7)

    assert not list(config.import_directory.glob("*.json"))


def test_repeated_customer_ids_are_rejected(tmp_path: Path) -> None:
    """Two users with one username would make the import fail halfway."""
    path = tmp_path / "customers.parquet"
    pl.DataFrame(
        {"customer_id": ["CLI-1", "CLI-1"], "customer_status": ["Active"] * 2}
    ).write_parquet(path)

    with pytest.raises(ValueError, match="repeated"):
        load_customers(path)


def test_passwords_are_8_letters_or_digits_and_unpredictable() -> None:
    """G6: 8 characters from upper, lower and digits, from a secure source."""
    alphabet = CredentialsConfig().password_alphabet
    passwords = {new_password(8, alphabet) for _ in range(500)}

    assert len(passwords) == 500
    assert all(
        len(password) == 8 and password.isalnum() and password.isascii() for password in passwords
    )
