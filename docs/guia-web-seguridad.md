# Guía de trabajo — Web y seguridad de krtr

_Versión 1 · 29-sep-2026 · Fuente: [`docs/goals.md`](goals.md) + decisiones acordadas con el equipo_
_Meta: terminar el 2-oct-2026 · Fecha límite de la hackathon: 5-oct-2026_

> **⚠️ Guía reemplazada.** Desde el 1-oct-2026 se sigue [`guia-web-seguridad_modal.md`](guia-web-seguridad_modal.md) (v2): Google Cloud quedó descartado y todo se despliega en Modal. Esta versión se conserva solo como referencia, porque la v2 remite a ella en algunos puntos ("igual que la v1"). No la uses para planear ni ejecutar tareas.

---

## 0. Cómo usar esta guía

- La ejecuta **Claude Code con revisión humana**. Cada tarea `x.y` es una unidad pequeña: un cambio, un commit y una revisión.
- Quién ejecuta cada tarea: **🤖** Claude Code · **👤** una persona del equipo (consolas, pagos, DNS, cosas físicas) · **👤🤖** Claude Code prepara los comandos y la persona los aprueba y ejecuta.
- Cada tarea tiene: **Objetivo**, **Archivos**, **Aceptación**, **Verificación**, **Depende de** y **Commit** (Conventional Commits, según el `CLAUDE.md`).
- **Reglas para Claude Code:**
  1. Cumplir el [`CLAUDE.md`](../CLAUDE.md) al 100%, también en el frontend (ver 1.5).
  2. No empezar una tarea si sus dependencias no están aprobadas.
  3. Si algo de esta guía no está claro, **preguntar antes de ejecutar**.
  4. Nunca subir secretos, contraseñas ni archivos de `data/` al repositorio.
  5. Los `table.sql` solo se escriben con la documentación de columnas que aprobó el usuario (§2 y §3.5).
- **Antes de empezar**, hay que revisar y cerrar las decisiones de la §2.

---

## 1. Decisiones cerradas

| Tema | Decisión | Ref. |
|---|---|---|
| Alcance | Solo **web y seguridad**: página, servidor, frontend, seguridad, despliegue. La IA, la lógica de casos y el resumen quedan fuera. | G2–G5, G15, G21 |
| Estructura | `krtr/back/` (FastAPI) con `krtr/back/web/` y `krtr/back/security/`; `krtr/front/` (SPA). Vertical slices según el `CLAUDE.md`. | G4 |
| Backend | FastAPI. | — |
| Frontend | React + Vite + TypeScript + Tailwind + shadcn/ui, compilado a estáticos que sirve FastAPI en el mismo dominio. | — |
| Autenticación | Opción (a): cuentas propias para los **150.000 `customer_id`** del dataset, con contraseñas aleatorias de **8 caracteres**. Proveedor de identidad: **Keycloak en Cloud Run**, flujo OIDC Authorization Code + PKCE, con FastAPI como BFF (backend-for-frontend). | G5, G6 |
| Registro | **No** se pueden crear cuentas nuevas. La única excepción es 1 cuenta con **MFA TOTP**, que crea el equipo. | G5 |
| Credenciales para el jurado | Archivo con una **muestra de 50** clientes **Active** elegidos al azar. Se publica en `JURY_ACCESS.md`, en la raíz del repo: son cuentas de prueba (E9 de `docs/security-checklist.md`). | G6 |
| Bloqueo por intentos | 5 intentos fallidos → bloqueo de 15 minutos. | G3 |
| Sesión | Se cierra tras **5 min** sin interacción y a los **30 min** como máximo aunque haya actividad. Se avisa **30 s antes**. **1 sesión por usuario**. Los casos abiertos se conservan. | G15 |
| Idiomas | Interfaz y login en **ES y PT** con selector. Por defecto **ES**. | G14 |
| Pantallas | Landing = login. Después del login: botón de **soporte**, **número de usuario** y **cerrar sesión**. | G5 |
| Casos | La web solo muestra los casos abiertos (ID, fecha, resumen) y permite escribir un ID. Qué casos existen y cuándo se abren o cierran lo decide el backend. Por ahora, datos de prueba. | G18 |
| Chat | El frontend solo habla con **un endpoint del backend**, y el backend se encarga de la IA. Por ahora responde un **mensaje genérico**, **completo** (sin streaming). | G7, G11 |
| "Escribiendo…" | Si la respuesta tarda **más de 2 s**, se muestra el indicador. La meta es responder en menos de 4 s (revisada el 2026-10-06; antes, 1 s). | G9, G16 |
| Voz | Botón que graba y **envía el audio al backend**. Se aceptan WebM/Opus y MP4/AAC, con un máximo de 60 s. Qué hace el backend con el audio queda fuera de alcance. | G8, G10 |
| Eventos | Una sola tabla `events(id UUID, event_name, properties cifrado, occurred_at)`. Se registra **todo**. Retención de **3 meses**. | G21 |
| Base de datos | Todo en **Neon** (AWS us-east-1, Norte de Virginia). Scale-to-zero **desactivado**. Base aparte `keycloak`. | — |
| Despliegue | **Google Cloud Run en `us-east4`** (prueba gratuita de 300 USD por 90 días). Un solo entorno (producción). **GitHub Actions** despliega con cada merge a `master` si pasan pytest y los linters. | — |
| Dominio | Se compra en los próximos 2 días. La guía incluye DNS, TLS y Load Balancer. | — |
| Seguridad | Referencia **OWASP ASVS 5.0 nivel 2** + OWASP Top 10. Pruebas en **pytest** que corren **contra producción**, más ZAP. | G3 |
| Carga | Menos de 20 usuarios simultáneos (jurados). Pruebas de carga con Locust. | G3 |
| Límite de mensajes | 20 mensajes por minuto por usuario. | G3 |

---

## 2. Decisiones por defecto (confirmar o ajustar en la revisión)

Estas decisiones salen de lo acordado, pero **nadie las dijo explícitamente**. Si el revisor no comenta nada, quedan como están.

