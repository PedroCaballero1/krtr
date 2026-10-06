# CHANGELOG

<!-- version list -->

## v1.8.0 (2026-10-06)

### Bug Fixes

- **back/ia/matching**: Ship the evaluation set outside an ignored data folder
  ([#14](https://github.com/PedroCaballero1/krtr/pull/14),
  [`6adf2ac`](https://github.com/PedroCaballero1/krtr/commit/6adf2acf845e061087ab291f3a598f515b7a356d))

### Features

- **back/ia**: Select models by Enum, add MiniLM and measured thresholds
  ([#14](https://github.com/PedroCaballero1/krtr/pull/14),
  [`6adf2ac`](https://github.com/PedroCaballero1/krtr/commit/6adf2acf845e061087ab291f3a598f515b7a356d))


## v1.7.0 (2026-10-06)

### Documentation

- **repo**: Define the messages table for chat text
  ([#13](https://github.com/PedroCaballero1/krtr/pull/13),
  [`ed16f5e`](https://github.com/PedroCaballero1/krtr/commit/ed16f5e067feefb53632140e470c76242c66c5b3))

### Features

- **back/ia**: Add deterministic conversation engine and krtr back ia CLI
  ([#13](https://github.com/PedroCaballero1/krtr/pull/13),
  [`ed16f5e`](https://github.com/PedroCaballero1/krtr/commit/ed16f5e067feefb53632140e470c76242c66c5b3))

- **back/ia/language**: Detect the reply language per conversation
  ([#13](https://github.com/PedroCaballero1/krtr/pull/13),
  [`ed16f5e`](https://github.com/PedroCaballero1/krtr/commit/ed16f5e067feefb53632140e470c76242c66c5b3))

- **back/ia/messages**: Store chat messages and replies, encrypted
  ([#13](https://github.com/PedroCaballero1/krtr/pull/13),
  [`ed16f5e`](https://github.com/PedroCaballero1/krtr/commit/ed16f5e067feefb53632140e470c76242c66c5b3))


## v1.6.0 (2026-10-05)

### Bug Fixes

- **front**: Serve favicon from assets ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **front**: Vendor shadcn's tailwind.css and drop the shadcn package
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **front/api**: Remove temporary demo mocks
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

### Chores

- **deploy/gcp**: Add registry, service account and secret setup script
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **repo**: Add application container image ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **repo**: Add web and security dependencies
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **repo**: Remove Google Cloud deployment artifacts
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **repo**: Scaffold back and front verticals
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

### Code Style

- **front**: Fix react-refresh lint warning ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

### Continuous Integration

- **repo**: Install the modal extra in lint-and-test
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **security**: Add static and dependency scanning
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

### Documentation

- **back/deploy**: Record Modal platform behaviour
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **repo**: Add frontend rules to CLAUDE.md ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **repo**: Add Modal deploy rules to CLAUDE.md
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **repo**: Add Modal version of the web and security guide
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **repo**: Add pending work for phase 7 ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **repo**: Add pending work for phases 5 and 6
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **repo**: Approve the new decisions and add production tables to 1.3
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **repo**: Drop Cloud Run references ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **repo**: Mark demo mock removal as done ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **repo**: Pin the Modal workspace and record task 0.4 in the guide
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **repo**: Point guide references to the Modal guide
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **repo**: Record task 3.2 in the guide ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **repo**: Record tasks 0.5 and 3.1 in the guide
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **repo**: Record tasks 4.11, 5.11 and 5.12 in the guide
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **repo**: Record tasks 4.3 and 4.4 in the guide
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **repo**: Record the Docker and Neon setup of tasks 1.1 and 1.3
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **repo**: Record the status of tasks 0.1, 1.1 and 1.3 in the guide
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **repo**: Update the Modal guide after the phase 0 review
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

### Features

- **back/deploy**: Add the Keycloak image for Modal
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **back/security/audit**: Add encrypted event logging
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **back/security/crypto**: Add a separate key for OIDC tokens
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **back/security/headers**: Add security headers middleware
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **back/security/keycloak**: Add a local test user command and document local login
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **back/security/keycloak**: Add krtr realm configuration
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **back/security/keycloak**: Run Keycloak locally on Neon dev
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **back/security/oidc**: Add OIDC login flow
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **back/security/sessions**: Add server-side sessions
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **back/web**: Add FastAPI application skeleton
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **back/web**: Add login and session endpoints
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **back/web**: Record events in the served app
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **database/neon**: Add pooled parameterized queries
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **database/neon**: Return the affected row count from execute_params
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **database/queries/app_sessions**: Add session table and queries
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **database/queries/events**: Add events table and queries
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **front**: Apply krtr visual design to phase 5 screens
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **front**: Instrument UI events ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **front**: Scaffold React application ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **front/api**: Add API client and event tracking
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **front/cases**: Add case selection ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **front/chat**: Add chat view with typing indicator
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **front/chat**: Add voice note recording ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **front/home**: Add authenticated home ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **front/i18n**: Add Spanish and Portuguese
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **front/landing**: Add login landing page ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

- **front/session**: Add inactivity and absolute timeout handling
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))

### Testing

- **front/pages**: Wait for the typing indicator to clear
  ([#11](https://github.com/PedroCaballero1/krtr/pull/11),
  [`d777576`](https://github.com/PedroCaballero1/krtr/commit/d777576109c93c7052afde266ebab493e8e5e87a))


## v1.5.0 (2026-10-02)

### Chores

- **deploy/gcp**: Add registry, service account and secret setup script
  ([#9](https://github.com/PedroCaballero1/krtr/pull/9),
  [`c2b7892`](https://github.com/PedroCaballero1/krtr/commit/c2b78928c176150a80d098ff7065a539529139e2))

- **repo**: Add application container image ([#9](https://github.com/PedroCaballero1/krtr/pull/9),
  [`c2b7892`](https://github.com/PedroCaballero1/krtr/commit/c2b78928c176150a80d098ff7065a539529139e2))

- **repo**: Add web and security dependencies ([#9](https://github.com/PedroCaballero1/krtr/pull/9),
  [`c2b7892`](https://github.com/PedroCaballero1/krtr/commit/c2b78928c176150a80d098ff7065a539529139e2))

- **repo**: Scaffold back and front verticals ([#9](https://github.com/PedroCaballero1/krtr/pull/9),
  [`c2b7892`](https://github.com/PedroCaballero1/krtr/commit/c2b78928c176150a80d098ff7065a539529139e2))

### Documentation

- **repo**: Add frontend rules to CLAUDE.md ([#9](https://github.com/PedroCaballero1/krtr/pull/9),
  [`c2b7892`](https://github.com/PedroCaballero1/krtr/commit/c2b78928c176150a80d098ff7065a539529139e2))

- **repo**: Add pending work for phases 5 and 6
  ([#9](https://github.com/PedroCaballero1/krtr/pull/9),
  [`c2b7892`](https://github.com/PedroCaballero1/krtr/commit/c2b78928c176150a80d098ff7065a539529139e2))

- **Web & Security**: Add plan ([#8](https://github.com/PedroCaballero1/krtr/pull/8),
  [`970072a`](https://github.com/PedroCaballero1/krtr/commit/970072ad90042542d7f19a40e4be3cbd6608ccb9))

### Features

- **back/security/audit**: Add encrypted event logging
  ([#9](https://github.com/PedroCaballero1/krtr/pull/9),
  [`c2b7892`](https://github.com/PedroCaballero1/krtr/commit/c2b78928c176150a80d098ff7065a539529139e2))

- **back/security/headers**: Add security headers middleware
  ([#9](https://github.com/PedroCaballero1/krtr/pull/9),
  [`c2b7892`](https://github.com/PedroCaballero1/krtr/commit/c2b78928c176150a80d098ff7065a539529139e2))

- **back/web**: Add FastAPI application skeleton
  ([#9](https://github.com/PedroCaballero1/krtr/pull/9),
  [`c2b7892`](https://github.com/PedroCaballero1/krtr/commit/c2b78928c176150a80d098ff7065a539529139e2))

- **database/neon**: Add pooled parameterized queries
  ([#9](https://github.com/PedroCaballero1/krtr/pull/9),
  [`c2b7892`](https://github.com/PedroCaballero1/krtr/commit/c2b78928c176150a80d098ff7065a539529139e2))

- **database/queries/app_sessions**: Add session table and queries
  ([#9](https://github.com/PedroCaballero1/krtr/pull/9),
  [`c2b7892`](https://github.com/PedroCaballero1/krtr/commit/c2b78928c176150a80d098ff7065a539529139e2))

- **database/queries/events**: Add events table and queries
  ([#9](https://github.com/PedroCaballero1/krtr/pull/9),
  [`c2b7892`](https://github.com/PedroCaballero1/krtr/commit/c2b78928c176150a80d098ff7065a539529139e2))

- **front**: Apply krtr visual design to phase 5 screens
  ([#9](https://github.com/PedroCaballero1/krtr/pull/9),
  [`c2b7892`](https://github.com/PedroCaballero1/krtr/commit/c2b78928c176150a80d098ff7065a539529139e2))

- **front**: Instrument UI events ([#9](https://github.com/PedroCaballero1/krtr/pull/9),
  [`c2b7892`](https://github.com/PedroCaballero1/krtr/commit/c2b78928c176150a80d098ff7065a539529139e2))

- **front**: Scaffold React application ([#9](https://github.com/PedroCaballero1/krtr/pull/9),
  [`c2b7892`](https://github.com/PedroCaballero1/krtr/commit/c2b78928c176150a80d098ff7065a539529139e2))

- **front/api**: Add API client and event tracking
  ([#9](https://github.com/PedroCaballero1/krtr/pull/9),
  [`c2b7892`](https://github.com/PedroCaballero1/krtr/commit/c2b78928c176150a80d098ff7065a539529139e2))

- **front/cases**: Add case selection ([#9](https://github.com/PedroCaballero1/krtr/pull/9),
  [`c2b7892`](https://github.com/PedroCaballero1/krtr/commit/c2b78928c176150a80d098ff7065a539529139e2))

- **front/chat**: Add chat view with typing indicator
  ([#9](https://github.com/PedroCaballero1/krtr/pull/9),
  [`c2b7892`](https://github.com/PedroCaballero1/krtr/commit/c2b78928c176150a80d098ff7065a539529139e2))

- **front/chat**: Add voice note recording ([#9](https://github.com/PedroCaballero1/krtr/pull/9),
  [`c2b7892`](https://github.com/PedroCaballero1/krtr/commit/c2b78928c176150a80d098ff7065a539529139e2))

- **front/home**: Add authenticated home ([#9](https://github.com/PedroCaballero1/krtr/pull/9),
  [`c2b7892`](https://github.com/PedroCaballero1/krtr/commit/c2b78928c176150a80d098ff7065a539529139e2))

- **front/i18n**: Add Spanish and Portuguese ([#9](https://github.com/PedroCaballero1/krtr/pull/9),
  [`c2b7892`](https://github.com/PedroCaballero1/krtr/commit/c2b78928c176150a80d098ff7065a539529139e2))

- **front/landing**: Add login landing page ([#9](https://github.com/PedroCaballero1/krtr/pull/9),
  [`c2b7892`](https://github.com/PedroCaballero1/krtr/commit/c2b78928c176150a80d098ff7065a539529139e2))

- **front/session**: Add inactivity and absolute timeout handling
  ([#9](https://github.com/PedroCaballero1/krtr/pull/9),
  [`c2b7892`](https://github.com/PedroCaballero1/krtr/commit/c2b78928c176150a80d098ff7065a539529139e2))


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
