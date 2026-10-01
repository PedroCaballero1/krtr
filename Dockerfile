# krtr-web container image (task 6.1 of docs/guia-web-seguridad.md).
#
# Three stages:
#   1. frontend — Node compiles the krtr/front SPA into static files.
#   2. backend  — uv installs the Python app and its runtime deps (no dev group)
#                 into a self-contained virtualenv.
#   3. runtime  — Python 3.13 slim with only that virtualenv and the built SPA,
#                 running as an unprivileged user on Cloud Run's $PORT.
#
# Build:  docker build -t krtr-web .
# Run:    docker run --rm -p 8080:8080 -e PORT=8080 krtr-web

ARG NODE_VERSION=24
ARG PYTHON_VERSION=3.13
ARG UV_VERSION=0.12.19

# ---------------------------------------------------------------------------
# 1. Frontend: compile krtr/front to krtr/front/dist.
# ---------------------------------------------------------------------------
FROM node:${NODE_VERSION}-bookworm-slim AS frontend

WORKDIR /build

# The repo root is an npm workspace whose lockfile covers krtr/front, so the
# manifests are copied first to cache `npm ci` across source-only changes.
COPY package.json package-lock.json ./
COPY krtr/front/package.json krtr/front/package.json
RUN npm ci --workspace krtr/front --include-workspace-root=false --no-audit --no-fund

COPY krtr/front krtr/front
RUN npm run build --workspace krtr/front

# ---------------------------------------------------------------------------
# 2. Backend: resolve the locked runtime dependencies into /app/.venv.
# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM python:${PYTHON_VERSION}-slim-bookworm AS backend

COPY --from=uv /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /src

# Dependencies first (cached layer), then the project itself.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY krtr krtr
RUN uv sync --frozen --no-dev --no-editable

# ---------------------------------------------------------------------------
# 3. Runtime: minimal image, unprivileged user, no build tooling.
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

RUN groupadd --system --gid 10001 krtr \
    && useradd --system --uid 10001 --gid krtr --no-create-home --shell /usr/sbin/nologin krtr

WORKDIR /app

COPY --from=backend --chown=root:root /app/.venv /app/.venv
COPY --from=frontend --chown=root:root /build/krtr/front/dist /app/frontend

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    KRTR_WEB_ENVIRONMENT=production \
    KRTR_WEB_FRONTEND_DIST_DIR=/app/frontend \
    PORT=8080

USER krtr:krtr

EXPOSE 8080

# `krtr back web serve` runs uvicorn on $PORT with the `Server` header
# disabled (see krtr/cli/back/web/handler.py).
CMD ["krtr", "back", "web", "serve"]