| # | Decisión propuesta | Por qué |
|---|---|---|
| D1 | Tabla **`app_sessions`**: `session_id_hash` (SHA-256 del token de la cookie), `customer_id`, `tokens_ciphertext` (tokens OIDC cifrados), `created_at`, `last_activity_at`, `absolute_expires_at`, `revoked_at`. | El BFF necesita guardar la sesión en el servidor para aplicar los timeouts y la regla de 1 sesión en cualquier instancia. El `CLAUDE.md` exige que el usuario apruebe las columnas. |
| D2 | **Cómo aplicar el `CLAUDE.md` a React/TS:** tests en `tests/front/` como espejo de `krtr/front/src/`; TSDoc en cada componente y función; `enum`/`as const` en lugar de strings mágicos; componentes de 40 líneas como máximo; nada de `console.*` (los eventos van al backend). **Excepción:** se permiten callbacks anónimos solo como argumento directo de hooks (`useEffect(() => …)`) o de props JSX (`onClick={() => …}`), y deben delegar en funciones del módulo. | Sin esta excepción, la regla de "no funciones anidadas" choca con el funcionamiento de React. |
| D3 | Los eventos de login los genera Keycloak. Un job cada 15 min los copia a `events` leyendo `event_entity` de la base `keycloak` con un rol de solo lectura. | Cumple G21, que pide "una sola tabla". Se lee directo de la base porque la API de administración queda bloqueada al público. |
| D4 | **Cuentas QA**: 50 clientes Active adicionales al azar, distintos de los del jurado, para pruebas de carga y pytest en producción. Sus contraseñas van en Secret Manager y GitHub Secrets. Las contraseñas en claro de las **otras ~149.900 cuentas se descartan** después de calcular el hash. | Si los tests usaran cuentas del jurado, la regla de 1 sesión cerraría la sesión de un jurado durante la demo. Guardar 150.000 contraseñas en claro sería un riesgo. |
| D5 | Los usuarios **no** pueden cambiar ni recuperar su contraseña: la consola de cuenta y "olvidé mi contraseña" de Keycloak quedan desactivadas. No se importan emails ni nombres. | Los emails son ficticios (y compartidos) y conviene guardar el mínimo de datos personales. |
| D6 | Mensaje de texto de 2.000 caracteres como máximo. Audio de 60 s y 2 MB como máximo. Límite general por IP en Cloud Armor: 600 peticiones por minuto. | Los jurados pueden salir todos por la misma IP, así que el límite por IP tiene que ser holgado. |
| D7 | Latencia del backend **sin IA**: p95 ≤ 300 ms con 20 usuarios. Con un pico de 50 usuarios, 0% de errores 5xx. | Le deja unos 700 ms a la IA dentro de la meta de 1 s (G16). |
| D8 | Cloud Run: la app con `min=1, max=1` y Keycloak con `min=1, max=1` y `--cache=local`. | El límite de mensajes se lleva en memoria y Keycloak no forma clúster en Cloud Run. Una instancia de cada uno aguanta de sobra 20 usuarios. |
| D9 | Las pruebas contra producción (seguridad, E2E y carga) van en `e2e/`, en la raíz y **fuera de** `tests/`. | No corresponden a ningún módulo, así que no pueden seguir la regla de espejo 1:1. |
| D10 | Desarrollo local: rama `dev` de Neon + Keycloak en Docker. | Todo sigue en Neon sin tocar los datos de producción. |
| D11 | La app en `<dominio>` y Keycloak en `auth.<dominio>`. Mientras no haya dominio, se prueba con las URLs `*.run.app`. | Así el LB sirve ambos servicios con un solo certificado por host. |
| D12 | Las 150.000 cuentas quedan habilitadas para login, estén Active o no. | "Credenciales para todos" (G6). La muestra del jurado solo tiene Active. |
| D13 | El aviso de 30 s aplica tanto al cierre por inactividad como al cierre por máximo de 30 min. | Para ser coherentes con el aviso de inactividad. |
| D14 | El idioma elegido se guarda en el navegador (`localStorage`). Sin preferencia guardada, se usa ES. Se envía a Keycloak con `ui_locales`. | Así el login y la app quedan en el mismo idioma. |
| D15 | Mensaje de prueba del chat. ES: "Gracias por tu mensaje. Nuestro asistente estará disponible muy pronto." PT: "Obrigado pela sua mensagem. Nosso assistente estará disponível em breve." | Placeholder hasta que se conecte la IA. |

---

## 3. Arquitectura

### 3.1 Vista general

```
                    Navegador (SPA React · es / pt-BR)
                                   │ HTTPS · TLS ≥ 1.2
                                   ▼
        Load Balancer HTTPS global + Cloud Armor (WAF OWASP, límite por IP, /admin solo IPs permitidas)
             │ <dominio>                                      │ auth.<dominio>
             ▼                                                ▼
   Cloud Run "krtr-web" (us-east4)                  Cloud Run "krtr-auth" (us-east4)
   FastAPI (BFF) + SPA estática   ── OIDC (código, ──►  Keycloak (realm "krtr")
   · sesiones · CSRF · headers       refresh, logout)   · usuarios 150k · MFA TOTP · bloqueo
   · límite de mensajes · eventos                       │
             │ pooled                                   │ conexión directa
             ▼                                          ▼
      Neon DB app: events, app_sessions          Neon DB keycloak (tablas de Keycloak)

   Cloud Scheduler ─► Cloud Run Jobs: purge-events (diario) · sync-auth-events (cada 15 min)
   GitHub Actions ─► (CI: pytest + linters + escáneres) ─► Artifact Registry ─► Cloud Run
   Secret Manager ─► secretos de krtr-web, krtr-auth y jobs
```

### 3.2 Flujos principales

**Login (G5, G6).**
1. En la landing, el usuario elige idioma y pulsa "Iniciar sesión".
2. El navegador va a `GET /auth/login?lang=es`.
3. FastAPI genera `state`, `nonce` y PKCE, y redirige a Keycloak con `ui_locales`.
4. Keycloak valida el usuario (`customer_id`) y la contraseña, aplica el bloqueo por intentos y pide TOTP solo a la cuenta que lo tiene configurado. Al terminar, redirige a `GET /auth/callback`.
5. FastAPI cambia el código por los tokens, **cierra la sesión anterior** de ese `customer_id`, crea la fila en `app_sessions` y entrega la cookie `__Host-krtr_session` (`HttpOnly`, `Secure`, `SameSite=Strict`). Después redirige a `/app`.
6. El navegador **nunca** ve los tokens.

**Sesión (G15).**
- El frontend detecta actividad (mouse, teclado, toque, scroll) y llama a `POST /api/session/activity` como máximo cada 60 s.
- El backend renueva `last_activity_at`, refresca los tokens si hace falta y devuelve `idle_expires_at` y `absolute_expires_at`.
- 30 s antes del cierre, el frontend muestra un aviso. En el aviso de inactividad, el botón "Seguir conectado" cuenta como actividad. Si se llega al límite, se cierra la sesión.
- El backend **también** aplica los límites, aunque el frontend falle.

