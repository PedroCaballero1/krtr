"""Defines what the local Keycloak tooling returns.

Exists to keep the test user's contract discoverable apart from the code that creates it.
Consumed by `krtr/back/security/keycloak/local_user.py` and the `krtr back security keycloak` CLI.
"""

from pydantic import BaseModel, SecretStr


class LocalUserCredentials(BaseModel):
    """The username and fresh password of the local test user.

    Exists so the CLI can show them once, right after they are set. The password is a
    SecretStr so it is never shown by accident (e.g. in a repr or a log of the model).
    """

    username: str
    password: SecretStr
