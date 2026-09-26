# CLAUDE.md

Guidance for Claude Code when writing or modifying code in this repository.

## Project structure

The `krtr` package (repo root: `krtr/`) is organized as **vertical slices**, not by
technical layer: each subdirectory directly under `krtr/` is a single, self-contained
concept, and further nesting narrows that concept into concrete implementations. This
is encapsulation and Single Responsibility applied at the package level — a vertical
should be understandable, testable, and replaceable without touching unrelated
verticals.

Example: `krtr/database/` is the "database" concept; each backend gets its own
sub-vertical: `krtr/database/s3/`, `krtr/database/snowflake/`. Shared database-wide
contracts/config live in `database/`; backend-specific logic stays inside its own
backend directory and does not leak into siblings.

At the discretion of whoever is implementing a subpackage, but preferred by default,
each subpackage should expose:

- **`config.py`** — the subpackage's configuration, defined with pydantic `BaseModel`s
  (see the Pydantic usage rule below).
- **`artifacts.py`** — the subpackage's contracts: the pydantic `BaseModel`s and typed
  return shapes that the subpackage's classes and functions produce or consume.

Splitting config and artifacts into their own modules keeps a subpackage's public
contract (what it accepts, what it returns) discoverable in two files, separate from
its implementation.

### CLI

The CLI is defined in `krtr/cli/` using `typer`. CLI commands should stay thin: parse
input, call into the relevant vertical under `krtr/`, and present the result. Business
logic belongs in the vertical package it concerns, not in the CLI layer.

`krtr/cli/` **mirrors the structure of `krtr/`**: for each vertical (and sub-vertical)
under `krtr/`, there is a matching module or subpackage under `krtr/cli/` that exposes
its commands, registered onto the root `app` (from `krtr/cli/main.py`) via
`app.add_typer(...)`. Example: `krtr/database/s3/` gets `krtr/cli/database/s3.py`
(or `krtr/cli/database/s3/` if it needs several command modules). A vertical with no
user-facing commands does not need a CLI counterpart — the mirroring is structural
where commands exist, not mandatory for every file.

### Tests

`tests/` (at the repo root) **mirrors the structure of `krtr/` 1:1**, including
`krtr/cli/`. Every module's tests live at the same relative path under `tests/` as the
module itself under `krtr/`: `krtr/database/s3/client.py` is tested by
`tests/database/s3/test_client.py`, `krtr/cli/database/s3.py` is tested by
`tests/cli/database/test_s3.py`, and so on. Each directory under `tests/` gets an
`__init__.py` (matching its `krtr/` counterpart) so that same-named test files in
different verticals (e.g. multiple `test_config.py`) don't collide during collection.
See the Testing philosophy section below for what a test in this tree must actually
assert.

## Clean code practices (mandatory)

Every change must follow these practices. Spaghetti code is not acceptable under any
circumstance — if a change starts to require it, stop and refactor instead.

- **Single Responsibility Principle**: a class, function, or method does exactly one thing.
  If it does more, split it.
- **Encapsulation**: keep internal state and implementation details private. Expose only
  what callers need through a minimal, intentional public interface.
- **Documentation**: every class, function, and method is documented per the rules below.
  Code should not need a comment to explain *what* it does if it's documented and named well.
- **DRY / reuse over recreation**: before writing new logic, search the repository for an
  existing utility, helper, or class that already does it (or most of it). Reuse or extend
  existing code instead of rewriting it. Only write new code when nothing suitable exists.
- **Descriptive naming**: names for variables, functions, classes, and modules must state
  their purpose unambiguously. No abbreviations that require guessing.
- **Small, focused functions**: see the 40-line rule below.
- **Separation of concerns**: don't mix unrelated layers (e.g., I/O, business logic, and
  presentation) in the same function or class.
- **Explicit, complete signatures**: see the type-hint rule below.
- **Fail fast, explicit error handling**: validate inputs and raise clear errors close to
  the source of the problem. Never silently swallow exceptions.