**Soporte y chat (G18, G8, G9).**
1. El usuario pulsa **Soporte** y elige "Caso nuevo" o "Caso existente".
2. Si es un caso existente: la web lista los casos abiertos (`GET /api/cases?status=open`) y además tiene un campo para escribir el ID (`POST /api/cases/resume`, que busca coincidencia exacta por `incident_id` + `customer_id` de la sesión).
3. Chat de texto: `POST /api/chat/messages`. Si no hay respuesta en 2 s, aparece "escribiendo…".
4. Voz: grabar, detener y enviar con `POST /api/chat/voice`. La respuesta siempre es texto.

### 3.3 Estructura de carpetas

```
krtr/
  back/
    web/                  # FastAPI: app, routers, servir la SPA
      config.py  artifacts.py  app.py
      routers/  (auth.py, session.py, cases.py, chat.py, events.py, health.py)
      cases/    (interfaz CaseRepository + StubCaseRepository)
      chat/     (interfaz ChatResponder + StubChatResponder)
    security/
      oidc/       # cliente OIDC hacia Keycloak
      sessions/   # sesiones en el servidor, timeouts, 1 sesión por usuario
      csrf/  headers/  rate_limit/
      crypto/     # AES-256-GCM para properties y tokens
      audit/      # servicio de eventos (G21), purga y sincronización con Keycloak
      credentials/# generación e importación de credenciales (G6)
      keycloak/   # Dockerfile, realm-krtr.json, themes/krtr/
  front/                  # proyecto Vite (package.json, src/, index.html)
  cli/back/...            # comandos typer, espejo de krtr/back
  database/queries/
    events/        (table.sql, query.sql, purge.sql)
    app_sessions/  (table.sql, query.sql, ...)
tests/back/... tests/front/... tests/cli/back/...   # espejo 1:1
e2e/  security/  browser/  load/                    # contra producción (D9)
Dockerfile   .github/workflows/deploy.yml
```

### 3.4 Contrato de la API (frontend ↔ backend)

| Método y ruta | Autenticación | Entrada | Salida |
|---|---|---|---|
| `GET /auth/login?lang=` | No | idioma | 302 a Keycloak |
| `GET /auth/callback` | No | `code`, `state` | cookie de sesión y 302 a `/app` |
| `POST /auth/logout` | Sí + CSRF | — | 204; también cierra la sesión en Keycloak |
| `GET /api/me` | Sí | — | `{customer_id, idle_expires_at, absolute_expires_at}` |
| `POST /api/session/activity` | Sí + CSRF | — | igual que `/api/me` |
| `GET /api/cases?status=open` | Sí | — | `[{incident_id, opened_at, summary}]` (datos de prueba) |
| `POST /api/cases` | Sí + CSRF | — | `{incident_id}` (datos de prueba) |
| `POST /api/cases/resume` | Sí + CSRF | `{incident_id}` | `{incident_id}` o 404 (la misma respuesta si no existe o si es de otro usuario) |
| `POST /api/chat/messages` | Sí + CSRF + límite | `{incident_id, text ≤2000, language}` | `{incident_id, reply, responded_at}` |
| `POST /api/chat/voice` | Sí + CSRF + límite | multipart `audio` (webm/opus o mp4/aac, ≤60 s, ≤2 MB), `incident_id`, `language` | igual que el anterior |
| `POST /api/events` | Opcional + Origin | `{event_name ∈ catálogo, properties ≤4 KB}` | 202 |
| `GET /healthz` | No | — | 200 |

Todas las respuestas llevan un `request_id`. Los errores tienen la forma `{error: <code>, message_key}` para que el frontend los traduzca.

### 3.5 Tabla `events` (G21)

| Columna | Tipo | Significado (dado por el usuario) |
|---|---|---|
| `id` | `UUID` PK | Identificador único del evento. |
| `event_name` | `VARCHAR(100) NOT NULL` | Tipo de evento: un valor del Enum `EventName`. |
| `properties` | `BYTEA NOT NULL` | JSON con las características del evento, **cifrado** con AES-256-GCM (nonce + ciphertext). No se puede consultar desde SQL. |
| `occurred_at` | `TIMESTAMPTZ NOT NULL` | Momento en que ocurrió el evento (UTC). |

La retención es de 90 días: `purge.sql` borra las filas con `occurred_at < now() - interval '3 months'`. **No** se crean índices (regla del `CLAUDE.md`).

**Catálogo inicial de `EventName`** (Enum; ampliarlo si aparecen eventos nuevos):
- **HTTP:** `http_request` (método, ruta, estado, latencia, IP, user-agent, request_id).
- **Login:** `auth_login_started`, `auth_login_succeeded`, `auth_login_failed`, `auth_logout`, `auth_*` (importados de Keycloak), `session_created`, `session_revoked_by_new_login`, `session_idle_warning_shown`, `session_absolute_warning_shown`, `session_extended`, `session_expired_idle`, `session_expired_absolute`.
- **Interfaz:** `page_view`, `language_changed`, `support_clicked`, `case_mode_selected`, `case_list_viewed`, `case_created`, `case_resume_succeeded`, `case_resume_failed`.
- **Chat:** `chat_message_sent`, `chat_response_received` (con latencia), `typing_indicator_shown`.
- **Voz:** `voice_recording_started`, `voice_recording_cancelled`, `voice_recording_sent`, `voice_permission_denied`.
- **Seguridad:** `rate_limit_exceeded`, `csrf_rejected`, `unauthorized_request`, `client_error`, `server_error`.

Nunca se guardan contraseñas, tokens ni cookies en `properties`.

---

## 4. Calendario

| Día | Fases | Nota |
|---|---|---|
| Mar 29-sep (tarde) | 1, 2 | Cerrar la §2 primero. |
| Mié 30-sep | 3, 4 | La fase 5 puede ir **en paralelo** porque el contrato (§3.4) ya está fijo. |
| Jue 1-oct | 5, 6 | El dominio tiene que estar comprado a más tardar hoy (6.5). |
| Vie 2-oct | 7, 8 | Congelar a las 18:00. |
| 3 a 5-oct | Colchón | Diseño visual y conexión con la IA (fuera de esta guía). |

---

## 5. Tareas

### Fase 1 — Preparación

#### 1.1 👤 Verificar herramientas locales
- **Objetivo:** tener instalados `uv`, Python 3.13, Node LTS + npm, Docker, `gcloud`, `gh` y `git`.
- **Aceptación:** `uv --version`, `node -v`, `docker info`, `gcloud --version` y `gh auth status` funcionan sin error.
- **Depende de:** —

