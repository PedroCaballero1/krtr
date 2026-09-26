"""Tests loading S3 settings from the environment."""

import pytest

from krtr.database.s3 import config as config_module
from krtr.database.s3.config import S3Config, S3EnvironmentVariable


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevents any real `.env` file or ambient variable from leaking into tests."""
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    for variable in S3EnvironmentVariable:
        monkeypatch.delenv(variable, raising=False)


def test_from_environment_reads_all_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies every variable, including optional ones, maps to its field."""
    monkeypatch.setenv(S3EnvironmentVariable.ACCESS_KEY_ID, "key-id")
    monkeypatch.setenv(S3EnvironmentVariable.SECRET_ACCESS_KEY, "secret")
    monkeypatch.setenv(S3EnvironmentVariable.SESSION_TOKEN, "token")
    monkeypatch.setenv(S3EnvironmentVariable.REGION, "eu-west-1")
    monkeypatch.setenv(S3EnvironmentVariable.ENDPOINT_URL, "http://localhost:9000")

    config = S3Config.from_environment()

    assert config.access_key_id == "key-id"
    assert config.secret_access_key.get_secret_value() == "secret"
    assert config.session_token.get_secret_value() == "token"
    assert config.region == "eu-west-1"
    assert config.endpoint_url == "http://localhost:9000"


def test_from_environment_leaves_optional_settings_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies only credentials are required."""
    monkeypatch.setenv(S3EnvironmentVariable.ACCESS_KEY_ID, "key-id")
    monkeypatch.setenv(S3EnvironmentVariable.SECRET_ACCESS_KEY, "secret")

    config = S3Config.from_environment()

    assert (config.session_token, config.region, config.endpoint_url) == (None, None, None)


def test_from_environment_names_every_missing_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies the error lists exactly which required variables are absent."""
    monkeypatch.setenv(S3EnvironmentVariable.ACCESS_KEY_ID, "key-id")

    with pytest.raises(ValueError, match=S3EnvironmentVariable.SECRET_ACCESS_KEY.value) as error:
        S3Config.from_environment()

    assert S3EnvironmentVariable.ACCESS_KEY_ID.value not in str(error.value)


def test_secret_is_not_exposed_in_repr() -> None:
    """Verifies the secret key never appears when the config is printed or logged."""
    config = S3Config(access_key_id="key-id", secret_access_key="super-secret")

    assert "super-secret" not in repr(config)
