# CHANGELOG

<!-- version list -->

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
