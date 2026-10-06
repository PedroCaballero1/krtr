"""Generates every customer's login and the jury and QA samples (task 3.4, G6, D4).

Exists so the 150,000 accounts are created in one reproducible, auditable run:

- every `customer_id` gets a random 8-character password (letters and digits, from `secrets`);
- each password is hashed with argon2id, in several processes (hashing is the slow part), and
  written as a Keycloak user, 1,000 per `krtr-users-<n>.json`, in `data/credentials/import/`;
- a seeded draw picks 50 Active customers for the jury and 50 others for QA; only their
  passwords are kept in clear, in `jury_credentials.csv` and `qa_credentials.csv`;
- every other password is discarded as soon as it is hashed.

The seed and the counts go to `manifest.json`. Every file is readable by its owner only.
Consumed by `krtr/cli/back/security/credentials/handler.py`.
"""

import csv
import io
import json
import logging
import os
import random
import secrets
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from krtr.back.security.credentials.artifacts import GenerationSummary
from krtr.back.security.credentials.config import (
    REALM,
    Argon2Parameters,
    CredentialsConfig,
    SampleGroup,
)
from krtr.back.security.credentials.keycloak_format import (
    password_credential,
    user_representation,
    users_file,
)

logger = logging.getLogger(__name__)

MANIFEST_FILE = "manifest.json"
USERS_FILE_TEMPLATE = f"{REALM}-users-{{index}}.json"
OWNER_ONLY = 0o600
CSV_HEADER = ("customer_id", "password")


@dataclass(frozen=True)
class BatchJob:
    """One worker's share: the customers of one users file.

    Exists as the picklable unit a worker process receives. `kept` lists the customers of this
    batch whose password must come back in clear (the jury and QA samples).
    """

    path: Path
    customer_ids: tuple[str, ...]
    kept: frozenset[str]
    password_length: int
    password_alphabet: str
    argon2: Argon2Parameters


def new_password(length: int, alphabet: str) -> str:
    """Generates a password from a cryptographically secure source.

    Args:
        length: How many characters.
        alphabet: The characters to draw from.

    Returns:
        str: the password.
    """
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_credentials(
    config: CredentialsConfig, seed: int | None = None, overwrite: bool = False
) -> GenerationSummary:
    """Runs the whole generation: passwords, hashes, user files, samples and manifest.

    Args:
        config: The settings of the run.
        seed: The seed of the sample draw; a random one, recorded, when None.
        overwrite: Whether earlier output may be replaced (it changes every password).

    Returns:
        GenerationSummary: what was written, and the seed.

    Raises:
        FileExistsError: if earlier output exists and `overwrite` is False.
        ValueError: if the source is invalid or has too few customers for the samples.
    """
    _prepare_output(config, overwrite)
    customers = load_customers(config.source)
    draw_seed = seed if seed is not None else secrets.randbits(63)
    samples = choose_samples(customers, config, draw_seed)
    jobs = _batch_jobs(customers["customer_id"].to_list(), samples, config)
    logger.info("Hashing %d passwords in %d files", customers.height, len(jobs))
    kept = _run_jobs(jobs, config.workers)
    sample_files = {
        group: _write_sample(config, group, ids, kept) for group, ids in samples.items()
    }
    summary = GenerationSummary(
        seed=draw_seed,
        users=customers.height,
        user_files=len(jobs),
        import_directory=config.import_directory,
        samples=sample_files,
    )
    _write_private(config.output_directory / MANIFEST_FILE, summary.model_dump_json(indent=2))
    logger.info("Generated %d users; sample seed %d", summary.users, summary.seed)
    return summary


def load_customers(source: Path) -> pl.DataFrame:
    """Reads every customer's ID and status from the customers Parquet file.

    Args:
        source: The Parquet file.

    Returns:
        pl.DataFrame: `customer_id` and `customer_status`, sorted by ID (so a seed always
        draws the same customers).

    Raises:
        ValueError: if an ID is missing or repeated.
    """
    customers = pl.read_parquet(source, columns=["customer_id", "customer_status"])
    if customers["customer_id"].null_count() or customers["customer_id"].n_unique() != len(
        customers
    ):
        raise ValueError(f"{source} has missing or repeated customer IDs")
    logger.info("Read %d customers from %s", customers.height, source)
    return customers.sort("customer_id")


def choose_samples(
    customers: pl.DataFrame, config: CredentialsConfig, seed: int
) -> dict[SampleGroup, list[str]]:
    """Draws each sample group from the eligible customers, without repeating anyone.

    Args:
        customers: Every customer, sorted by ID.
        config: The sample sizes and the eligible status.
        seed: The draw's seed.

    Returns:
        dict[SampleGroup, list[str]]: each group's customer IDs, in draw order.

    Raises:
        ValueError: if there are fewer eligible customers than the samples need.
    """
    eligible = customers.filter(pl.col("customer_status") == config.sample_status)
    total = sum(config.sample_sizes.values())
    if eligible.height < total:
        raise ValueError(f"Only {eligible.height} {config.sample_status} customers for {total}")
    drawn = random.Random(seed).sample(eligible["customer_id"].to_list(), total)
    samples: dict[SampleGroup, list[str]] = {}
    start = 0
    for group, size in config.sample_sizes.items():
        samples[group] = drawn[start : start + size]
        start += size
    return samples


