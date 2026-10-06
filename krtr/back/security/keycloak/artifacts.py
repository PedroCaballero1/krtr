"""Defines what the Keycloak admin tooling returns.

Exists to keep the test user's and the user import's contracts discoverable apart from the code
that produces them. Consumed by `krtr/back/security/keycloak/local_user.py`,
`krtr/back/security/credentials/importer.py` and the `krtr back security` CLI.
"""

from pydantic import BaseModel, SecretStr


class LocalUserCredentials(BaseModel):
    """The username and fresh password of the local test user.

    Exists so the CLI can show them once, right after they are set. The password is a
    SecretStr so it is never shown by accident (e.g. in a repr or a log of the model).
    """

    username: str
    password: SecretStr


class PartialImportResult(BaseModel):
    """How many users one `partialImport` call added and skipped (they already existed).

    Exists so the import can report its progress and prove it is idempotent: a second run adds
    nothing and skips everyone.
    """

    added: int
    skipped: int