#### 1.2 👤 Crear el proyecto de GCP
- **Objetivo:** proyecto `krtr-hackathon` con la prueba gratuita activa (300 USD / 90 días) y una alerta de presupuesto (50/90/100% de 100 USD).
- **Aceptación:** APIs habilitadas: Cloud Run, Artifact Registry, Secret Manager, Cloud Scheduler, Compute (LB + Cloud Armor), IAM Credentials, Cloud Logging.
- **Verificación:** `gcloud services list --enabled` muestra todas las APIs.
- **Depende de:** 1.1

#### 1.3 👤 Preparar Neon
- **Objetivo:**
  - En el proyecto Neon (us-east-1), crear la base `keycloak` y una rama `dev`.
  - Crear los roles `krtr_app` (DML sobre `events` y `app_sessions`), `krtr_keycloak` (dueño de la base `keycloak`) y `krtr_audit_reader` (solo `SELECT` sobre `keycloak.public.event_entity`).
  - **Desactivar scale-to-zero** en la rama principal.
- **Aceptación:** existen 4 connection strings (app pooled, keycloak directa, audit, admin), guardadas en `.env` local y en un gestor seguro. Ninguna en git.
- **Depende de:** —

#### 1.4 🤖 Crear la estructura del repositorio
- **Objetivo:** crear las carpetas de la §3.3 con sus `__init__.py`, y los espejos en `tests/` y `krtr/cli/back/`.
- **Además:**
  - Excluir `krtr/front/` (y `node_modules`, `dist`) en `.gitignore`, black, ruff, flake8, pytest y el wheel de hatch.
  - Agregar `data/credentials/` a `.gitignore`.
- **Aceptación:** `uv run black --check krtr tests`, `uv run flake8 krtr tests`, `uv run ruff check krtr tests` y `uv run pytest` pasan, y `uv build` no incluye `krtr/front`.
- **Commit:** `chore(repo): scaffold back and front verticals`
- **Depende de:** revisión de §2

#### 1.5 🤖 Documentar las reglas para el frontend en `CLAUDE.md`
- **Objetivo:** agregar la sección "Frontend (TypeScript/React)" con las reglas de D2 (tests espejo en `tests/front`, TSDoc, enums, 40 líneas, excepción de callbacks, eventos en lugar de `console`).
- **Aceptación:** el revisor humano aprueba el texto.
- **Commit:** `docs(repo): add frontend rules to CLAUDE.md`
- **Depende de:** 1.4

#### 1.6 🤖 Instalar dependencias con `uv`
- **Objetivo:**
  - Con `uv add`: `fastapi`, `uvicorn[standard]`, `authlib`, `httpx`, `itsdangerous`, `cryptography`, `argon2-cffi`, `python-multipart`, `slowapi`.
  - Con `uv add --dev`: `pytest-playwright`, `locust`, `respx`, `bandit`, `pip-audit`.
- **Aceptación:** `uv lock` queda consistente y CI (`uv sync --locked`) pasa.
- **Commit:** `chore(repo): add web and security dependencies`
- **Depende de:** 1.4

### Fase 2 — Base de datos

#### 2.1 🤖 SQL de `events`
- **Objetivo:** `krtr/database/queries/events/table.sql`, `query.sql` (INSERT) y `purge.sql` (DELETE por retención), con la documentación de la §3.5.
- **Aceptación:** los tests de carga de SQL existentes pasan; no hay índices.
- **Verificación:** `krtr database neon create-schema events` contra la rama `dev`.
- **Commit:** `feat(database/queries/events): add events table and queries`
- **Depende de:** 1.4

#### 2.2 🤖 SQL de `app_sessions`
- **Objetivo:** `table.sql` y las consultas necesarias (insertar, buscar por hash, tocar actividad, revocar por `customer_id`, revocar por id), con las columnas aprobadas en **D1**.
- **Aceptación:** igual que 2.1.
- **Commit:** `feat(database/queries/app_sessions): add session table and queries`
- **Depende de:** D1 aprobada

#### 2.3 🤖 Pool de conexiones en `NeonClient`
- **Objetivo:** **extender** el `NeonClient` existente (regla DRY) con un pool (`ThreadedConnectionPool`) y métodos con parámetros (`execute_params`, `fetch_one`, `fetch_all`), sin romper `load`.
- **Aceptación:** los tests existentes siguen pasando y hay tests nuevos de comportamiento (el pool se reutiliza, los parámetros se escapan).
- **Commit:** `feat(database/neon): add pooled parameterized queries`
- **Depende de:** 1.6

### Fase 3 — Identidad (Keycloak)

#### 3.1 🤖 Imagen de Keycloak
- **Objetivo:** `krtr/back/security/keycloak/Dockerfile` basado en la **última versión estable de Keycloak** (fijar el tag exacto y anotarlo), con build optimizado (`kc.sh build`, `db=postgres`, health habilitado).
- **Configuración en tiempo de ejecución:** `KC_HOSTNAME`, `KC_PROXY_HEADERS=xforwarded`, `KC_HTTP_ENABLED=true` (el TLS termina en el LB), `--cache=local`.
- **Desarrollo local:** `docker-compose.yml` con la conexión a la rama `dev` de Neon.
- **Aceptación:** `docker compose up` levanta Keycloak y `/health/ready` responde 200.
- **Commit:** `feat(back/security/keycloak): add Keycloak image`
- **Depende de:** 1.3, 1.4

#### 3.2 🤖 Realm `krtr` como código
- **Objetivo:** `realm-krtr.json` importable, **sin secretos**.
- **Configuración del realm:**
  - Registro OFF, "olvidé mi contraseña" OFF, "recordarme" OFF, consola de cuenta OFF (D5).
  - i18n habilitado con `es` y `pt-BR`; por defecto `es`.
  - Política de contraseña `length(8)`.
  - Protección contra fuerza bruta: 5 fallos → bloqueo temporal de 15 min.
  - SSO Session Idle 5 min, SSO Session Max 30 min, access token de 5 min.
  - Flujo browser con **User Session Count Limiter** (máximo 1, cerrar la sesión más antigua) y **Conditional OTP** (pide TOTP solo a quien lo tiene configurado).
  - User Profile con email, nombre y apellido opcionales. Emails duplicados permitidos (no se importan).
  - Eventos de login y de administración activos, con expiración de 90 días.
- **Clientes:**
  - `krtr-web`: confidencial, PKCE S256, redirect URIs exactos (local, `run.app` y `<dominio>`), web origins exactos, post-logout redirect.
  - `krtr-importer`: service account con los roles mínimos para importar usuarios. Verificar en la documentación si `partialImport` exige `manage-realm`.
