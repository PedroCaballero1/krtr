# krtr

## Cómo inicializar

Requisitos previos: Python 3.13+ and [uv](https://docs.astral.sh/uv/).

1. Instalar dependencias:

   ```bash
   uv sync
   ```

2. Copiar `.env.example` a `.env` y completar las variables que necesites (ver
   [S3 downloads](#s3-downloads) y [Neon Postgres](#neon-postgres) más abajo
   para el detalle de cada una). Nunca commitear `.env` (ya está en
   `.gitignore`).

3. Correr cualquier comando `krtr ...` (o `uv run krtr ...` si no activaste el
   virtualenv) desde la raíz del repo; `.env` se carga automáticamente.

La carpeta `data/` (en la raíz del repo, también ignorada por git) es donde
se guardan y buscan por defecto los archivos descargados/cargados: listados y
catálogos de S3, y los `.parquet`/`.csv` que carga `krtr database neon load`.

## Probar la página en local (con login)

Levanta krtr-web en http://localhost:8000 con el login real: Keycloak en Docker y las sesiones
en la rama `dev` de Neon. Detalle en [`docs/guia-web-seguridad_modal.md`](docs/guia-web-seguridad_modal.md).

Requisitos:

- Docker (en Mac, Colima) y Node.
- En `.env` (ver `.env.example`; pide los valores al equipo): `NEON_DEV_DB_HOST`,
  `NEON_DEV_DIRECT_HOST`, `KRTR_KEYCLOAK_DB_PASSWORD`, `KRTR_KEYCLOAK_ADMIN_PASSWORD`,
  `KRTR_WEB_OIDC_CLIENT_SECRET` y `KRTR_TOKENS_KEY`.

1. Levantar Keycloak (la primera vez tarda unos minutos):

   ```bash
   docker compose --env-file .env -f krtr/back/security/keycloak/docker-compose.yml up -d
   curl -s http://localhost:9000/health/ready   # listo cuando responde "UP"
   ```

2. Compilar el frontend:

   ```bash
   (cd krtr/front && npm ci && npm run build)
   ```

3. Levantar krtr-web contra la rama `dev` de Neon:

   ```bash
   uv run --env-file .env sh -c 'NEON_DB_HOST="$NEON_DEV_DB_HOST" KRTR_WEB_ENVIRONMENT=development krtr back web serve --host 127.0.0.1'
   ```

4. Crear el usuario de prueba. En otra terminal:

   ```bash
   uv run krtr back security keycloak test-user
   ```

   Muestra el usuario (`99999999`) y una **contraseña nueva** cada vez que se corre. La
   contraseña no está escrita en ningún lado del repo.

5. Abrir http://localhost:8000 en **Chrome o Firefox**, elegir idioma y entrar con ese usuario
   y contraseña. Safari no guarda la cookie de sesión en `http://localhost`, así que el login
   parece no hacer nada.

6. Al terminar:

   ```bash
   uv run krtr back security keycloak test-user --delete
   docker compose --env-file .env -f krtr/back/security/keycloak/docker-compose.yml down
   ```

Ten en cuenta:

- Keycloak guarda sus datos en la rama `dev` de Neon, así que el usuario de prueba es **el mismo
  para todo el equipo**. Si alguien vuelve a correr `test-user`, la contraseña anterior deja de
  servir y las sesiones abiertas se cierran.
- La sesión se cierra tras 5 minutos sin actividad o 30 minutos desde el login, y solo puede
  haber una sesión abierta por usuario.
- El chat responde con el motor de IA, leyendo la rama `dev`. Sin `KRTR_MESSAGES_KEY`, los
  mensajes quedan solo en memoria; sin `NEON_DB_HOST`, responde el mensaje genérico de D15.
- El contrato entre el frontend y el backend está en [`docs/api.md`](docs/api.md).

## Producción en Modal (krtr-web)

La página vive en Modal, en el workspace `juan-alvarezo-2002` (ver `docs/guia-web-seguridad_modal.md`, fase 6):

- App: https://juan-alvarezo-2002--krtr.modal.run
- Keycloak: https://juan-alvarezo-2002--krtr-auth.modal.run (con `/admin`, `/realms/master`, `/metrics` y `/health*` bloqueados)

Todos los comandos se corren desde la raíz del repo, con el extra `modal` instalado (`uv sync --extra modal`):

```bash
# 1. Secretos (krtr-web, krtr-auth, krtr-jobs) desde .env; genera la primera vez la
#    contraseña del admin de Keycloak y el secreto del cliente OIDC de producción
uv run --env-file .env krtr back deploy push-secrets

# 2. Front compilado + despliegue. Siempre como módulo (-m), no por ruta.
#    KRTR_WARM=true deja un contenedor de cada servicio siempre encendido (modo demo, D17)
npm --prefix krtr/front run build
KRTR_WARM=true uv run --env-file .env modal deploy -m krtr.back.deploy.app

# 3. Credenciales (una sola vez): 150.000 cuentas, más las muestras del jurado y de QA
uv run krtr back security credentials generate
#    Importarlas a producción: primero desplegar con KRTR_WARM=false para que `auth` se
#    apague, y no abrir krtr-auth mientras corre (tarda unos 20-50 minutos)
uv run --env-file .env krtr back security credentials import --remote

# 4. Pruebas de seguridad contra producción (usa las cuentas QA)
uv run pytest e2e/security
```

- Las credenciales quedan en `data/credentials/` (fuera de git, permisos `600`). `jury_credentials.csv` se entrega al jurado por un canal privado.
- La purga diaria (`purge_events`, 03:00 COT) borra eventos y mensajes de más de 3 meses. Para correrla a mano: `uv run --env-file .env modal run -m krtr.back.deploy.app::purge_events`.
- Cada despliegue reinicia Keycloak (unos 30 s sin login): no desplegar durante la evaluación.
- Desde la tarea 6.7, el despliegue lo hace GitHub Actions con cada merge a `master` que pasa el CI (`.github/workflows/deploy.yml`). El modo demo se controla con la variable del repositorio `KRTR_WARM`. Los pasos 1 y 2 de arriba quedan para la puesta en marcha y para emergencias.
- Cómo operar producción (desplegar, modo demo, rotar secretos, reimportar usuarios, desbloquear cuentas, purga): [`docs/runbook.md`](docs/runbook.md). El gasto diario se registra en [`docs/modal-platform.md`](docs/modal-platform.md#registro-de-gasto-diario).

## Conversation agent (`krtr back ia`)

`krtr/back/ia/` is the agent that answers customer messages. It tries to land every message
on a deterministic answer: it matches the message against example phrases per intent, fills
the details the answer needs with rules, and asks the customer when something is unclear. It
always answers from ES / PT templates, never with free text. See `docs/ia-proposal.md` for
the design.

Phase 1 runs on sample data for one demo customer (`CUST-DEMO`), held in memory, so it needs
no `.env`, no Neon and no model. It understands two intents for now: a product's balance and
a complaint's status.

### Asking one message

```bash
uv run krtr back ia ask "Necesito consultar el saldo de mi tarjeta de crédito"
# [resolved · 0.6 ms] Saldo de tarjeta de crédito:
# - ****9921: saldo 812,300.00 COP, cupo 5,000,000.00 COP

# Start in Portuguese (the interface's language, before any clear message)
uv run krtr back ia ask "saldo da minha conta poupança" --language pt-BR
# [resolved · 0.6 ms] Saldo de conta poupança:
# - ****7781: 2,350,400.50 COP

uv run krtr back ia ask "estado de mi queja PQR-104233"
# [resolved · 0.6 ms] Tu caso PQR-104233 (comisiones), abierto el 2026-09-14, está en estado: en proceso.

# No --language needed: the reply follows the language the message is written in
uv run krtr back ia ask "Preciso consultar o saldo do meu cartão de crédito"
# [resolved · 0.6 ms] Saldo de cartão de crédito:
# - ****9921: saldo 812,300.00 COP, limite 5,000,000.00 COP
```

Each reply starts with how the turn ended — `resolved`, `needs_clarification`, `escalated`
(handed to a human) or `closed` (a hard rule ended it) — and how long the turn took.

### Holding a conversation

`chat` keeps the conversation going, so a question and its answer are two turns of the same
case. Type `/exit` to leave; the chat also stops by itself when the case is escalated or closed.

```bash
uv run krtr back ia chat
> ¿Cuál es mi saldo?
[needs_clarification · 0.6 ms] ¿Sobre qué producto? Responde con el número:
1. cuenta de ahorros
2. cuenta corriente
3. tarjeta de crédito
...
> 1
[resolved · 0.6 ms] Saldo de cuenta de ahorros:
- ****7781: 2,350,400.50 COP
> ¿Cómo va mi reclamo?
[needs_clarification · 0.6 ms] Por favor, indícame el número de caso.
> pqr-104233
[resolved · 0.6 ms] Tu caso PQR-104233 (comisiones), abierto el 2026-09-14, está en estado: en proceso.
> /exit
```

Other flows worth trying in `chat`:

- **A message that matches no intent** (e.g. `xyz`): the agent asks you to rephrase. After 3
  questions in a row, the 4th turn escalates the case to a human.
- **The same message 3 times** (e.g. `hola banco`): the conversation is closed.
- **A message after an escalation or a closure:** the agent says the conversation has ended.

### Language

The agent detects the language each conversation is written in (ES or PT) and replies in it.
`--language es` (the default) or `--language pt-BR` is only the starting language, the way the
web interface's selector will be.

- **What sets the language.** A message of at least 3 words, detected with at least 80%
  confidence (py3langid, offline), sets it for the conversation.
- **What never changes it.** Short replies such as `1`, `saldo` or `PQR-104233`. A Portuguese
  conversation stays in Portuguese while the customer picks options.
- **Switching.** A later clear sentence in the other language switches the replies.

```bash
uv run krtr back ia chat
> Quero saber o status da minha reclamação
[needs_clarification · 0.6 ms] Por favor, informe o número do caso.
> pqr-104233
[resolved · 0.6 ms] Seu caso PQR-104233 (tarifas), aberto em 2026-09-14, está com status: em andamento.
> Ahora quiero saber el saldo de mi cuenta de ahorros
[resolved · 0.6 ms] Saldo de cuenta de ahorros:
- ****7781: 2,350,400.50 COP
```

### Latency

Every reply carries its latency (`AgentReply.timings`): the total and each step of the turn —
language, guardrails, embedding, matching, resolution, action, writing — in milliseconds. The
CLI shows the total next to the outcome; `--verbose` logs the steps:

```bash
uv run krtr --verbose back ia ask "¿Cuál es mi saldo?"
# ... INFO  ... Incident INC-DEMO turn ended as needs_clarification in 0.53 ms
# ... DEBUG ... Incident INC-DEMO step durations (ms): language 0.18, guardrails 0.01,
#     embedding 0.04, matching 0.10, resolution 0.04, action 0.02, writing 0.01
```

Today's sub-millisecond turns come from the hashing embedder and in-memory data. The real
multilingual model (phase 2), Neon reads and the LLM clarifier (phase 3) are what the < 1 s
target (G16) will be measured against.

Add `--verbose` before
`back` (`uv run krtr --verbose back ia chat`) to see each step of the turn in the log.

### Current limits

- **Spelling, not meaning.** The matcher compares spelling (character trigrams), not meaning,
  until the local multilingual model arrives in phase 2. A message worded far from the example
  phrases may therefore be asked about instead of answered.
- **Seed phrases.** The example phrases (`krtr/back/ia/matching/exemplars/<language>/<intent>.txt`,
  one per line) are a small seed set.
- **Provisional complaint ID format.** The format is provisional
  (`krtr/back/ia/deterministic/config.py`).

## S3 downloads

`krtr` can download a single file or a whole "directory" (key prefix) from S3.

### Credentials

Credentials are read from environment variables, optionally loaded from a `.env` file in the
working directory (do not commit it).

To set them up:

1. Copy the example file to `.env`:

   ```bash
   cp .env.example .env        # Windows PowerShell: Copy-Item .env.example .env
   ```

2. Open `.env` and replace the placeholder values with your own keys. Only
   `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are required; leave the optional ones empty
   if you don't need them.
3. Run any `krtr database s3 ...` command from the same directory; the file is loaded
   automatically.

The variables are:

```dotenv
AWS_ACCESS_KEY_ID=...          # required
AWS_SECRET_ACCESS_KEY=...      # required
AWS_SESSION_TOKEN=...          # optional, for temporary credentials
AWS_DEFAULT_REGION=...         # optional
AWS_ENDPOINT_URL=...           # optional, for S3-compatible services such as MinIO
BUCKET_NAME=...                # optional, default bucket for paths without `s3://bucket`
```

### CLI

```bash
# List the files under a directory (one per line, relative to it)
krtr database s3 list-files s3://my-bucket/data
# ... also saved to data/my-bucket_data_files.txt by default; pass --no-save to skip that
krtr database s3 list-files s3://my-bucket/data --no-save

# One file
krtr database s3 download-file s3://my-bucket/data/report.csv ./downloads/report.csv

# Every object under a prefix, preserving the sub-structure
krtr database s3 download-directory s3://my-bucket/data ./downloads/data
```

When `BUCKET_NAME` is set you can omit the bucket and pass just the key or prefix
(`krtr database s3 download-file data/report.csv ./report.csv`). A bucket written in the path
(`s3://other-bucket/...`) always overrides the default.

### Datasets

Files laid out as `<dataset>/year=YYYY/month=MM/day=DD/<dataset>_YYYYMMDD.csv` (e.g.
`complaints/year=2024/month=09/day=11/complaints_20240911.csv`) belong to the dataset
`complaints`. Files at the bucket root, like `customers.csv`, are single-file datasets.

```bash
# What is available? Coverage, file count and missing days per dataset
krtr database s3 datasets

# Save the distinct concepts to data/<bucket>_catalog.txt, one `concept | format` per line
# (e.g. `complaints | directory`, `customers | .csv`)
krtr database s3 generate-catalog --source data --output data

# Download a dataset (into data/, keeping the year=/month=/day= folders), all or by date
krtr database s3 download-dataset data/products.csv
krtr database s3 download-dataset complaints --start 2024-01-01 --end 2024-03-31
krtr database s3 download-dataset transactions --source data --year 2026
krtr database s3 download-dataset complaints --month 2024-09
```

`--start/--end`, `--year` and `--month` are mutually exclusive. Dates cannot be used with
single-file datasets. All three commands accept `--source` (a directory other than the bucket
root) and the download and catalog commands accept `--output` (a directory other than `data/`).

Parent directories are created as needed. Add `--verbose` before the subcommand
(`krtr --verbose database s3 ...`) for debug logging. Failures (bad path, missing credentials,
empty prefix, S3 errors) exit with code 1.

### Python

```python
from pathlib import Path

from krtr.database.s3.client import S3Client

client = S3Client()  # or S3Client(S3Config(...))
client.download_file("s3://my-bucket/data/report.csv", Path("report.csv"))
result = client.download_directory("s3://my-bucket/data", Path("downloads"))
print(result.downloaded_files)
```

Directory downloads paginate through all objects, skip folder marker keys, only match the exact
prefix (`data` never matches `data2/`), and refuse keys that would be written outside the local
directory.

## Neon Postgres

`krtr` can create a table's schema in the [Neon](https://neon.tech) Postgres database and load a
Parquet (or CSV) source file into it, for any table — not just one hardcoded table.

### Credentials

1. In `.env`, set `NEON_DB_HOST` to the **full connection string** Neon gives you, e.g.:

   ```dotenv
   NEON_DB_HOST=postgresql://user:password@host/dbname?sslmode=require&channel_binding=require
   ```

   (Despite the name, this must be the complete `postgresql://...` URL, not just a hostname — see
   `.env.example`.)

2. Run any `krtr database neon ...` command from the repo root; `.env` is loaded automatically.

### Adding a table

A table is defined entirely by its SQL, under `krtr/database/queries/<table>/`:

- `table.sql` — the table's `CREATE TABLE` DDL (required for `create-schema`).
- `query.sql` — the table's `INSERT` template, in the same column order as `table.sql` (required
  for `load`).

There is no per-table Python or CLI code: `krtr database neon create-schema products` and
`krtr database neon load products` work because `krtr/database/queries/products/table.sql` and
`query.sql` already exist. Adding another table (e.g. `customers`) only means adding its own
`krtr/database/queries/customers/` directory with those same two files.

`products` assumes `customers` and `branches` already exist in the database, since it references
both by foreign key — this repository does not create them.

### CLI

```bash
# Create the products table (and, once you add their SQL, any other table) in Neon
krtr database neon create-schema products

# Load data/products.parquet (or data/products.csv, converted to Parquet automatically
# and cached back to data/products.parquet) into the products table
krtr database neon load products

# Truncate the table first, so a retry never duplicates rows
krtr database neon load products --truncate

# Read from a different directory
krtr database neon load products --source /path/to/data

# Force-reconvert data/products.csv to Parquet even if data/products.parquet is already cached
# (e.g. after the CSV changed)
krtr database neon load products --force-convert

# Stop at the first invalid row instead of skipping it and continuing
krtr database neon load products --strict

# Rows read/inserted per round trip to Postgres (default 5000)
krtr database neon load products --batch-size 10000

# Run the load on Modal instead of this machine (see "Modal (remote execution)" below)
krtr database neon load products --remote    # upload the file, wait for the result
krtr database neon load products --detach    # upload the file, return once it has started
```

`load` streams the Parquet file in row-group batches via pyarrow (never loading the whole file
into memory), validates and coerces each row's values against the table's *live* column types and
nullability (read from Postgres itself, not redeclared in Python), and bulk-inserts each batch with
`psycopg2.extras.execute_values`. A progress bar shows rows loaded; invalid rows are logged and
skipped (unless `--strict`) and are counted separately from successfully loaded rows.

### Loading a partitioned dataset (`load-dataset`)

A dataset downloaded with `krtr database s3 download-dataset` into daily files (e.g.
`transactions`, one `transactions_YYYYMMDD.csv` per day under `year=/month=/day=` folders) has no
single `<table>.csv` for `load` to find. `load-dataset` loads every one of those files instead,
in date order, through the exact same `neon-load` task `load` uses:

```bash
# Load every data/transactions/year=*/month=*/day=*/transactions_*.csv file
krtr database neon load-dataset transactions

# Truncate once, before the first file, so a retry never duplicates rows
krtr database neon load-dataset transactions --truncate

# Same --strict, --force-convert and --batch-size options as load
krtr database neon load-dataset transactions --strict --batch-size 10000

# Run every file's load on Modal instead of this machine (sequentially, waiting for each)
krtr database neon load-dataset transactions --remote
```

Each file reports its own row counts in the log; the command finishes by logging the total rows
read/loaded/failed across every file. `--truncate` only empties the table before the first file,
never between later ones. There is no `--detach` for `load-dataset`, since detaching makes sense
for one run, not a sequence of them.

## Modal (remote execution)

Commands can optionally run on [Modal](https://modal.com) instead of your machine. Modal is an
optional dependency: without it, every command keeps running locally exactly as before, and
merely starting `krtr` never imports the Modal SDK.

There are two independent routes into Neon:

| Route | Command | Uses Modal |
| --- | --- | --- |
| Local → Neon | `krtr database neon load products` | Never |
| Local → Modal → Neon | `krtr database neon load products --remote` (or `--detach`) | Yes |

Both call the very same `run_table_load` function, so they cannot diverge. Only `neon load` can
run on Modal so far; `krtr compute modal tasks` lists the tasks that can.

### Setup

1. Install the optional dependency:

   ```bash
   uv sync --extra modal
   ```

2. Put your Modal token in `.env` (see `.env.example`), or run `modal token new` once:

   ```dotenv
   MODAL_TOKEN_ID=...             # required only for --remote / --detach
   MODAL_TOKEN_SECRET=...         # required only for --remote / --detach
   ```

3. Copy the Neon connection string from `.env` into a Modal secret. Only `NEON_DB_HOST` is ever
   sent, never the whole `.env`. Run it again whenever that value changes:

   ```bash
   krtr compute modal secrets sync
   ```

4. Check everything at once. It reports Neon (needed by every run) apart from the Modal checks
   (needed only for `--remote` / `--detach`), so one failing does not hide the other:

   ```bash
   krtr compute modal doctor
   ```

### Running on Modal

```bash
# Upload data/products.parquet (or the converted CSV), load it from Modal, and wait for the result
krtr database neon load products --remote

# Same, but return as soon as the run has started; the load keeps going after the CLI exits
krtr database neon load products --detach
```

`--remote` and `--detach` cannot be combined. Because the container cannot see your disk, the
source file is first uploaded to a named Modal Volume (`krtr-staging`) and the task receives its
path there. Retries are off by default (`retries=0`): a retried load could insert the same rows
twice, so use `--truncate` when re-running a load.

### Following a run

```bash
krtr compute modal runs                 # every run launched from this machine
krtr compute modal status <call-id>     # running, succeeded or failed (with the reason)
krtr compute modal result <call-id>     # wait for the run and print its result as JSON
krtr compute modal cancel <call-id>     # stop the run and its container
```

Runs are recorded in `.krtr/runs.jsonl` (git-ignored), so a `--detach` run can be found again
without copying its call id.

### Staged files

A run that succeeds deletes its staged file. One that fails or is cancelled **keeps it**, so it
can be launched again without uploading it twice:

```bash
krtr compute modal staging list             # what runs have left on the volume
krtr compute modal staging clean            # remove the files of every finished run
krtr compute modal staging clean <run-id>   # remove one run's files
```

A run that is still going is never cleaned.

### Adding another task

A task runs on Modal by registering it in `krtr/compute/modal/registry.py`: its function (which
takes plain values only), its resources, and which arguments are local files to upload. The
Modal app needs no change. The command then adds `--remote` / `--detach` with the shared options
in `krtr/cli/compute/modal/options.py` and calls `run_task(...)`, as `neon load` does.