- **Avoid deep nesting**: prefer guard clauses and early returns over nested conditionals.
- **No dead code**: no commented-out code, no unused parameters, no speculative
  "just in case" code paths.

## No hardcoded strings or values — use Enums

Never hardcode a "magic" string or value that represents one option out of a known,
fixed set (a mode, a status, a backend name, a stage, a file extension, etc.). Define
an `Enum` (or `StrEnum`) for it instead, and reference the enum member everywhere —
never the raw literal, not even for comparisons or default arguments.

- **Enums must have a docstring**, following the same justification rule as any other
  class: why the set of values exists and where it's consumed.
- **Document non-obvious members**: if a member's meaning isn't self-evident from its
  name, add an inline comment or docstring note explaining it.
- **Enums can drive polymorphic behavior**: an abstract base class with several
  concrete use cases can take an Enum member as a discriminator, and use
  `typing.Literal[...]` (built from the enum's values) or `Annotated` types in its
  signatures so each use case's valid inputs are enforced statically, instead of
  branching on raw strings at runtime.

Example shape:

```python
class DatabaseBackend(str, Enum):
    """The database backends this repository knows how to connect to.

    Used by `krtr/database/` to select which backend-specific client to
    construct, and by the CLI to validate the `--backend` option.
    """

    S3 = "s3"
    SNOWFLAKE = "snowflake"


def get_client(backend: Literal[DatabaseBackend.S3, DatabaseBackend.SNOWFLAKE]) -> Client: ...
```

## No nested functions or methods

Do not define a function inside another function, or a method inside another method.
If logic needs to be factored out, extract it to a module-level function or a private
(`_`-prefixed) method on the class instead. This keeps the resulting helper testable,
reusable, and independent of its former enclosing scope.

## Function and method length: 40-line limit

No function or method body may exceed 40 lines. If implementing a piece of logic would
exceed that limit, extract the excess into one or more private helper methods
(prefixed with `_`) that each encapsulate a single, separate responsibility. The public
method should read as a short, readable sequence of calls to those helpers.

## Complete signatures

Every function and method must have a complete signature: full type hints on every
parameter and on the return type. No untyped or partially typed signatures.

## Docstrings

### Classes

Every class must have a docstring that explains:

1. Why the class exists (the justification/problem it solves).
2. Where it is expected to be consumed (calling module/layer, e.g. "used by the CLI
   entrypoint" or "consumed by the ingestion pipeline").

### `__init__` methods

Every `__init__` must document each constructor parameter (name, type, and purpose).

### Functions and methods (all of them)

Every function and method docstring must contain, in this order:

1. A verb-first summary of what it does (e.g., "Validates...", "Builds...", "Parses...").
2. The justification for why it exists and where it could be useful.
3. `Args`: each parameter with its meaning.
4. `Returns`: what is returned and what it represents.

Example shape:

```python
def parse_config(path: str) -> ConfigModel:
    """Parses a configuration file into a validated ConfigModel.

    Exists to centralize configuration loading so callers never read raw
    config files directly; useful anywhere the app needs typed, validated
    settings (CLI startup, tests, service bootstrap).

    Args:
        path: Filesystem path to the configuration file to load.

    Returns:
        ConfigModel: the parsed and validated configuration.
    """
```

## Pydantic usage

This repository uses `pydantic` (`BaseModel`) for exactly two purposes:

1. **Configuration objects** — belong in a subpackage's `config.py`.
2. **Return contracts for important artifacts** — when a function/method returns a
   meaningful structured result (not a primitive or a trivial internal tuple), define a
   `BaseModel` subclass for it instead of returning a dict/tuple, and use that model as
   the return type in the signature. These belong in a subpackage's `artifacts.py`.

Do not introduce `pydantic` models for internal, throwaway, or purely local data —
plain classes or built-in types are fine there.

## SQL statements live in `.sql` files, never as Python string literals

Never declare a SQL statement (DDL or DML: `CREATE TABLE`, `CREATE INDEX`,
`INSERT`, `SELECT`, ...) as a Python string constant or inline literal,
including in an `artifacts.py`. All SQL text lives in `.sql` files under
`krtr/database/queries/<table>/`, one subdirectory per table:

- `krtr/database/queries/<table>/table.sql` — that table's schema DDL
  (`CREATE TABLE`, its indexes, etc.).
- `krtr/database/queries/<table>/query.sql` — that table's data-manipulation
  query (e.g. the `INSERT` template a loader uses).

Example: the `products` table's DDL lives at
`krtr/database/queries/products/table.sql` and its load query at
`krtr/database/queries/products/query.sql`.

Python code never builds or concatenates SQL strings for these cases; it
reads the `.sql` file (e.g. via `krtr.database.queries.load_sql`) and passes
the text straight to the database client. This keeps SQL reviewable and
editable as SQL, and keeps a table's schema and query in one discoverable
place per table.

Do not create indexes unless the user explicitly asks for them for that
table; a table's `.sql` files ship with no indexes by default.

### SQL docstrings

Every `.sql` file must open with a docstring-style comment block (`--`
lines) explaining, like a Python module docstring, why the file exists and
where it is consumed — and every CTE (`WITH <name> AS (...)`) must have its
own short `--` comment immediately above it explaining what that CTE
computes.

`table.sql` files must additionally document every column: its type and its
business meaning, one `--` line per column, immediately above or beside its
definition. This column documentation must come from the user (or from
existing, user-provided documentation of the table) — never invented or
inferred from the column name alone. If a table's full column documentation
has not been provided, ask the user for it before writing the `table.sql`.

## Logging

Never use `print` for output. All output — status updates, progress, results, errors —
goes through the standard `logging` module.

- Logs should read as a clear, step-by-step narrative of what the code is doing, so a
  reader can follow execution from the log output alone (e.g. "Loading config from
  {path}", "Connecting to {backend}", "Wrote {n} records to {target}").
- Use the appropriate level: `debug` for internal detail, `info` for normal step-by-step
  progress, `warning` for recoverable issues, `error`/`exception` for failures.
- Get a module-scoped logger with `logging.getLogger(__name__)`; do not configure
  logging handlers inside library/vertical code — configuration belongs in the CLI
  entrypoint (`krtr/cli/`).

## Testing philosophy

Tests must verify the actual behavior and intent of the code, not just exercise it.

- Before writing a test, understand what the unit under test is *for* — the problem it
  solves — and write assertions that would fail if that problem were reintroduced.
- Do not write tests with trivial, unuseful assertions (e.g. asserting a function
  merely "runs without error", asserting a mock was called, asserting a value is
  "not None" when a real value could be checked). Assert on concrete expected outcomes.
- Cover the meaningful edge cases and failure modes of the behavior, not just the
  happy path.
- A test that would still pass after the underlying logic is broken is worse than no
  test — it should be rewritten or removed.

## Dependency management: always use `uv`

Never hand-edit `pyproject.toml`'s `dependencies` (or `uv.lock`) to add,
remove, or change the version of a package. Always use `uv` for this
(`uv add <package>`, `uv remove <package>`, `uv add --upgrade-package
<package>`, etc.), so `pyproject.toml` and `uv.lock` stay resolved and
consistent. If `uv` is not installed in the working environment, install it
first rather than falling back to a manual edit.

## Commit messages

Commits must follow Conventional Commits: `<type>(<scope>): <description>`.

- `type` is one of: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `ci`, `style`,
  `perf`.
- `scope` is the vertical or area the change touches (e.g. `database`, `cli`,
  `database/s3`).
- `description` is a short, imperative summary (e.g. "add", not "added"/"adds").

Example: `feat(database/snowflake): add connection pooling`.

## Downloaded datasets

All downloaded datasets must be saved under `C:\Users\pcaba\krtr\data` (the `data/` directory
at the repo root). Use it as the `local_path` whenever downloading data (e.g. from S3) instead
of any other location.
