"""Checks that the environment is ready to run tasks on Modal.

Exists so a missing token, a missing secret or an unreachable database is
found by one command that names every problem, instead of one at a time in
the middle of a run. The Neon check is reported apart from the Modal ones
because Neon is needed by every run, local or remote, while Modal is needed
only for `--remote` and `--detach`. Consumed by the
`krtr compute modal doctor` command.
"""

import logging

from krtr.compute.modal.artifacts import DoctorCheck, DoctorReport
from krtr.compute.modal.config import DoctorCheckName, ForwardedSecretVariable, ModalConfig
from krtr.compute.modal.errors import MODAL_MISSING_HINT
from krtr.database.neon.client import NeonClient

logger = logging.getLogger(__name__)


def run_doctor(config: ModalConfig) -> DoctorReport:
    """Runs every environment check and collects the results.

    Exists so one bad check never hides the others: each check reports its own
    failure, and the Modal secret is only looked up once the credentials work.

    Args:
        config: The Modal names to check, such as the secret's name.

    Returns:
        DoctorReport: the result of every check, in the order they ran.
    """
    neon_check = _check_neon_connection()
    credentials_check = _check_modal_credentials()
    if credentials_check.passed:
        secret_check = _check_modal_secret(config.secret_name)
    else:
        secret_check = DoctorCheck(
            name=DoctorCheckName.MODAL_SECRET,
            passed=False,
            detail="Not checked: the Modal credentials did not work",
        )
    return DoctorReport(checks=[neon_check, credentials_check, secret_check])


def _check_neon_connection() -> DoctorCheck:
    """Checks that the Neon connection string is set and the database accepts a connection.

    Returns:
        DoctorCheck: passed if a connection could be opened, else failed with the reason.
    """
    try:
        NeonClient().close()
    except Exception as error:
        return DoctorCheck(name=DoctorCheckName.NEON_CONNECTION, passed=False, detail=str(error))
    return DoctorCheck(
        name=DoctorCheckName.NEON_CONNECTION, passed=True, detail="Connected to Neon"
    )


def _check_modal_credentials() -> DoctorCheck:
    """Checks that the Modal SDK is installed and Modal accepts the credentials.

    Exists as a real, cheap request (listing one secret), because a token
    can be present and still be wrong.

    Returns:
        DoctorCheck: passed if Modal answered, else failed with the reason.
    """
    try:
        import modal

        modal.Secret.objects.list(max_objects=1)
    except ImportError:
        return DoctorCheck(
            name=DoctorCheckName.MODAL_CREDENTIALS, passed=False, detail=MODAL_MISSING_HINT
        )
    except Exception as error:
        return DoctorCheck(name=DoctorCheckName.MODAL_CREDENTIALS, passed=False, detail=str(error))
    return DoctorCheck(
        name=DoctorCheckName.MODAL_CREDENTIALS, passed=True, detail="Modal accepted the credentials"
    )


def _check_modal_secret(secret_name: str) -> DoctorCheck:
    """Checks that the Modal secret exists and holds every variable the tasks need.

    Exists because a task on Modal cannot reach Neon without it. Modal never
    returns a secret's values, so this can confirm the names are there but
    not that the values are current; `secrets sync` refreshes them.

    Args:
        secret_name: Name of the Modal secret.

    Returns:
        DoctorCheck: passed if the secret exists with the required variables,
            else failed with the reason and how to fix it.
    """
    import modal

    required_keys = [variable.value for variable in ForwardedSecretVariable]
    try:
        modal.Secret.from_name(secret_name, required_keys=required_keys).hydrate()
    except Exception as error:
        return DoctorCheck(
            name=DoctorCheckName.MODAL_SECRET,
            passed=False,
            detail=f"{error}; create or refresh it with `krtr compute modal secrets sync`",
        )
    return DoctorCheck(
        name=DoctorCheckName.MODAL_SECRET,
        passed=True,
        detail=f"Secret '{secret_name}' exists with {', '.join(required_keys)}",
    )
