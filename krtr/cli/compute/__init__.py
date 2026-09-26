"""Groups the compute-related CLI commands under `krtr compute`.

Exists to mirror the `krtr/compute/` vertical: each backend sub-vertical
registers its own Typer app here. Consumed by `krtr/cli/main.py`.
"""

import typer

from krtr.cli.compute.modal.handler import modal_app

compute_app = typer.Typer(name="compute", help="Compute commands.", no_args_is_help=True)
compute_app.add_typer(modal_app, name="modal")
