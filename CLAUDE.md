# CLAUDE.md

Guidance for Claude Code when writing or modifying code in this repository.

## Project structure

`krtr/krtr/` is organized as **vertical slices**, not by technical layer: each
subdirectory is a single, self-contained concept, and further nesting narrows that
concept into concrete implementations. This is encapsulation and Single Responsibility
applied at the package level — a vertical should be understandable, testable, and
replaceable without touching unrelated verticals.

Example: `krtr/krtr/database/` is the "database" concept; each backend gets its own
sub-vertical: `krtr/krtr/database/s3/`, `krtr/krtr/database/snowflake/`. Shared
database-wide contracts/config live in `database/`; backend-specific logic stays inside
its own backend directory and does not leak into siblings.

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
input, call into the relevant vertical under `krtr/krtr/`, and present the result.
Business logic belongs in the vertical package it concerns, not in the CLI layer.

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

    Used by `krtr/krtr/database/` to select which backend-specific client to
    construct, and by the CLI to validate the `--backend` option.
    """

    S3 = "s3"
    SNOWFLAKE = "snowflake"


def get_client(backend: Literal[DatabaseBackend.S3, DatabaseBackend.SNOWFLAKE]) -> Client:
    ...
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

## Commit messages

Commits must follow Conventional Commits: `<type>(<scope>): <description>`.

- `type` is one of: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `ci`, `style`,
  `perf`.
- `scope` is the vertical or area the change touches (e.g. `database`, `cli`,
  `database/s3`).
- `description` is a short, imperative summary (e.g. "add", not "added"/"adds").

Example: `feat(database/snowflake): add connection pooling`.
