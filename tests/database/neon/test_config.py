"""Tests loading the Neon connection string from the environment."""

import pytest

from krtr.database.neon import config as config_module
from krtr.database.neon.config import NeonConfig, NeonEnvironmentVariable


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevents any real `.env` file or ambient variable from leaking into tests."""
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    monkeypatch.delenv(NeonEnvironmentVariable.CONNECTION_STRING, raising=False)


def test_from_environment_reads_the_connection_string(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies the connection string is read from NEON_DB_HOST specifically."""
    monkeypatch.setenv(NeonEnvironmentVariable.CONNECTION_STRING, "postgresql://u:p@h/db")

    config = NeonConfig.from_environment()

    assert config.connection_string.get_secret_value() == "postgresql://u:p@h/db"


def test_from_environment_raises_when_missing() -> None:
    """Verifies a clear error names NEON_DB_HOST when it is not set."""
    with pytest.raises(ValueError, match=NeonEnvironmentVariable.CONNECTION_STRING.value):
        NeonConfig.from_environment()


def test_secret_is_not_exposed_in_repr() -> None:
    """Verifies the connection string never appears when the config is printed or logged."""
    config = NeonConfig(connection_string="postgresql://u:super-secret@h/db")

    assert "super-secret" not in repr(config)
