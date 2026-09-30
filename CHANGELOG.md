# CHANGELOG

<!-- version list -->

## v1.4.0 (2026-09-30)

### Bug Fixes

- **compute/modal**: Do not stream logs on --detach so the CLI returns at once
  ([#6](https://github.com/PedroCaballero1/krtr/pull/6),
  [`286b7c1`](https://github.com/PedroCaballero1/krtr/commit/286b7c13ce1b98703b7e4641a2d3a0f276997814))

- **compute/modal**: Load .env before reading the Modal token
  ([#6](https://github.com/PedroCaballero1/krtr/pull/6),
  [`286b7c1`](https://github.com/PedroCaballero1/krtr/commit/286b7c13ce1b98703b7e4641a2d3a0f276997814))

- **database/neon**: Load products fully and in one round trip per batch
  ([#6](https://github.com/PedroCaballero1/krtr/pull/6),
  [`286b7c1`](https://github.com/PedroCaballero1/krtr/commit/286b7c13ce1b98703b7e4641a2d3a0f276997814))

- **database/neon**: Load products fully and in one round trip per batch
  ([#3](https://github.com/PedroCaballero1/krtr/pull/3),
  [`2a08a19`](https://github.com/PedroCaballero1/krtr/commit/2a08a198fad6563e6c59daa8e0795ff9cb668e40))

- **database/queries/products**: Remove non-existent foreign key constraints
  ([#6](https://github.com/PedroCaballero1/krtr/pull/6),
  [`286b7c1`](https://github.com/PedroCaballero1/krtr/commit/286b7c13ce1b98703b7e4641a2d3a0f276997814))

- **database/queries/products**: Remove non-existent foreign key constraints
  ([#3](https://github.com/PedroCaballero1/krtr/pull/3),
  [`2a08a19`](https://github.com/PedroCaballero1/krtr/commit/2a08a198fad6563e6c59daa8e0795ff9cb668e40))

### Chores

- **compute/modal**: Add modal optional dependency and conventions
  ([#6](https://github.com/PedroCaballero1/krtr/pull/6),
  [`286b7c1`](https://github.com/PedroCaballero1/krtr/commit/286b7c13ce1b98703b7e4641a2d3a0f276997814))

- **repo**: Stop tracking bytecode and add a test that keeps it out
  ([#6](https://github.com/PedroCaballero1/krtr/pull/6),
  [`286b7c1`](https://github.com/PedroCaballero1/krtr/commit/286b7c13ce1b98703b7e4641a2d3a0f276997814))

### Continuous Integration

- Re-run checks on the fixed uv.lock ([#6](https://github.com/PedroCaballero1/krtr/pull/6),
  [`286b7c1`](https://github.com/PedroCaballero1/krtr/commit/286b7c13ce1b98703b7e4641a2d3a0f276997814))

### Documentation

- **cli/database/neon**: Add usage examples to the load command docstring
  ([#3](https://github.com/PedroCaballero1/krtr/pull/3),
  [`2a08a19`](https://github.com/PedroCaballero1/krtr/commit/2a08a198fad6563e6c59daa8e0795ff9cb668e40))

- **compute/modal**: Document remote execution workflow
  ([#6](https://github.com/PedroCaballero1/krtr/pull/6),
  [`286b7c1`](https://github.com/PedroCaballero1/krtr/commit/286b7c13ce1b98703b7e4641a2d3a0f276997814))

- **compute/modal**: Keep empty Modal variables commented in .env.example
  ([#6](https://github.com/PedroCaballero1/krtr/pull/6),
  [`286b7c1`](https://github.com/PedroCaballero1/krtr/commit/286b7c13ce1b98703b7e4641a2d3a0f276997814))

- **goals**: Add goals document ([#7](https://github.com/PedroCaballero1/krtr/pull/7),
  [`7be5632`](https://github.com/PedroCaballero1/krtr/commit/7be56328d8a2d99cde2de651babff7c3ea0b722e))

### Features

- **cli/compute/modal**: Add modal commands and remote option for neon load
  ([#6](https://github.com/PedroCaballero1/krtr/pull/6),
  [`286b7c1`](https://github.com/PedroCaballero1/krtr/commit/286b7c13ce1b98703b7e4641a2d3a0f276997814))

- **cli/database/neon**: Add --remote and --detach to load
  ([#6](https://github.com/PedroCaballero1/krtr/pull/6),
  [`286b7c1`](https://github.com/PedroCaballero1/krtr/commit/286b7c13ce1b98703b7e4641a2d3a0f276997814))

- **compute/modal**: Add config, enums and artifacts
  ([#6](https://github.com/PedroCaballero1/krtr/pull/6),
  [`286b7c1`](https://github.com/PedroCaballero1/krtr/commit/286b7c13ce1b98703b7e4641a2d3a0f276997814))

- **compute/modal**: Add file staging to volume
  ([#6](https://github.com/PedroCaballero1/krtr/pull/6),
  [`286b7c1`](https://github.com/PedroCaballero1/krtr/commit/286b7c13ce1b98703b7e4641a2d3a0f276997814))

- **compute/modal**: Add local run registry ([#6](https://github.com/PedroCaballero1/krtr/pull/6),
  [`286b7c1`](https://github.com/PedroCaballero1/krtr/commit/286b7c13ce1b98703b7e4641a2d3a0f276997814))

- **compute/modal**: Add modal app, image and remote entrypoint
  ([#6](https://github.com/PedroCaballero1/krtr/pull/6),
  [`286b7c1`](https://github.com/PedroCaballero1/krtr/commit/286b7c13ce1b98703b7e4641a2d3a0f276997814))

- **compute/modal**: Add remote task registry ([#6](https://github.com/PedroCaballero1/krtr/pull/6),
  [`286b7c1`](https://github.com/PedroCaballero1/krtr/commit/286b7c13ce1b98703b7e4641a2d3a0f276997814))

- **compute/modal**: Add secret sync and environment doctor
  ([#6](https://github.com/PedroCaballero1/krtr/pull/6),
  [`286b7c1`](https://github.com/PedroCaballero1/krtr/commit/286b7c13ce1b98703b7e4641a2d3a0f276997814))

- **compute/modal**: Add task runner with local, remote and detached modes
  ([#6](https://github.com/PedroCaballero1/krtr/pull/6),
  [`286b7c1`](https://github.com/PedroCaballero1/krtr/commit/286b7c13ce1b98703b7e4641a2d3a0f276997814))

- **database/neon**: Add table-generic Neon Postgres schema creation and loading
  ([#6](https://github.com/PedroCaballero1/krtr/pull/6),
  [`286b7c1`](https://github.com/PedroCaballero1/krtr/commit/286b7c13ce1b98703b7e4641a2d3a0f276997814))

- **database/neon**: Add table-generic Neon Postgres schema creation and loading
  ([#3](https://github.com/PedroCaballero1/krtr/pull/3),
  [`2a08a19`](https://github.com/PedroCaballero1/krtr/commit/2a08a198fad6563e6c59daa8e0795ff9cb668e40))

- **database/queries/daily_exchange_rates**: Add table and insert SQL
  ([#6](https://github.com/PedroCaballero1/krtr/pull/6),
  [`286b7c1`](https://github.com/PedroCaballero1/krtr/commit/286b7c13ce1b98703b7e4641a2d3a0f276997814))

- **eda**: Add physical places (branches) hypothesis analysis
  ([#5](https://github.com/PedroCaballero1/krtr/pull/5),
  [`e1bf39e`](https://github.com/PedroCaballero1/krtr/commit/e1bf39ee29c981dad74869e4e721c43213ced214))

- **eda**: Quantify user value, churn cost and survey reasons
  ([#5](https://github.com/PedroCaballero1/krtr/pull/5),
  [`e1bf39e`](https://github.com/PedroCaballero1/krtr/commit/e1bf39ee29c981dad74869e4e721c43213ced214))

- **eda/compensations**: Analyse reasons behind low ratings and their cost
  ([#5](https://github.com/PedroCaballero1/krtr/pull/5),
  [`e1bf39e`](https://github.com/PedroCaballero1/krtr/commit/e1bf39ee29c981dad74869e4e721c43213ced214))

- **eda/physical-places**: Add capacity and human-handled job-pool analysis
  ([#5](https://github.com/PedroCaballero1/krtr/pull/5),
  [`e1bf39e`](https://github.com/PedroCaballero1/krtr/commit/e1bf39ee29c981dad74869e4e721c43213ced214))

### Performance Improvements

- **compute/modal**: Default remote tasks to 0.25 CPU and 512 MiB, no GPU
  ([#6](https://github.com/PedroCaballero1/krtr/pull/6),
  [`286b7c1`](https://github.com/PedroCaballero1/krtr/commit/286b7c13ce1b98703b7e4641a2d3a0f276997814))

### Refactoring

- **database/neon**: Extract load orchestration from CLI handler
  ([#6](https://github.com/PedroCaballero1/krtr/pull/6),
  [`286b7c1`](https://github.com/PedroCaballero1/krtr/commit/286b7c13ce1b98703b7e4641a2d3a0f276997814))


## v1.3.0 (2026-09-26)

### Chores

- **deps**: Add pandas and matplotlib as dev dependencies and notebook
  ([#4](https://github.com/PedroCaballero1/krtr/pull/4),
  [`623c83e`](https://github.com/PedroCaballero1/krtr/commit/623c83e8bed241824aae8f9f3a317a090a96fb65))

### Features

- **eda**: Add delinquency and complaints hypothesis analyses
  ([#4](https://github.com/PedroCaballero1/krtr/pull/4),
  [`623c83e`](https://github.com/PedroCaballero1/krtr/commit/623c83e8bed241824aae8f9f3a317a090a96fb65))


## v1.2.0 (2026-09-26)

### Bug Fixes

- **repo**: Sync uv.lock with the released version and keep it in sync
  ([#2](https://github.com/PedroCaballero1/krtr/pull/2),
  [`72636af`](https://github.com/PedroCaballero1/krtr/commit/72636af243b67953958fe0140146449fe0dc810a))

### Features

- **database/s3**: Add dataset catalog and date-range downloads
  ([#2](https://github.com/PedroCaballero1/krtr/pull/2),
  [`72636af`](https://github.com/PedroCaballero1/krtr/commit/72636af243b67953958fe0140146449fe0dc810a))

- **database/s3**: Add list_files method and list-files CLI command
  ([#2](https://github.com/PedroCaballero1/krtr/pull/2),
  [`72636af`](https://github.com/PedroCaballero1/krtr/commit/72636af243b67953958fe0140146449fe0dc810a))

- **database/s3**: Add S3 client and download CLI commands
  ([#2](https://github.com/PedroCaballero1/krtr/pull/2),
  [`72636af`](https://github.com/PedroCaballero1/krtr/commit/72636af243b67953958fe0140146449fe0dc810a))

- **database/s3**: Default to the bucket from BUCKET_NAME
  ([#2](https://github.com/PedroCaballero1/krtr/pull/2),
  [`72636af`](https://github.com/PedroCaballero1/krtr/commit/72636af243b67953958fe0140146449fe0dc810a))


## v1.1.0 (2026-09-26)

### Features

- **repo**: Add isort dependency
  ([`4211423`](https://github.com/PedroCaballero1/krtr/commit/4211423190c8314f0f93b46f7b4f67c475ded881))


## v1.0.2 (2026-09-24)

### Bug Fixes

- **changelog**: Restore the version-list insertion marker
  ([`4dd6a3d`](https://github.com/PedroCaballero1/krtr/commit/4dd6a3d4b53b9bd3f28f4758462f49438f3debb7))


## v1.0.0 (2026-09-24)

### Chores

- **repo**: Add lint/format tooling, CI, and CLAUDE.md conventions
  ([#1](https://github.com/PedroCaballero1/krtr/pull/1),
  [`ebf27d2`](https://github.com/PedroCaballero1/krtr/commit/ebf27d216bebfaa227afd585fd50b0c3998b0571))

### Continuous Integration

- Scope lint and test steps to krtr/krtr ([#1](https://github.com/PedroCaballero1/krtr/pull/1),
  [`ebf27d2`](https://github.com/PedroCaballero1/krtr/commit/ebf27d216bebfaa227afd585fd50b0c3998b0571))

- **release**: Add automated semantic-release versioning and tagging
  ([`786690f`](https://github.com/PedroCaballero1/krtr/commit/786690f3126afe4b4d3e08a999d8490249b898e2))

### Features

- **cli**: Implement root Typer app and mirror its structure in tests
  ([#1](https://github.com/PedroCaballero1/krtr/pull/1),
  [`ebf27d2`](https://github.com/PedroCaballero1/krtr/commit/ebf27d216bebfaa227afd585fd50b0c3998b0571))
