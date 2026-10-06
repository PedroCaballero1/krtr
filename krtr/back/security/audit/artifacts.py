"""Defines the result contracts of the audit jobs (task 4.10).

Exists so the CLI and the Modal cron report a sync run from one typed shape instead of a loose
dict. Consumed by `krtr/back/security/audit/keycloak_sync.py`, `krtr/cli/back/security/audit/`
and `krtr/back/deploy/app.py`.
"""

from datetime import datetime

from pydantic import BaseModel


class AuthEventSyncResult(BaseModel):
    """What one run of the Keycloak event sync did.

    Exists so a run can be checked from its logs or its Modal return value: where it resumed
    from, how many Keycloak events it read, and how many of them were new to `events`.
    Produced by `sync_auth_events`.
    """

    since: datetime | None  # None on the first run, which reads every Keycloak event.
    read: int
    inserted: int  # `read` minus the events a previous run already copied.
