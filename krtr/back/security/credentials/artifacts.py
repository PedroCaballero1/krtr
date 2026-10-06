"""Defines what a credentials generation run produces (task 3.4).

Exists so the CLI reports a run from one typed summary, which never holds a password.
Consumed by `krtr/back/security/credentials/generator.py` and the CLI.
"""

from pathlib import Path

from pydantic import BaseModel

from krtr.back.security.credentials.config import SampleGroup


class GenerationSummary(BaseModel):
    """The outcome of one generation run, safe to log and to keep in `manifest.json`.

    Exists so the seed that chose the samples is recorded (G6: "con semilla registrada") next
    to what was written, without any password.
    """

    seed: int
    users: int
    user_files: int
    import_directory: Path
    samples: dict[SampleGroup, Path]  # Each group's CSV.