def hash_batch(job: BatchJob) -> dict[str, str]:
    """Creates the passwords of one batch, writes its users file, and returns the kept ones.

    Runs in a worker process. Passwords outside `job.kept` never leave this function.

    Args:
        job: The batch.

    Returns:
        dict[str, str]: the clear passwords of the batch's sample customers, by customer ID.
    """
    kept: dict[str, str] = {}
    users = []
    for customer_id in job.customer_ids:
        password = new_password(job.password_length, job.password_alphabet)
        users.append(user_representation(customer_id, password_credential(password, job.argon2)))
        if customer_id in job.kept:
            kept[customer_id] = password
    _write_private(job.path, json.dumps(users_file(REALM, users)))
    return kept


def _prepare_output(config: CredentialsConfig, overwrite: bool) -> None:
    """Creates the output folders, refusing to replace an earlier run unless told to.

    Args:
        config: Where the output goes.
        overwrite: Whether earlier output may be deleted.

    Returns:
        None.

    Raises:
        FileExistsError: if earlier output exists and `overwrite` is False.
    """
    earlier = [*config.import_directory.glob("*.json")]
    earlier += [config.sample_file(group) for group in SampleGroup]
    earlier = [path for path in earlier if path.exists()]
    if earlier and not overwrite:
        raise FileExistsError(
            f"{config.output_directory} already has credentials; regenerating changes every "
            "password (the jury's too). Pass --overwrite to do it anyway."
        )
    for path in earlier:
        path.unlink()
    config.import_directory.mkdir(parents=True, exist_ok=True)


def _batch_jobs(
    customer_ids: list[str], samples: dict[SampleGroup, list[str]], config: CredentialsConfig
) -> list[BatchJob]:
    """Splits the customers into one job per users file.

    Args:
        customer_ids: Every customer ID.
        samples: The sample groups, whose passwords must be kept.
        config: The batch size, password rules and hash cost.

    Returns:
        list[BatchJob]: the jobs, in file order.
    """
    sampled = {customer_id for ids in samples.values() for customer_id in ids}
    jobs = []
    for index, start in enumerate(range(0, len(customer_ids), config.batch_size)):
        batch = tuple(customer_ids[start : start + config.batch_size])
        jobs.append(
            BatchJob(
                path=config.import_directory / USERS_FILE_TEMPLATE.format(index=index),
                customer_ids=batch,
                kept=frozenset(sampled.intersection(batch)),
                password_length=config.password_length,
                password_alphabet=config.password_alphabet,
                argon2=config.argon2,
            )
        )
    return jobs


def _run_jobs(jobs: list[BatchJob], workers: int | None) -> dict[str, str]:
    """Runs the jobs in a process pool, logging progress, and gathers the kept passwords.

    Args:
        jobs: The batches.
        workers: How many processes; one per CPU when None.

    Returns:
        dict[str, str]: every kept password, by customer ID.
    """
    kept: dict[str, str] = {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for done, batch_kept in enumerate(pool.map(hash_batch, jobs), start=1):
            kept.update(batch_kept)
            if done % 10 == 0 or done == len(jobs):
                logger.info("Wrote %d of %d user files", done, len(jobs))
    return kept


def _write_sample(
    config: CredentialsConfig, group: SampleGroup, customer_ids: list[str], kept: dict[str, str]
) -> Path:
    """Writes one sample group's CSV of customer IDs and clear passwords.

    Args:
        config: Where the CSV goes.
        group: The group.
        customer_ids: The group's customers, in draw order.
        kept: The clear passwords of every sampled customer.

    Returns:
        Path: the CSV written.
    """
    path = config.sample_file(group)
    rows = [CSV_HEADER, *((customer_id, kept[customer_id]) for customer_id in customer_ids)]
    _write_private(path, _csv_text(rows))
    logger.info("Wrote %d %s credentials to %s", len(customer_ids), group.value, path)
    return path


def _csv_text(rows: list[tuple[str, str]]) -> str:
    """Renders rows as CSV text.

    Args:
        rows: The rows, header first.

    Returns:
        str: the CSV.
    """
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    return buffer.getvalue()


def _write_private(path: Path, text: str) -> None:
    """Writes a file readable and writable by its owner only, from its creation.

    Args:
        path: The file.
        text: Its content.

    Returns:
        None.
    """
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, OWNER_ONLY)
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        file.write(text)
