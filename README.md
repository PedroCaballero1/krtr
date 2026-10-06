# krtr

**A banking customer service agent that answers only what it can prove.**

> **Start here:** download and open [`00-START-HERE-krtr-story.html`](00-START-HERE-krtr-story.html)
> in a browser. It's the full story as an infographic, with the numbers behind each decision.
> GitHub shows HTML files as source code, so the file has to be opened locally.

## What we achieved

A bank customer asks for a balance or how a complaint is going, in Spanish or Portuguese. krtr
answers from that customer's own data, or hands the case to a person.

- **Zero wrong answers on the evaluation set,** in both languages. The thresholds are set so a
  doubtful message gets a question, never a guess.
- **About 3 ms for a clear request,** with no LLM. About 1.3 s only when the local LLM reads a
  doubtful reply.
- **Under 10 USD a month for the whole solution,** all the infrastructure and model hosting
  included.
- **No tokens sent to an outside model.** Both models run locally: no per-token cost, and no
  conversation leaves the system.
- **656 automated tests,** with 98% coverage on the agent. The tests never download a model.
- **Built:** the agent (three phases, usable from the command line), login with Keycloak and
  sessions on the server, an encrypted log of every event, and the bilingual web front end.

### For the jury

Log in at `https://juan-alvarezo-2002--krtr.modal.run/` with one of the 50 test accounts.
The accounts (customer number and password), with what each one can ask the assistant, are
handed to the jury separately through a private channel: passwords are never stored in this
repository.

## The solution: deterministic first

Every answer comes from the customer's own data; models only help understand the question.
- **An action** reads the session customer's data and returns facts.
- **A template** phrases those facts in the customer's language, and can show nothing else.
- **A local embedding model** (MiniLM, vector similarity) matches the message against known
  phrasings. A match needs a high score and a clear lead over every rival.
- **A local LLM** (Qwen2.5-1.5B, int4 ONNX) reads only the doubtful replies. It chooses among
  the options offered, and a deterministic rule checks whatever it proposes.

Each turn ends in one of four ways:
1. **Answer:** a clear request with its details.
2. **Ask:** a question with numbered options, when a detail is missing or the match is
   doubtful.
3. **Hand over:** a person takes the case, for requests the agent can't answer or after three
   questions without progress.
4. **Close:** a confirmed repeated, abusive or off-topic conversation.

## How the data led there

### The brief

The hackathon asked for a secure web page where a bank's customers log in and chat with an
agent ([`docs/goals.md`](docs/goals.md)). It had to:
- meet industry-standard security;
- close the session after 5 minutes idle;
- log every event;
- support Spanish and Portuguese (a requirement of the challenge);
- answer in under a second;
- route by difficulty to cut cost, and hand a case to a person when needed.

### What the data said

We had ten datasets covering three years of daily files: 150,000 customers, 67,095 complaints,
171,321 call transcripts and 212,759 surveys. Four analyses ([`notebooks/eda/`](notebooks/eda/))
found real structure in size and concentration:

| Hypothesis | What the data supports |
|---|---|
| Delinquency | The top 10% of delinquent customers hold about 77% of the delinquent balance |
| Complaints | 74.9% of complaints are still active |
| Branches | No branch stands out |
| Customer value | Very skewed: the top 10% of customers hold 66% of interest income |

### Why there is no machine learning model

The EDA found **no relationship a model could learn**:
- credit score and tenure vs customer value: Spearman 0.00;
- days to resolution vs low-rating comments: between −0.07 and +0.08;
- call topic labels vs call text: Cramér's V 0.01;
- delinquency: a flat 15% in every segment.

The one relationship that moves is activity vs balances (0.61), and it's mechanical: more
products mean more activity.

The data also looks generated, not observed:
- `days_past_due` takes only 7 values;
- surveys hold 13 distinct comments;
- a complaint's product never belongs to the complainant.

**Any predictive model trained on it would overfit:** it would look accurate on these files
and fail on real customers. No large opportunity in the analysis needed one either. The only
machine learning technique the solution uses is **vector similarity**, to match a customer's
message with known phrasings.

### The decision

The call history made it clear. Its 171,321 transcripts hold only 12 distinct lines, and
**every call opens with a balance request**. Two facts pointed to automating the recurring
questions:
- **What customers ask:** balances, and how their complaints are going (3 in 4 are still
  open). Both can be answered from data the bank holds, with no person involved.
- **What it costs today:** about 92,000 jobs a year are handled by people (11,321 of them
  call-center complaints).

The agent covers **account balance** and **complaint status** first. Everything else (an
unrecognised charge, a lost card, a loan) goes to a person.

### Built in three phases, measured at every step

1. **A deterministic core:** no model at all, fully testable offline.
2. **Vector similarity (MiniLM):** the thresholds are measured per language with one rule, no
   wrong match ever. A rival label for requests the agent can't answer raised the guard flags
   from 4 to 11 of 16.
3. **A local LLM (Qwen):** it reads only doubtful replies. Asking it to classify a message
   instead of "is it abusive?" cut false closures from 17 to 1 of 26 banking complaints.

### The platform

Both developers work full time, so every infrastructure choice was judged by how fast we could
change it and test it.

| Choice | Why |
|---|---|
| **Modal** | Google Cloud's free trial requires a payment. Modal's Starter credits run our code without Docker image builds, so changes are tested quickly. |
| **Neon** | Serverless Postgres with a free tier and branches for `dev` and production, easy to use from Modal. |
| **Keycloak** | Open-source, standard login (OIDC with PKCE) for the 150,000 accounts, at no cost. |
| **FastAPI** | A backend-for-frontend: the browser never sees a token, and session cookies are `HttpOnly`, `Secure` and `__Host-`. |
| **Local models** | MiniLM and Qwen run inside the app: no per-token cost, no data leaving, and they run in tests. |
| **Clean code** | Vertical slices, every model chosen from a fixed list, SQL in `.sql` files, events encrypted with AES-256-GCM. |

## Next steps

| Area | Next step |
|---|---|
| Agent | **More deterministic answers:** open more intents the agent can solve from data, starting with a polite close and filing a complaint with its category, so fewer cases need a person. |
| Agent | **Some independence:** give the agents more room where it is safe, such as phrasing replies or chaining steps, while every fact still comes from a deterministic action. |
| Agent | **Bundles by config:** package each agent (intents, phrases, thresholds, models, prompts) as a versioned configuration, so a version can be deployed, compared and rolled back. |
| Platform | **Cheaper, stable infra:** look for hosting that costs less and is more stable than a monthly credit budget, for the web app, the login service and the models. |
| Platform | **Docker:** containerise the repository, so it runs the same way on every machine and on any provider. |
| Platform | **Microservices:** split the vertical slices (web, security, agent, data) into services that can be deployed and scaled on their own. |

The rest of this README is the walkthrough for the repository's tools.

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
- Mientras no estén las tareas 4.8 y 4.9 de la guía, crear un caso y el chat todavía no
  funcionan.
- La versión en Modal todavía no está desplegada (fase 6 de la guía).

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
