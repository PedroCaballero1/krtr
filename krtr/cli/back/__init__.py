"""Groups the backend-related CLI commands under `krtr back`.

Exists to mirror the `krtr/back/` vertical: each of its sub-verticals (web,
security) registers its own Typer app here as it grows commands. Consumed by
`krtr/cli/main.py`.
"""

import typer

from krtr.cli.back.web.handler import web_app

back_app = typer.Typer(
    name="back", help="Backend (web and security) commands.", no_args_is_help=True
)
back_app.add_typer(web_app, name="web")
