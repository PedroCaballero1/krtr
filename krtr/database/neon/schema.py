"""Creates a table's schema in Neon Postgres from its `table.sql`.

Exists so applying any table's DDL (defined in
`krtr/database/queries/<table>/table.sql`) is one function call, for every
table loaded into Neon - not just one hardcoded table. Consumed by the
`krtr database neon create-schema` CLI command.
"""

import logging

from krtr.database.neon.client import NeonClient
from krtr.database.queries import load_sql

logger = logging.getLogger(__name__)


def create_table_schema(client: NeonClient, table_name: str) -> None:
    """Creates a table if it does not already exist, using its `table.sql`.

    Exists so the schema for any table under `krtr/database/queries/` can be
    (re)applied idempotently, from the CLI or tests, without hand-running SQL.

    Args:
        client: An open NeonClient to run the DDL statement against.
        table_name: Name of the table, matching the directory
            `krtr/database/queries/<table_name>/table.sql`.

    Returns:
        None.

    Raises:
        FileNotFoundError: if no `table.sql` exists for `table_name`.
    """
    logger.info("Creating table %s (if not present)", table_name)
    client.execute(load_sql(table_name, "table.sql"))
    logger.info("Schema for %s is up to date", table_name)
