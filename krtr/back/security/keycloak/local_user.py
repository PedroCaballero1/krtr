"""Creates and deletes the local test user that logs in to krtr-web.

Exists so anyone on the team can try the login without a password ever being written in the
repository: each run creates the user again with a new random password and shows it once. The
local Keycloak stores its data in the `keycloak` database of the Neon `dev` branch, so the user
is shared by everyone using that branch. Consumed by the `krtr back security keycloak` CLI.
"""

import logging
import secrets

from krtr.back.security.keycloak.admin_client import KeycloakAdminClient
from krtr.back.security.keycloak.artifacts import LocalUserCredentials

logger = logging.getLogger(__name__)

LOCAL_USERNAME = "99999999"  # 8 digits like a customer_id, but not one from the dataset.
LOCAL_PASSWORD_BYTES = 12  # 16 base64url characters, above the realm's length(8) policy.


def reset_local_user(admin: KeycloakAdminClient) -> LocalUserCredentials:
    """Creates the test user with a new random password, replacing it if it exists.

    Replacing (instead of only changing the password) also ends any session it had.

    Args:
        admin: The admin client of the local Keycloak.

    Returns:
        LocalUserCredentials: the username and its new password.
    """
    delete_local_user(admin)
    password = secrets.token_urlsafe(LOCAL_PASSWORD_BYTES)
    admin.create_user(LOCAL_USERNAME, password)
    return LocalUserCredentials(username=LOCAL_USERNAME, password=password)


def delete_local_user(admin: KeycloakAdminClient) -> bool:
    """Deletes the test user, if it exists.

    Args:
        admin: The admin client of the local Keycloak.

    Returns:
        bool: True if a user was deleted, False if there was none.
    """
    user_id = admin.find_user_id(LOCAL_USERNAME)
    if user_id is None:
        logger.info("There is no local test user %s to delete", LOCAL_USERNAME)
        return False
    admin.delete_user(user_id)
    return True
