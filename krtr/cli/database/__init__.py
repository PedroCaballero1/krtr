"""Groups the database-related CLI commands under `krtr database`.

Exists to mirror the `krtr/database/` vertical: each backend sub-vertical
registers its own Typer app here. Consumed by `krtr/cli/main.py`.
"""

import typer

from krtr.cli.database.neon.handler import neon_app
from krtr.cli.database.s3.handler import s3_app

database_app = typer.Typer(name="database", help="Database commands.", no_args_is_help=True)
database_app.add_typer(s3_app, name="s3")
database_app.add_typer(neon_app, name="neon")
