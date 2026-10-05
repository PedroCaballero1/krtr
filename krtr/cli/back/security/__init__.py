"""Groups the security-related CLI commands under `krtr back security`.

Exists to mirror the `krtr/back/security/` vertical: each of its sub-verticals registers its own
Typer app here as it grows commands. Consumed by `krtr/cli/back/__init__.py`.
"""

import typer

from krtr.cli.back.security.keycloak.handler import keycloak_app

security_app = typer.Typer(name="security", help="Security commands.", no_args_is_help=True)
security_app.add_typer(keycloak_app, name="keycloak")
