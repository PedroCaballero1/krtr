"""Defines the structured values produced by Neon table loaders.

Exists to keep a loader's contracts (what a table's live column looks like,
what a validation failure looks like, what a load run produced) discoverable
apart from its implementation, shared across every table loaded into Neon.
No table's specific shape is declared here — that lives only in that
table's `table.sql`; `ColumnSpec` is populated at runtime by introspecting
the database. Consumed by `krtr/database/neon/client.py`,
`krtr/database/neon/validation.py` and `krtr/database/neon/products/loader.py`.
"""

from pydantic import BaseModel


class ColumnSpec(BaseModel):
    """One column's name, Postgres data type and nullability.

    Exists so a loader validates rows against a table's actual, live schema
    instead of a Python declaration duplicating that table's `table.sql`.
    Returned by `NeonClient.get_column_specs`, in table column order.
    """

    name: str
    data_type: str
    is_nullable: bool


class ValidationFailure(BaseModel):
    """One source row that failed validation and was not loaded.

    Exists so a load run can report exactly which rows were skipped and why,
    without stopping the rest of the load. Returned as part of `LoadSummary`.
    """

    row_number: int
    reason: str


class LoadSummary(BaseModel):
    """The outcome of loading a source file into a Neon table.

    Exists so callers (CLI, tests) get a typed count of what happened instead
    of parsing log output. Returned by table loaders such as
    `krtr/database/neon/products/loader.py`.
    """

    rows_read: int
    rows_loaded: int
    failures: list[ValidationFailure] = []

    @property
    def rows_failed(self) -> int:
        """Returns how many rows failed validation.

        Returns:
            int: the number of entries in `failures`.
        """
        return len(self.failures)