- **Aceptación:** al importar en local, un usuario de prueba entra con `customer_id` + contraseña, queda bloqueado al sexto intento y un segundo login cierra la sesión anterior.
- **Commit:** `feat(back/security/keycloak): add krtr realm configuration`
- **Depende de:** 3.1

#### 3.3 🤖 Tema de login mínimo "krtr"
- **Objetivo:** `themes/krtr/login` que extiende el tema base, con el nombre krtr, el selector ES/PT visible y CSS sin estilos inline. El diseño final queda para después.
- **Aceptación:** la pantalla de login se ve en ES y en PT según `ui_locales`.
- **Commit:** `feat(back/security/keycloak): add krtr login theme`
- **Depende de:** 3.2

#### 3.4 🤖 Generador de credenciales (G6)
- **Objetivo:** comando `krtr back security generate-credentials`. Lee `customers.csv` (descargado con `krtr database s3 download-dataset customers.csv`) y hace lo siguiente:
  - **(a)** Genera, para los 150.000 `customer_id`, una contraseña aleatoria de 8 caracteres con `secrets`, usando mayúsculas, minúsculas y dígitos.
  - **(b)** Calcula el hash **argon2id** en el formato de credencial que importa Keycloak. Verificar el formato exacto en la documentación de la versión fijada en 3.1. Usar multiproceso.
  - **(c)** Escribe los JSON de importación por lotes de 1.000 en `data/credentials/import/`.
  - **(d)** Elige al azar, con semilla registrada, **50 Active para el jurado** y **50 Active para QA** (D4), sin que se repitan.
  - **(e)** Escribe `data/credentials/jury_credentials.csv` y `qa_credentials.csv` (`customer_id,password`).
  - **(f)** **No guarda** las contraseñas en claro del resto.
- **Aceptación:**
  - Hay tests de comportamiento: largo 8 y alfabeto correcto, el hash se verifica contra la contraseña, las muestras son solo Active, son disjuntas y tienen 50 cada una, y no hay contraseñas en claro fuera de las muestras.
  - Un logger informa el progreso.
- **Commit:** `feat(back/security/credentials): generate customer credentials`
- **Depende de:** 1.6

#### 3.5 🤖 Importador de usuarios
- **Objetivo:** comando `krtr back security import-users --source data/credentials/import`.
  - Usa el service account `krtr-importer` y el endpoint `partialImport` con `ifResourceExists=SKIP`, por lotes y con reintentos.
  - Al final muestra un resumen (importados, omitidos, fallidos).
  - Es idempotente.
- **Aceptación:** los tests con Keycloak simulado (`respx`) cubren lotes, reintentos y resumen.
- **Commit:** `feat(back/security/credentials): import users into Keycloak`
- **Depende de:** 3.2, 3.4

#### 3.6 👤🤖 Probar la importación en `dev`
- **Objetivo:** importar primero 1.000 usuarios y después los 150.000 en el Keycloak local (Neon `dev`).
- **Aceptación:**
  - 3 cuentas del jurado entran bien.
  - Una cuenta cualquiera con una contraseña incorrecta es rechazada.
  - Se anota cuánto tardó la importación.
- **Depende de:** 3.5

### Fase 4 — Backend (FastAPI)

#### 4.1 🤖 Base de la app
- **Objetivo:**
  - `config.py` (pydantic, desde el entorno), `create_app()`, `GET /healthz` y logging por petición con `request_id`.
  - `/docs`, `/redoc` y `/openapi.json` **desactivados en producción**.
  - Servir `krtr/front/dist`, con fallback de la SPA para `/`, `/app` y sus rutas.
  - Comando `krtr back web serve`.
- **Aceptación:** los tests con `TestClient` validan health, que docs quede desactivado según la configuración y el fallback de la SPA.
- **Commit:** `feat(back/web): add FastAPI application skeleton`
- **Depende de:** 1.6

#### 4.2 🤖 Cabeceras de seguridad
- **Objetivo:** middleware que agrega:
  - HSTS (1 año, `includeSubDomains`).
  - CSP: `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; form-action 'self' https://auth.<dominio>; frame-ancestors 'none'; base-uri 'none'; object-src 'none'`.
  - `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Permissions-Policy: microphone=(self), camera=(), geolocation=()`, COOP `same-origin`.
  - `Cache-Control: no-store` en `/api/*`.
- **Aceptación:** hay tests que comprueban cada cabecera y que no se filtra `Server`.
- **Commit:** `feat(back/security/headers): add security headers middleware`
- **Depende de:** 4.1

#### 4.3 🤖 Cliente OIDC (BFF)
- **Objetivo:** `/auth/login`, `/auth/callback` y `/auth/logout` con Authlib.
  - `state`, `nonce` y PKCE S256; `ui_locales` según `lang`.
  - Validar el ID token (issuer, audience, firma, `nonce`, expiración).
  - Logout RP-initiated y revocación del refresh token.
- **Aceptación:** los tests con Keycloak simulado cubren el callback correcto, el `state` inválido y el `nonce` inválido (ambos → 400 + evento), y que el logout limpia la sesión.
- **Commit:** `feat(back/security/oidc): add OIDC login flow`
- **Depende de:** 3.2, 4.1

#### 4.4 🤖 Sesiones del servidor (G15)
- **Objetivo:**
  - Token aleatorio de 256 bits en la cookie `__Host-krtr_session` (`HttpOnly`, `Secure`, `SameSite=Strict`, `Path=/`). En la base solo se guarda su hash.
  - Tokens OIDC cifrados.
  - Inactividad de 5 min, máximo de 30 min, **revocar la sesión anterior** en cada login nuevo.
  - `GET /api/me` y `POST /api/session/activity`; refrescar el access token cuando falte menos de 60 s.
  - Rotar el id de sesión al hacer login.
- **Aceptación:** los tests (con reloj simulado) cubren el cierre en 5:00 y en 30:00, que la actividad extiende la inactividad pero no el máximo, que el segundo login invalida el primero, y que una cookie manipulada da 401.
- **Commit:** `feat(back/security/sessions): add server-side sessions`
- **Depende de:** 2.2, 2.3, 4.3

#### 4.5 🤖 Protección CSRF
- **Objetivo:** en todo método que cambia estado:
  - Validar `Origin` o `Referer` contra `<dominio>`.
  - Double-submit: cookie `__Host-krtr_csrf` (legible por JS) + cabecera `X-KRTR-CSRF`.
- **Aceptación:** los tests cubren que falte la cabecera, que el token no coincida y que el Origin sea ajeno (todos → 403 + `csrf_rejected`).
- **Commit:** `feat(back/security/csrf): add CSRF protection`
- **Depende de:** 4.4

