"""Defines the settings of the customer credentials generator (task 3.4, G6).

Exists so the password rules, the Keycloak hash parameters, the samples for the jury and QA,
and where every file goes are declared once. Consumed by `krtr/back/security/credentials/` and
`krtr/cli/back/security/credentials/handler.py`.
"""

import string
from enum import StrEnum
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, Field

DEFAULT_SOURCE = Path("data/customers.parquet")
DEFAULT_OUTPUT_DIRECTORY = Path("data/credentials")
IMPORT_SUBDIRECTORY = "import"
REALM = "krtr"

# The Modal Volume the users files are staged on for the production import (task 3.5), and the
# folder inside it; kept here, free of heavy imports, because the Keycloak image reads them.
IMPORT_VOLUME = "krtr-credentials-import"
VOLUME_IMPORT_DIRECTORY = PurePosixPath("/import")


class SampleGroup(StrEnum):
    """The groups of customers whose passwords are kept in clear, each in its own CSV (D4)."""

    JURY = "jury"  # Handed to the jury (G6).
    QA = "qa"  # Used by the tests against production and the load tests (D4).


# 50 Active customers for the jury (G6) and 50 for QA (D4), never the same customer.
DEFAULT_SAMPLE_SIZES = {SampleGroup.JURY: 50, SampleGroup.QA: 50}


class Argon2Parameters(BaseModel):
    """The argon2id cost Keycloak 26.8 uses by default for new passwords.

    Exists so the imported hashes cost exactly what Keycloak would compute itself: a login
    then takes the same time whether the password was imported or set in Keycloak.
    Written into each credential's `credentialData`, which Keycloak reads to verify it.
    """

    iterations: int = 5
    memory_kib: int = 7168
    parallelism: int = 1
    hash_length: int = 32
    salt_bytes: int = 16


class CredentialsConfig(BaseModel):
    """Settings of one generation run.

    Exists to give the generator a validated, typed settings object. Consumed by
    `krtr/back/security/credentials/generator.py`.
    """

    source: Path = DEFAULT_SOURCE  # Parquet with `customer_id` and `customer_status`.
    output_directory: Path = DEFAULT_OUTPUT_DIRECTORY
    password_length: int = 8  # G6.
    password_alphabet: str = string.ascii_letters + string.digits
    batch_size: int = 1000  # Users per `krtr-users-N.json`.
    sample_sizes: dict[SampleGroup, int] = Field(default_factory=DEFAULT_SAMPLE_SIZES.copy)
    sample_status: str = "Active"  # Only active customers are handed out (G6, D12).
    workers: int | None = None  # Processes that hash; None means one per CPU.
    argon2: Argon2Parameters = Field(default_factory=Argon2Parameters)

    @property
    def import_directory(self) -> Path:
        """Returns where the Keycloak user files are written.

        Returns:
            Path: `<output_directory>/import`.
        """
        return self.output_directory / IMPORT_SUBDIRECTORY

    def sample_file(self, group: SampleGroup) -> Path:
        """Returns the CSV that keeps one group's passwords in clear.

        Args:
            group: The sample group.

        Returns:
            Path: `<output_directory>/<group>_credentials.csv`.
        """
        return self.output_directory / f"{group.value}_credentials.csv"
