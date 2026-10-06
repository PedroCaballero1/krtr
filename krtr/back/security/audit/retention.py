"""Deletes audit events older than their 3-month retention (task 4.10, G21).

Exists so the daily `purge_events` Modal cron (task 6.5) runs `events/purge.sql` through one
function that reports how many rows it deleted. The chat text in `messages` has the same
retention and is purged by `NeonMessageStore.purge_expired` in the same cron. Consumed by
`krtr/back/deploy/app.py`.
"""

import logging

from krtr.database.neon.client import NeonClient
from krtr.database.queries import load_sql

logger = logging.getLogger(__name__)

_PURGE = load_sql("events", "purge.sql")


def purge_expired_events(client: NeonClient) -> int:
    """Deletes the events older than the retention.

    Args:
        client: The pooled Neon client of the app database.

    Returns:
        int: how many events were deleted.
    """
    deleted = client.execute_params(_PURGE)
    logger.info("Purged %d expired events", deleted)
    return deleted