#### 4.6 🤖 Límite de mensajes
- **Objetivo:** 20 mensajes por minuto por `customer_id` en `/api/chat/*`, y un límite general moderado por sesión en `/api/*`. La respuesta es 429 con `Retry-After`.
- **Aceptación:** el test envía 21 mensajes y el último da 429, y se registra `rate_limit_exceeded`.
- **Commit:** `feat(back/security/rate_limit): add per-user rate limiting`
- **Depende de:** 4.4

#### 4.7 🤖 Servicio de eventos (G21)
- **Objetivo:**
  - `crypto/`: AES-256-GCM con la clave desde Secret Manager o el entorno.
  - `audit/`: Enum `EventName`, `record_event(name, properties)` y un middleware que registra `http_request`.
  - `POST /api/events` para eventos del frontend: solo nombres del catálogo, 4 KB como máximo, límite por IP, y el `customer_id` se toma de la sesión, nunca del cliente.
  - Escritura asíncrona para no sumar latencia.
- **Aceptación:**
  - Los tests prueban que lo guardado **no** es JSON legible y que se descifra al original.
  - Un nombre fuera del catálogo da 422.
  - Nunca se guardan contraseñas ni tokens.
- **Commit:** `feat(back/security/audit): add encrypted event logging`
- **Depende de:** 2.1, 2.3, 4.1

#### 4.8 🤖 Casos (datos de prueba, G18)
- **Objetivo:**
  - Interfaz `CaseRepository` (`list_open`, `create`, `get_by_id_for_customer`) y `StubCaseRepository`, que devuelve 2 casos de prueba por cliente en memoria.
  - Endpoints según la §3.4.
  - Coincidencia **exacta** de `incident_id` + `customer_id`. Si no existe o es de otro cliente, la respuesta es **la misma** (404).
- **Aceptación:** hay un test que demuestra que un cliente A no puede retomar un caso de B.
- **Commit:** `feat(back/web/cases): add case endpoints with stub repository`
- **Depende de:** 4.4, 4.5

#### 4.9 🤖 Chat de texto y voz (datos de prueba)
- **Objetivo:**
  - Interfaz `ChatResponder` y `StubChatResponder` (texto de D15 según `language`).
  - `POST /api/chat/messages`: valida texto de 1 a 2.000 caracteres e idioma `es` o `pt-BR`.
  - `POST /api/chat/voice`: valida content-type **y magic bytes** (WebM/EBML o MP4/`ftyp`), 2 MB como máximo y duración declarada ≤ 60 s. El audio no se guarda (fuera de alcance).
- **Aceptación:** los tests cubren un tipo de archivo falso (→ 415), tamaño excedido (→ 413) y la respuesta en ES y en PT.
- **Commit:** `feat(back/web/chat): add chat endpoints with stub responder`
- **Depende de:** 4.5, 4.6

#### 4.10 🤖 Jobs de eventos
- **Objetivo:**
  - `krtr back security purge-events`: ejecuta `purge.sql` y registra cuántas filas borró.
  - `krtr back security sync-auth-events`: lee `event_entity` desde la última marca y los inserta en `events` como `auth_*`, cifrados (D3).
- **Aceptación:** los tests cubren la idempotencia de la sincronización y que la purga no borra eventos recientes.
- **Commit:** `feat(back/security/audit): add purge and Keycloak event sync jobs`
- **Depende de:** 4.7

### Fase 5 — Frontend (en paralelo con la fase 4)

#### 5.1 🤖 Crear el proyecto base
- **Objetivo:** Vite + React + TS en `krtr/front`, con:
  - Tailwind y shadcn/ui.
  - react-router e i18next.
  - Vitest + Testing Library, configurado para leer `tests/front/`.
  - ESLint y Prettier.
  - Proxy de desarrollo a FastAPI.
  - Scripts `build`, `test` y `lint`.
- **Aceptación:** `npm run build`, `npm test` y `npm run lint` pasan, y el build no genera scripts inline.
- **Commit:** `feat(front): scaffold React application`
- **Depende de:** 1.4, 1.5

#### 5.2 🤖 Idiomas ES y PT
- **Objetivo:** archivos `es.json` y `pt-BR.json`, un selector en el header, la preferencia guardada según D14 y `?lang=` al iniciar sesión.
- **Aceptación:** un test comprueba que al cambiar el idioma cambian todos los textos. No quedan textos sin traducir.
- **Commit:** `feat(front/i18n): add Spanish and Portuguese`
- **Depende de:** 5.1

#### 5.3 🤖 Cliente de API y eventos
- **Objetivo:** un cliente que:
  - Hace `fetch` en el mismo origen.
  - Agrega la cabecera CSRF.
  - Ante 401 lleva a la landing y ante 429 muestra un aviso.
  - Traduce los errores con `message_key`.
  - Expone `trackEvent(EventName, props)` → `POST /api/events`.
- **Aceptación:** los tests cubren cada código de respuesta.
- **Commit:** `feat(front/api): add API client and event tracking`
- **Depende de:** 5.1

#### 5.4 🤖 Landing = login
- **Objetivo:** página pública con la marca krtr, el selector de idioma y el botón "Iniciar sesión" / "Entrar". Registra `page_view`.
- **Aceptación:** el botón navega a `/auth/login?lang=<actual>`.
- **Commit:** `feat(front/landing): add login landing page`
- **Depende de:** 5.2, 5.3

#### 5.5 🤖 Página después del login
- **Objetivo:** `/app` con un header que muestra el **número de usuario** (`customer_id` desde `/api/me`) y los botones **Cerrar sesión** y **Soporte**.
- **Aceptación:** sin sesión, la página redirige a la landing; cerrar sesión vuelve a la landing.
- **Commit:** `feat(front/home): add authenticated home`
- **Depende de:** 5.4

#### 5.6 🤖 Gestor de sesión (G15)
- **Objetivo:**
  - Detectar actividad con los listeners `pointerdown`, `keydown`, `wheel`, `touchstart` y `scroll`.
  - Llamar a `/api/session/activity` como máximo cada 60 s.
  - Mostrar un modal con cuenta regresiva 30 s antes de la inactividad y del máximo (D13). "Seguir conectado" solo aparece en el aviso de inactividad.
  - Al vencer, cerrar sesión y mostrar el mensaje "Sesión cerrada por inactividad".
- **Aceptación:** los tests con reloj falso cubren que el modal aparece en 4:30, se cierra en 5:00 y el máximo corta en 30:00.
- **Commit:** `feat(front/session): add inactivity and absolute timeout handling`
- **Depende de:** 5.5

