"""Implements a thin Postgres client for the Neon-hosted warehouse tables.

Exists so every table loader executes DDL and batched inserts through one
connection wrapper instead of touching psycopg2 directly. Consumed by
`krtr/database/neon/products/schema.py` and `krtr/database/neon/products/loader.py`.
"""

import logging
from types import TracebackType
from typing import Any, Sequence

import psycopg2
from psycopg2.extras import execute_values
from psycopg2.pool import ThreadedConnectionPool

from krtr.database.neon.artifacts import ColumnSpec
from krtr.database.neon.config import NeonConfig
from krtr.database.queries import load_sql

logger = logging.getLogger(__name__)


class NeonClient:
    """Executes DDL and batched inserts against the Neon Postgres database.

    Exists to centralize connection handling and give table loaders a small,
    reusable interface (`execute`, `insert_rows`, `truncate_table`) instead of
    each one managing its own psycopg2 connection and cursor. Consumed by the
    `neon` CLI commands and any table-specific loader under
    `krtr/database/neon/`.
    """

    def __init__(self, config: NeonConfig | None = None) -> None:
        """Opens a connection to Neon using the given or environment config.

        Args:
            config: NeonConfig with the connection string. When None, it is
                loaded from the environment / `.env` via `NeonConfig.from_environment`.
        """
        resolved_config = config or NeonConfig.from_environment()
        self._config = resolved_config
        self._connection = psycopg2.connect(resolved_config.connection_string.get_secret_value())
        self._pool: ThreadedConnectionPool | None = None

    def __enter__(self) -> "NeonClient":
        """Returns this client, allowing use as a context manager.

        Returns:
            NeonClient: this instance.
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Closes the connection when the context manager block exits.

        Args:
            exc_type: The exception type raised in the block, if any.
            exc: The exception instance raised in the block, if any.
            traceback: The exception traceback, if any.

        Returns:
            None.
        """
        self.close()

    def close(self) -> None:
        """Closes the underlying database connection and the pool, if opened.

        Returns:
            None.
        """
        self._connection.close()
        if self._pool is not None:
            self._pool.closeall()

    def execute(self, statement: str) -> None:
        """Runs a single SQL statement and commits it.

        Exists for DDL (`CREATE TABLE`, `CREATE INDEX`, `TRUNCATE`) where no
        rows are returned.

        Args:
            statement: The SQL statement to execute.

        Returns:
            None.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(statement)
        self._connection.commit()
        logger.debug("Executed statement: %s", statement.strip().splitlines()[0])

    def truncate_table(self, table_name: str) -> None:
        """Removes every row from a table.

        Exists so loads can be restarted without duplicating rows.

        Args:
            table_name: Name of the table to truncate.

        Returns:
            None.
        """
        self.execute(f"TRUNCATE TABLE {table_name}")
        logger.info("Truncated table %s", table_name)

    def insert_rows(self, insert_statement: str, rows: Sequence[tuple[Any, ...]]) -> None:
        """Bulk-inserts rows using a single `execute_values` call.

        Exists so loaders insert a batch in one round trip instead of one
        `INSERT` per row.

        Args:
            insert_statement: An `INSERT INTO table (...) VALUES %s` template.
            rows: The row tuples to insert, in column order.

        Returns:
            None.
        """
        if not rows:
            return
        with self._connection.cursor() as cursor:
            execute_values(cursor, insert_statement, rows, page_size=len(rows))
        self._connection.commit()

    def get_column_specs(self, table_name: str) -> list[ColumnSpec]:
        """Reads a table's columns, in order, with their type and nullability.

        Exists so a loader learns the table's shape from the live database -
        which was built from that table's own `table.sql` - instead of a
        Python declaration duplicating it.

        Args:
            table_name: Name of the table to introspect.

        Returns:
            list[ColumnSpec]: the table's columns, in creation order.

        Raises:
            ValueError: if the table has no columns (it does not exist).
        """
        statement = load_sql("shared", "column_specs.sql")
        with self._connection.cursor() as cursor:
            cursor.execute(statement, {"table_name": table_name})
            rows = cursor.fetchall()
        if not rows:
            raise ValueError(f"Table '{table_name}' has no columns; does it exist?")
        return [
            ColumnSpec(name=name, data_type=data_type, is_nullable=(is_nullable == "YES"))
            for name, data_type, is_nullable in rows
        ]

    def _get_pool(self) -> ThreadedConnectionPool:
        """Returns this client's pooled-connection pool, opening it on first use.

        Exists so the pool is only created for callers that actually need
        parameterized, concurrent-safe queries (`execute_params`, `fetch_one`,
        `fetch_all`); the single-connection loader path (`execute`,
        `insert_rows`, `get_column_specs`) never pays for it.

        Args:
            None.

        Returns:
            ThreadedConnectionPool: the lazily-created pool, reused on every call.
        """
        if self._pool is None:
            self._pool = ThreadedConnectionPool(
                self._config.pool_min_size,
                self._config.pool_max_size,
                self._config.connection_string.get_secret_value(),
            )
            logger.debug(
                "Opened Neon connection pool (min=%d, max=%d)",
                self._config.pool_min_size,
                self._config.pool_max_size,
            )
        return self._pool

    def execute_params(self, statement: str, params: dict[str, Any] | None = None) -> int:
        """Runs a parameterized statement from a pooled connection and commits it.

        Exists for parameterized DML (`INSERT`/`UPDATE`/`DELETE` with
        `%(name)s` placeholders) issued from concurrent request handlers, such
        as the FastAPI BFF's session and event writes, where a single
        long-lived connection would serialize unrelated requests.

        Args:
            statement: The SQL statement to execute, with `%(name)s` placeholders.
            params: The values for the statement's placeholders, by name.

        Returns:
            int: the number of rows the statement affected, e.g. how many
            sessions an `UPDATE` revoked.
        """
        pool = self._get_pool()
        connection = pool.getconn()
        try:
            with connection.cursor() as cursor:
                cursor.execute(statement, params)
                affected_rows = cursor.rowcount
            connection.commit()
            return affected_rows
        finally:
            pool.putconn(connection)

    def fetch_one(
        self, statement: str, params: dict[str, Any] | None = None
    ) -> tuple[Any, ...] | None:
        """Runs a parameterized query from a pooled connection and returns one row.

        Exists for point lookups (e.g. a session by its hash) from concurrent
        request handlers, without holding a dedicated connection per caller.

        Args:
            statement: The SQL query to execute, with `%(name)s` placeholders.
            params: The values for the query's placeholders, by name.

        Returns:
            tuple[Any, ...] | None: the first matching row, or None if no row matched.
        """
        pool = self._get_pool()
        connection = pool.getconn()
        try:
            with connection.cursor() as cursor:
                cursor.execute(statement, params)
                return cursor.fetchone()
        finally:
            pool.putconn(connection)

    def fetch_all(
        self, statement: str, params: dict[str, Any] | None = None
    ) -> list[tuple[Any, ...]]:
        """Runs a parameterized query from a pooled connection and returns every row.

        Exists for list queries (e.g. open cases) from concurrent request
        handlers, without holding a dedicated connection per caller.

        Args:
            statement: The SQL query to execute, with `%(name)s` placeholders.
            params: The values for the query's placeholders, by name.

        Returns:
            list[tuple[Any, ...]]: every matching row, in the query's order.
        """
        pool = self._get_pool()
        connection = pool.getconn()
        try:
            with connection.cursor() as cursor:
                cursor.execute(statement, params)
                return cursor.fetchall()
        finally:
            pool.putconn(connection)