#### 5.7 🤖 Selección de caso (G18)
- **Objetivo:** al pulsar Soporte, el usuario elige **Caso nuevo** o **Caso existente**. En caso existente se ve la lista (ID, fecha, resumen) y un campo para escribir el ID (sin espacios alrededor, 64 caracteres como máximo). Un error muestra "Caso no encontrado".
- **Aceptación:** los tests cubren las 3 rutas (nuevo, elegir de la lista, escribir el ID).
- **Commit:** `feat(front/cases): add case selection`
- **Depende de:** 5.5

#### 5.8 🤖 Vista de chat (G7, G9)
- **Objetivo:** lista de mensajes, caja de texto (Enter envía, Shift+Enter hace salto de línea, contador de 2.000), botón enviar deshabilitado mientras espera, **"escribiendo…" si pasan 2 s sin respuesta**, y manejo de errores, 429 y timeout de 30 s.
- **Aceptación:**
  - Un test con respuesta en 500 ms comprueba que no aparece el indicador.
  - Un test con respuesta en 3 s comprueba que sí aparece a los 2 s.
- **Commit:** `feat(front/chat): add chat view with typing indicator`
- **Depende de:** 5.7

#### 5.9 🤖 Botón de voz (G8)
- **Objetivo:**
  - Grabar con `MediaRecorder`, eligiendo `audio/webm;codecs=opus` o `audio/mp4` según lo que soporte el navegador.
  - Contador visible y corte automático a los 60 s.
  - Opciones de cancelar o enviar; manejo del permiso de micrófono negado.
  - Enviar con `/api/chat/voice`.
- **Aceptación:** los tests con `MediaRecorder` simulado cubren el corte a los 60 s, la cancelación y el permiso negado (con su evento).
- **Commit:** `feat(front/chat): add voice note recording`
- **Depende de:** 5.8

#### 5.10 🤖 Instrumentar eventos
- **Objetivo:** emitir todos los eventos de interfaz del catálogo de la §3.5.
- **Aceptación:** un test por evento comprueba que se envía con el nombre correcto.
- **Commit:** `feat(front): instrument UI events`
- **Depende de:** 5.4–5.9

### Fase 6 — Contenedores y despliegue

#### 6.1 🤖 Imagen de la app
- **Objetivo:** `Dockerfile` multi-etapa:
  - Node compila `krtr/front`.
  - Python 3.13 slim con `uv sync --frozen --no-dev`.
  - Usuario sin privilegios; arranca con `uvicorn` en `$PORT`.
- **Aceptación:** la imagen construye en local, `/healthz` responde 200 y el escaneo de vulnerabilidades no reporta críticas.
- **Commit:** `build(repo): add application container image`
- **Depende de:** 4.1, 5.1

#### 6.2 👤🤖 Registro de imágenes, cuentas de servicio y secretos
- **Objetivo:**
  - Crear el repositorio `krtr` en Artifact Registry (us-east4).
  - Crear las service accounts `krtr-web`, `krtr-auth`, `krtr-jobs` y `krtr-deployer`, con permisos mínimos.
  - Guardar en Secret Manager: connection strings, `KRTR_EVENTS_KEY`, `KRTR_TOKENS_KEY`, el secreto del cliente `krtr-web`, el admin de Keycloak y el secreto de `krtr-importer`.
- **Aceptación:** cada service account solo lee sus propios secretos.
- **Verificación:** `gcloud secrets get-iam-policy` para cada secreto.
- **Depende de:** 1.2

#### 6.3 👤🤖 Desplegar Keycloak
- **Objetivo:** Cloud Run `krtr-auth` en us-east4 con:
  - `min=1, max=1`, CPU siempre asignada, `--cpu-boost`, 2 GiB.
  - Secretos montados y health check en `/health/ready`.
- **Aceptación:** el realm está importado y el login funciona en la URL `run.app`.
- **Depende de:** 3.3, 6.2

#### 6.4 👤🤖 Desplegar la app
- **Objetivo:** Cloud Run `krtr-web` en us-east4 con `min=1, max=1` (D8) y los secretos montados.
- **Aceptación:** el flujo completo funciona en la URL `run.app`: login → soporte → chat.
- **Depende de:** 4.10, 5.10, 6.1, 6.3

#### 6.5 👤 Comprar el dominio y configurar DNS
- **Objetivo:** comprar el dominio (se recomienda Cloudflare Registrar) a más tardar el 1-oct y activar DNSSEC.
- **Aceptación:** `dig NS <dominio>` responde bien.
- **Depende de:** —

#### 6.6 👤🤖 Load Balancer HTTPS
- **Objetivo:**
  - LB externo global con serverless NEGs hacia `krtr-web` y `krtr-auth`.
  - Reglas por host: `<dominio>` y `auth.<dominio>`.
  - Certificados gestionados por Google, redirección HTTP→HTTPS y SSL policy con TLS 1.2 como mínimo (perfil MODERN o RESTRICTED).
  - Registros A en DNS apuntando a la IP del LB.
  - Cambiar ambos servicios a **ingress solo desde el LB** y actualizar `KC_HOSTNAME` y los redirect URIs.
- **Aceptación:** las URLs `run.app` responden 403/404 desde internet, y los dos hosts tienen certificado válido.
- **Depende de:** 6.4, 6.5

#### 6.7 👤🤖 Cloud Armor
- **Objetivo:** una política asociada a ambos backends con:
  - Reglas OWASP preconfiguradas (sqli, xss, lfi, rce), revisadas para evitar falsos positivos.
  - Límite por IP de 600 peticiones por minuto (D6).
  - `/admin/*` en `auth.<dominio>` solo desde las IPs permitidas del equipo.
- **Aceptación:** desde una IP no permitida, `/admin` da 403.
- **Depende de:** 6.6

#### 6.8 🤖 Despliegue continuo
- **Objetivo:** `.github/workflows/deploy.yml`.
  - Al hacer push a `master`, espera a que pasen CI y seguridad (7.1).
  - Se autentica con **Workload Identity Federation**, sin llaves JSON.
  - Construye la imagen, la sube, despliega `krtr-web` y corre el smoke test (`/healthz`).
  - Keycloak se despliega a mano o con `workflow_dispatch`.
- **Aceptación:** un merge de prueba despliega sin intervención manual.
- **Commit:** `ci(deploy): deploy to Cloud Run on master`
- **Depende de:** 6.4, 7.1

#### 6.9 👤🤖 Jobs programados
- **Objetivo:** Cloud Run Jobs `purge-events` (diario, 03:00 COT) y `sync-auth-events` (cada 15 min), con la imagen de la app y disparados por Cloud Scheduler.
- **Aceptación:** una ejecución manual de cada job termina con éxito y se ven sus logs.
- **Depende de:** 4.10, 6.4

#### 6.10 👤 Datos de producción y cuenta con MFA
- **Objetivo:**
  - Importar los 150.000 usuarios en el Keycloak de producción (3.5).
  - Crear la cuenta de excepción con la acción requerida "Configure OTP" y enrolar TOTP.
  - Guardar las credenciales QA en GitHub Secrets.
- **Aceptación:**
  - Una cuenta del jurado entra.
  - La cuenta con MFA pide TOTP.
  - Una cuenta QA entra.
- **Depende de:** 6.3

### Fase 7 — Seguridad y pruebas

#### 7.1 🤖 Escáneres en CI
- **Objetivo:** agregar al CI un job de seguridad con:
  - `bandit -r krtr/back`, Semgrep (reglas `p/python`, `p/owasp-top-ten`, `p/typescript`).
  - `pip-audit`, `npm audit --audit-level=high`, `gitleaks`.
  - Las pruebas del frontend.
- **Aceptación:** el CI falla si hay hallazgos altos o críticos. Hoy el estado es verde.
- **Commit:** `ci(security): add static and dependency scanning`
- **Depende de:** 1.6, 5.1

#### 7.2 🤖 Pruebas de seguridad contra producción
- **Objetivo:** `e2e/security/` con pytest y `--base-url`. Casos:
  - Cabeceras y flags de las cookies.
  - Redirección HTTP→HTTPS y TLS 1.0/1.1 rechazado.
  - `/api/*` sin sesión → 401.
  - Sin CSRF → 403.
  - IDOR: un caso de otro cliente → 404.
  - Segundo login cierra el primero.
  - Límite de 20 mensajes → 429.
  - Voz con tipo de archivo falso → 415.
  - `/docs` → 404.
  - `/admin` bloqueado.
  - Bloqueo tras 5 intentos, comprobado con la API de administración y usando una cuenta **no** del jurado.
  - Cierre por inactividad a los 5 min (test lento, marcado).
  - `properties` cifrado en la base.
- **Aceptación:** todo en verde. Se ejecuta después de cada despliegue y a mano antes de la demo.
- **Commit:** `test(e2e/security): add production security suite`
- **Depende de:** 6.7, 6.10

#### 7.3 🤖 Pruebas E2E de navegador
- **Objetivo:** `e2e/browser/` con pytest-playwright. Recorridos:
  - login ES → caso nuevo → mensaje → respuesta.
  - Cambio a PT.
  - Retomar un caso por ID.
  - Voz con micrófono falso (`--use-fake-device-for-media-stream`).
  - Modal de inactividad con el reloj acelerado.
- **Aceptación:** todo en verde en Chromium y WebKit.
- **Commit:** `test(e2e/browser): add end-to-end user journeys`
- **Depende de:** 6.10

#### 7.4 🤖 ZAP
- **Objetivo:** workflow con el ZAP baseline scan contra `<dominio>` y `auth.<dominio>`, después de cada despliegue y a mano. Las reglas aceptadas se documentan en `.zap/rules.tsv`.
- **Aceptación:** 0 alertas altas y cada alerta media está justificada.
- **Commit:** `ci(security): add OWASP ZAP baseline scan`
- **Depende de:** 6.8

#### 7.5 🤖 Pruebas de carga
- **Objetivo:** `e2e/load/locustfile.py` con usuarios QA que hacen el login OIDC completo y luego mezclan `me`, `activity`, `cases` y `chat`. Escenarios:
  - Base de 20 usuarios durante 10 min.
  - Pico de 50 usuarios.
  - Prueba sostenida de 30 min con 20 usuarios.
- **Aceptación:** se cumple D7 (p95 ≤ 300 ms sin IA; 0% de errores 5xx en el pico). El reporte HTML queda en `docs/reports/`.
- **Commit:** `test(e2e/load): add Locust load scenarios`
- **Depende de:** 6.10

#### 7.6 👤 Revisión contra ASVS nivel 2
- **Objetivo:** `docs/security-checklist.md` con los controles aplicables de ASVS 5.0 L2 (autenticación, sesión, control de acceso, validación, criptografía, logs, configuración). Cada control con estado y evidencia (test o configuración).
- **Aceptación:** no queda ningún control aplicable sin evidencia ni sin excepción justificada.
- **Depende de:** 7.2–7.5

### Fase 8 — Entrega

#### 8.1 🤖 Documentación
- **Objetivo:**
  - Actualizar el `README.md` (cómo levantar en local, comandos nuevos).
  - `docs/runbook.md`: desplegar, rotar secretos, volver a importar usuarios, desbloquear una cuenta, correr los jobs y las pruebas.
  - `docs/api.md` con el contrato de la §3.4 para el equipo de IA.
- **Aceptación:** una persona nueva levanta el proyecto en local siguiendo solo el README.
- **Commit:** `docs(repo): add web runbook and API contract`
- **Depende de:** 7.x

#### 8.2 👤 Congelar y entregar
- **Objetivo:**
  - Correr 7.2 y 7.3 en verde.
  - Revocar las sesiones QA.
  - Publicar las cuentas del jurado en `JURY_ACCESS.md` (raíz del repo), con las instrucciones (URL, idioma, cómo se usa).
  - Etiquetar la versión.
- **Aceptación:** checklist firmado por el revisor humano.
- **Depende de:** 8.1

---

## 6. Fuera de alcance (lo hacen otros equipos o fases)

- Lógica de IA, enrutamiento por dificultad, escalamiento a humanos, reglas duras y ambigüedad (G11–G13, G19, G20).
- La tabla de casos, sus estados y los resúmenes (G17). La web usa las interfaces `CaseRepository` y `ChatResponder` para conectarlos después.
- El procesamiento del audio (voz a texto).
- El diseño visual final (después del 2-oct).

## 7. Riesgos

| Riesgo | Mitigación |
|---|---|
| El dominio o los certificados se demoran (hasta 24 h) | Comprar el dominio el 30-sep. Mientras tanto se prueba con `run.app`. |
| Importar 150.000 usuarios toma horas | Medirlo en `dev` (3.6); correrlo por lotes, en paralelo e idempotente. |
| Keycloak tarda en arrancar o se reinicia | `min=1`, CPU siempre asignada, sesiones persistentes en la base. |
| Los jurados salen por la misma IP | Límite por IP holgado (D6); el límite fino es por usuario. |
| Las reglas de Cloud Armor bloquean tráfico legítimo | Revisar los logs de Armor después de las pruebas 7.2 y 7.3. |
| Los créditos de GCP | Alerta de presupuesto (1.2). El costo estimado cabe en los 300 USD. |
