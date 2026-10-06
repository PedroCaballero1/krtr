# Guía de trabajo — Web y seguridad de krtr

_Versión 3.1 · 6-oct-2026 · **Cambio de plataforma: de Google Cloud a Modal** · Fuente: [`docs/goals.md`](goals.md) + decisiones acordadas con el equipo_
_Fecha límite de la hackathon: 5-oct-2026 · Rama de trabajo: `web-develop-security`_

> **Qué cambió en la v2.** Google Cloud quedó descartado porque la prueba gratuita exige un pago. Todo se despliega en **Modal** (plan Starter, con 30 USD/mes de créditos y sin pagos adicionales). Por eso:
> - No hay Load Balancer, Cloud Armor, Secret Manager ni Cloud Scheduler.
> - **No hay dominio propio**: las URLs son `*.modal.run`.
>
> La fase 6 se reescribió completa. Se agregó la **Fase 0** para deshacer lo que se preparó para GCP. Las decisiones nuevas son D16–D23 (§2) y van marcadas con 🆕.
>
> **v2.1 (revisión de la fase 0).** 0.2 y 0.3 quedaron hechas y D18 aprobada. Se agregaron las tareas 0.5 y 4.11, y se ajustaron 0.1–0.4, 1.1, 3.2, 5.13, 6.1, 6.2, 6.7, 7.6 y las §3.3–§4 para cerrar los huecos que encontró la revisión.
>
> **v2.2 (cuenta de Modal y 0.4).** El workspace es `juan-alvarezo-2002` (D11 con las URLs reales). Regla 7 nueva: los comandos `modal` llevan `--env-file .env`. La 0.4 quedó hecha ([`docs/modal-platform.md`](modal-platform.md)) y sus resultados se aplicaron en 3.7, 4.6 y D22.
>
> **v2.3.** D16, D17 y D19–D23 aprobadas. La 1.3 ahora incluye crear las tablas `events` y `app_sessions` con sus permisos, y el orden correcto del permiso de `krtr_audit_reader`.
>
> **v2.4.** 4.11, 5.11 y 5.12 hechas, y arreglado el test inestable de `chat-page`. La 6.2 sirve `create_served_app()`.
>
> **v2.7 (5-oct).** En la 6.2, la imagen de `web` incluye también el LLM local del agente (Qwen2.5-1.5B, int4 ONNX), que necesita más memoria.
>
> **v2.6 (5-oct).** En la 6.2, la imagen de `web` incluye los pesos del modelo de embeddings del agente y se aclara de dónde salen sus textos: de la página en producción, de Neon solo fuera de línea.
>
> **v2.5 (5-oct).** Nueva tabla `messages` para el texto del chat, decidida con el vertical de IA ([`docs/ia-proposal.md`](ia-proposal.md)): cifrada, retención de 3 meses e índice en `(incident_id, customer_id)` (§3.6). En `events` solo van los metadatos de cada turno, nunca el texto. Se actualizaron 6.1 (nueva llave en `krtr-web`) y 6.5 (la purga diaria también limpia `messages`).
>
> **v2.5.** 1.1 hecha (Docker con Colima) y 1.3 hecha salvo el permiso de auditoría, que va en 3.1. Neon está en us-east-2 (Ohio) y su rama principal se llama `production`.
>
> **v2.6.** 0.5 y 3.1 hechas, con Keycloak 26.8.0 en local y su imagen para Modal. El CI instala el extra `modal`. El permiso de auditoría quedó dado en `dev`. La 6.3 suma lo aprendido en la 3.1.
>
> **v2.7.** 3.2 hecha: el realm `krtr` como código, verificado al reimportarlo (22 de 22). La 6.3 suma lo que la 3.2 deja para producción.
>
> **v3.1 (6-oct) — integración.** Una sola rama, `release-integration`, junta `web-finish-guide`, `keycloak-theme` (3.3, 4.10 y su cron), `security-tests` (7.2–7.6, 4.4) y `delivery-docs` (8.1, 8.2, 6.8) con el `master` de Pedro (#14 MiniLM y #15 LLM Qwen). El chat de producción corre **MiniLM + Qwen 2.5 1.5B int4** (decidido el 6-oct): los modelos viven en el Volume `krtr-models`, preparados una vez con `modal run -m krtr.back.deploy.app::prepare_models`, y `web` sube a **2 CPU / 4 GiB** (cambia D8 y la §8: ≈ 7,8 USD/día con el modo demo).
>
> **v3.0 (5-oct) — salida al aire.** Hechas 3.4–3.7, 4.5, 4.6, 4.8, 4.9 (el chat responde con el motor de IA de Pedro), la purga de 4.10 y 6.1–6.5; 6.6 en curso. **D20 cambió:** los usuarios se importan con `partialImport` de la API de administración, desde dentro del contenedor, no con `kc.sh import` (ver D20 y 3.5). Además: `customer_id` se pasa a mayúsculas al iniciar sesión (Keycloak guarda los usernames en minúsculas), y `krtr_app` puede leer `products` y `complaints`. El despliegue se hace con `modal deploy -m krtr.back.deploy.app` (como módulo, no por ruta). Pendientes: 3.3, 4.10 (sincronización de eventos de Keycloak), 6.7, 7.2–7.6, 8.x.
>
> **v3.1 (5-oct) — entrega.** 8.1 hecha: [`docs/runbook.md`](runbook.md), [`docs/api.md`](api.md) (la §3.4 tal como quedó en el código) y el README al día. 6.8: el registro de gasto empezó en [`docs/modal-platform.md`](modal-platform.md#registro-de-gasto-diario); el CLI de Modal muestra el gasto (`modal billing`), pero el saldo de créditos y un posible límite de gasto solo se ven en el dashboard. La 8.2 tiene su checklist.
>
> **v2.8.** 4.3 y 4.4 hechas: login OIDC, sesiones del servidor y sus endpoints, verificados contra Keycloak local y la rama `dev` de Neon (13 de 13). La 4.5 y el frontend heredan dos puntos abiertos (ver la 4.4).

---

## 0. Cómo usar esta guía

- La ejecuta **Claude Code con revisión humana**. Cada tarea `x.y` es una unidad pequeña: un cambio, un commit y una revisión.
- Quién ejecuta cada tarea: **🤖** Claude Code · **👤** una persona del equipo (consolas, cuentas, decisiones) · **👤🤖** Claude Code prepara los comandos y la persona los aprueba y ejecuta.
- Cada tarea tiene: **Objetivo**, **Archivos**, **Aceptación**, **Verificación**, **Depende de** y **Commit** (Conventional Commits, según el `CLAUDE.md`).
- Estado de cada tarea: ✅ hecha (con su commit) · ♻️ hecha pero hay que corregirla · ⬜ pendiente · ❌ cancelada.
- **Reglas para Claude Code:**
  1. Cumplir el [`CLAUDE.md`](../CLAUDE.md) al 100%, también en el frontend.
  2. No empezar una tarea si sus dependencias no están aprobadas.
  3. Si algo de esta guía no está claro, **preguntar antes de ejecutar**.
  4. Nunca subir secretos, contraseñas ni archivos de `data/` al repositorio.
  5. Los `table.sql` solo se escriben con la documentación de columnas que aprobó el usuario.
  6. **Reutilizar `krtr/compute/modal/`** (imagen, secretos, volúmenes) en lugar de reescribir esa lógica (regla DRY).
  7. **Los comandos del CLI de Modal se corren desde la raíz del repo como `uv run --env-file .env modal …`.** El token de krtr está en `.env` (workspace `juan-alvarezo-2002`), pero el CLI `modal` no lee `.env`: sin `--env-file` usa el perfil activo de `~/.modal.toml` (`development-maia`, otro workspace) y desplegaría ahí. Los comandos `krtr` ya cargan `.env` solos, y el CI usa los secretos de GitHub.
- **Antes de seguir**, el revisor confirma las decisiones 🆕 de la §2. ✅ Todas aprobadas el 1-oct.

---

## 1. Decisiones cerradas

| Tema | Decisión | Ref. |
|---|---|---|
| Alcance | Solo **web y seguridad**: página, servidor, frontend, seguridad, despliegue. La IA, la lógica de casos y el resumen quedan fuera. | G2–G5, G15, G21 |
| Estructura | `krtr/back/` (FastAPI) con `web/`, `security/` y, nuevo, `deploy/` (app de Modal); `krtr/front/` (SPA). Vertical slices según el `CLAUDE.md`. | G4 |
| Backend / Frontend | FastAPI · React + Vite + TS + Tailwind + shadcn/ui, compilado y servido por FastAPI en el mismo origen. | — |
| Autenticación | Cuentas propias para los **150.000 `customer_id`**, con contraseñas aleatorias de **8 caracteres**. **Keycloak** (ahora corriendo en Modal), flujo OIDC Authorization Code + PKCE, con FastAPI como BFF. | G5, G6 |
| Registro | **No** se pueden crear cuentas nuevas. La única excepción es 1 cuenta con **MFA TOTP**, que crea el equipo. | G5 |
| Credenciales para el jurado | Archivo con una muestra de **50** clientes **Active** elegidos al azar. Se publica en `JURY_ACCESS.md`, en la raíz del repo: son cuentas de prueba (E9 de `docs/security-checklist.md`). | G6 |
| Bloqueo por intentos / límite de chat | 5 fallos → bloqueo de 15 min · 20 mensajes por minuto por usuario. | G3 |
| Sesión | Se cierra tras **5 min** sin interacción y a los **30 min** como máximo aunque haya actividad. Aviso **30 s antes**. **1 sesión por usuario**. Los casos abiertos se conservan. | G15 |
| Idiomas | Interfaz y login en **ES y PT** con selector. Por defecto **ES**. | G14 |
| Pantallas | Landing = login. Después del login: botón de **soporte**, **número de usuario** y **cerrar sesión**. | G5 |
| Casos | La web solo muestra los casos abiertos (ID, fecha, resumen) y permite escribir un ID. Lo demás lo decide el backend. Por ahora, datos de prueba. | G18 |
| Chat | Un endpoint del backend, que se encarga de la IA. Por ahora responde un **mensaje genérico**, **completo** (sin streaming). "Escribiendo…" si tarda más de 2 s. Meta: menos de 4 s (revisada el 2026-10-06; antes, 1 s). | G7, G9, G16 |
| Voz | Graba y envía el audio al backend. Se aceptan WebM/Opus y MP4/AAC, con un máximo de 60 s. Lo que el backend haga con el audio queda fuera de alcance. | G8, G10 |
| Eventos | Una sola tabla `events(id UUID, event_name, properties cifrado, occurred_at)`. Se registra **todo**. Retención de **3 meses**. | G21 |
| **Mensajes del chat** 🆕 | Tabla `messages` (§3.6) con el texto de cada mensaje y respuesta, **cifrado** (AES-256-GCM, llave propia `KRTR_MESSAGES_KEY`). Retención de **3 meses**. Índice en `(incident_id, customer_id)`, pedido explícitamente (excepción a la regla del `CLAUDE.md`). En `events` solo van los metadatos del turno, nunca el texto. | G17, G21 |
| Base de datos | Todo en **Neon** (AWS us-east-2, Ohio; la v1 decía us-east-1, pero el host del proyecto es us-east-2). Scale-to-zero **desactivado**. Base aparte `keycloak`. | — |
| **Despliegue** 🆕 | **Modal**, un solo entorno (producción). **GitHub Actions** ejecuta `modal deploy` con cada merge a `master` si pasan pytest, los linters y los escáneres. | — |
| **Dominio** 🆕 | **Ninguno.** Modal solo permite dominio propio desde el plan Team (250 USD/mes). Las URLs son `https://juan-alvarezo-2002--krtr.modal.run` (app) y `https://juan-alvarezo-2002--krtr-auth.modal.run` (Keycloak). | — |
| **Secretos y jobs** 🆕 | **Modal Secrets** reemplaza a Secret Manager. **Modal Cron** reemplaza a Cloud Scheduler (el plan Starter permite 5 crons; usamos 2). | — |
| Seguridad | Referencia **OWASP ASVS 5.0 nivel 2** + OWASP Top 10. Pruebas en **pytest** que corren **contra producción**, más ZAP. Sin WAF: toda la protección vive en la app (ver §7). | G3 |
| Carga | Menos de 20 usuarios simultáneos (jurados). Locust. | G3 |

---

## 2. Decisiones por defecto (confirmar o ajustar en la revisión)

Las decisiones D1–D15 son las de la v1. Si alguna cambió por el paso a Modal, está indicado.

| # | Decisión | Por qué |
|---|---|---|
| D1 | Tabla `app_sessions` (✅ ya existe, commit `685129f`). | Sesiones en el servidor. |
| D2 | Reglas del `CLAUDE.md` para React/TS (✅ commit `dd51ee2`). | — |
| D3 | Los eventos de login de Keycloak se copian a `events` cada 15 min, leyendo `event_entity` con un rol de solo lectura. | G21: una sola tabla. |
| D4 | 50 cuentas **QA** aparte de las del jurado, para pytest y carga en producción. Las contraseñas en claro del resto se descartan. | Evita que la regla de 1 sesión cierre la sesión de un jurado en plena demo. |
| D5 | Sin cambio ni recuperación de contraseña; no se importan emails ni nombres. | Emails ficticios y mínimo de datos personales. |
| D6 | Texto de 2.000 caracteres como máximo; audio de 60 s y 2 MB. **Cambia:** el límite por IP (600 peticiones/min) ahora lo aplica **la app** (antes Cloud Armor), usando la IP que Modal reenvía (ver 0.4). | Sin WAF, el límite tiene que estar en el código. |
| D7 | Backend **sin IA**: p95 ≤ 300 ms con 20 usuarios; 0% de errores 5xx con un pico de 50. | Le deja unos 700 ms a la IA (G16). |
| D8 | **Cambia:** en Modal, la app usa `max_containers=1` y `@modal.concurrent`; Keycloak usa `max_containers=1`. `min_containers` depende de D17. | El límite de mensajes vive en memoria y Keycloak no forma clúster. |
| D9 | Las pruebas contra producción van en `e2e/`, fuera de `tests/`. | No siguen la regla de espejo 1:1. |
| D10 | Desarrollo local: rama `dev` de Neon + Keycloak en Docker (`docker compose`). | Docker se usa **solo en local**; no se paga nada. |
| D11 | **Cambia:** la app en `https://juan-alvarezo-2002--krtr.modal.run` y Keycloak en `https://juan-alvarezo-2002--krtr-auth.modal.run` (etiquetas `krtr` y `krtr-auth`, workspace `juan-alvarezo-2002` confirmado en 0.1, entorno `main`). En el resto de esta guía, `<ws>` = `juan-alvarezo-2002`. | Sin dominio propio. |
| D12 | Las 150.000 cuentas pueden iniciar sesión, estén Active o no. La muestra del jurado solo tiene Active. | G6. |
| D13 | El aviso de 30 s aplica a la inactividad y al máximo de 30 min. | Coherencia. |
| D14 | El idioma se guarda en `localStorage`; por defecto ES; se envía a Keycloak con `ui_locales`. | — |
| D15 | Mensaje de prueba del chat. ES: "Gracias por tu mensaje. Nuestro asistente estará disponible muy pronto." PT: "Obrigado pela sua mensagem. Nosso assistente estará disponível em breve." | Placeholder. |
| **D16** 🆕 | ✅ **Aprobada** (1-oct). Fijar la **región `us-east`** (este de EE. UU.) en las funciones `web` y `auth`, cerca de Neon, que está en us-east-2 (Ohio). | Baja la latencia hacia Neon, pero Modal cobra ×1,75 en región fija (§8). Alternativa más barata: no fijar región (Modal elige, puede quedar lejos de Neon). |
| **D17** 🆕 | ✅ **Aprobada** (1-oct). **"Modo demo"**: `min_containers=1` (siempre encendido) solo desde que la página sale al aire hasta que termina la evaluación. Fuera de esa ventana, `min_containers=0`: se apaga sin tráfico y arranca en frío (Keycloak tarda unos 20–40 s). Se controla con la variable `KRTR_WARM` al hacer `modal deploy`. | Los créditos de 30 USD/mes no alcanzan para tener todo encendido el mes completo (§8). |
| **D18** 🆕 | ✅ **Aprobada** y ejecutada en 0.2 (`24d7dba`). **Retirar** el `Dockerfile` y el `.dockerignore` de la tarea 6.1 v1. La imagen de la app se arma con la API de imágenes de Modal (`uv_sync` + `add_local_python_source` + `add_local_dir` del front compilado), **igual que `krtr/compute/modal/app.py`**. | Evita mantener dos formas de construir la misma imagen; reutiliza lo que ya funciona en Modal. |
| **D19** 🆕 | ✅ **Aprobada** (1-oct). Keycloak corre dentro del contenedor detrás de un **gateway ASGI propio**. Keycloak escucha en `127.0.0.1:8081`, y el gateway lo publica bloqueando `/admin/*`, `/realms/master/*`, `/metrics` y `/health*` (responden 404). La administración se hace con `kcadm.sh` desde `modal container exec`, nunca desde internet. | Reemplaza la regla de Cloud Armor que restringía `/admin` por IP. |
| **D20** 🆕 | ✅ **Cambiada** (5-oct). Los 150.000 usuarios se importan con el **`partialImport`** de la API de administración (`ifResourceExists=SKIP`), desde la función de Modal `auth_import`, que arranca su propio Keycloak y llama a `127.0.0.1:8081` (el gateway nunca expone `/admin`). Los JSON llegan por un **Volume**, que se vacía al terminar aunque falle. Se hace con el servicio `auth` detenido. | `kc.sh import --dir` solo importa usuarios mientras crea el realm: con el realm ya importado, `--override false` se salta a todos los usuarios y `--override true` borra el realm (verificado en el código de Keycloak 26). `partialImport` es idempotente y no toca el realm. |
| **D21** 🆕 | ✅ **Aprobada** (1-oct). La app de Modal se llama **`krtr-web`** y tiene 5 funciones: `web`, `auth`, `auth_import`, `purge_events` (cron diario, 03:00 COT) y `sync_auth_events` (cada 15 min). Vive en `krtr/back/deploy/`. | Un `modal deploy` despliega todo junto. |
| **D22** 🆕 | ✅ **Aprobada** (1-oct). La cookie temporal del login OIDC (`__Host-krtr_oidc`, guarda `state`, `nonce` y el verificador PKCE) usa **`SameSite=Lax`**. La cookie de sesión sigue en `Strict`. **Todas** las cookies llevan el prefijo `__Host-`. | La vuelta desde Keycloak puede contar como navegación entre sitios distintos. Con `Strict`, esa cookie no llegaría al callback. El prefijo `__Host-` impide que otra app en `modal.run` sobrescriba nuestras cookies. **0.4(d):** `modal.run` no está en la Public Suffix List, así que la vuelta desde Keycloak es del mismo sitio y `Strict` también llegaría. `Lax` sigue siendo válido; lo esencial es el prefijo `__Host-`. |
| **D23** 🆕 | ✅ **Aprobada** (1-oct). Nuevo calendario (§4): salida al aire el **sábado 3-oct**; congelar cambios el **domingo 4-oct** a las 18:00. | La meta del 2-oct ya no es realista con el cambio de plataforma. |

---

## 3. Arquitectura

### 3.1 Vista general

```
                     Navegador (SPA React · es / pt-BR)
                                   │ HTTPS (TLS terminado por Modal)
            ┌──────────────────────┴───────────────────────┐
            ▼ <ws>--krtr.modal.run                         ▼ <ws>--krtr-auth.modal.run
  Modal app "krtr-web" · función web               función auth (1 contenedor)
  @asgi_app · max 1 · us-east (D16)                ┌──────────────────────────────┐
  FastAPI (BFF) + SPA estática  ── OIDC ─────────► │ Gateway ASGI (D19)            │
  · sesiones · CSRF · headers                      │  bloquea /admin, /realms/master│
  · límite por usuario e IP · eventos              │        ▼ 127.0.0.1:8081        │
            │ pooled                               │ Keycloak (realm "krtr")        │
            ▼                                      └──────────────┬─────────────────┘
   Neon DB app: events, app_sessions               Neon DB keycloak (conexión directa)

   Modal Cron ─► purge_events (diario) · sync_auth_events (cada 15 min)
   Modal Volume "krtr-credentials-import" ─► auth_import (kc.sh import, una sola vez)
   Modal Secrets: krtr-web · krtr-auth · krtr-jobs
   GitHub Actions ─► CI (pytest + linters + escáneres) ─► npm build ─► modal deploy
```

### 3.2 Flujos principales

**Login (G5, G6).**
1. En la landing, el usuario elige idioma y pulsa "Iniciar sesión".
2. El navegador va a `GET /auth/login?lang=es`.
3. FastAPI guarda `state`, `nonce` y PKCE en la cookie `__Host-krtr_oidc` (Lax, 10 min) y redirige a Keycloak con `ui_locales`.
4. Keycloak valida `customer_id` + contraseña, aplica el bloqueo por intentos y pide TOTP solo a la cuenta que lo tiene configurado. Al terminar, redirige a `/auth/callback`.
5. FastAPI cambia el código por los tokens, **cierra la sesión anterior**, crea la fila en `app_sessions`, entrega `__Host-krtr_session` (`HttpOnly`, `Secure`, `Strict`), borra `__Host-krtr_oidc` y redirige a `/app`.
6. La SPA llama a `/api/me`. Esa petición es del mismo sitio, así que la cookie `Strict` sí viaja.
7. El navegador **nunca** ve los tokens.

**Sesión (G15)** y **Soporte y chat (G18, G8, G9)**: sin cambios respecto a la v1 (el frontend ya los implementa; ver 5.6–5.9).

### 3.3 Estructura de carpetas

```
krtr/
  back/
    web/          # ✅ FastAPI: app, routers, servir la SPA · ⬜ cases/, chat/
    security/
      audit/ crypto/ headers/          # ✅
      oidc/ sessions/ csrf/ rate_limit/ credentials/   # ⬜
      keycloak/   # ⬜ realm-krtr.json, themes/krtr/, gateway (D19), docker-compose.yml (solo local)
    deploy/       # 🆕 app de Modal "krtr-web": config.py, images.py, app.py (D21)
  front/          # ✅ SPA
  compute/modal/  # ✅ existente: se REUTILIZA (imagen, secretos, volúmenes)
  cli/back/{web,security,deploy}/      # comandos typer, espejo de krtr/back
  database/queries/{events,app_sessions,messages}/   # ✅ (messages: texto del chat, §3.6; creada en Neon el 5-oct)
tests/...  (espejo 1:1)     e2e/{security,browser,load}/  (contra producción)
deploy/gcp/, Dockerfile, .dockerignore  ❌ eliminados en 0.2 (D18, 24d7dba)
```

### 3.4 Contrato de la API (frontend ↔ backend)

Sin cambios respecto a la v1:

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
| `POST /api/events` | Opcional + Origin | `{event_name ∈ catálogo, properties ≤4 KB}` | 202 (✅ hecho) |
| `GET /healthz` | No | — | 200 (✅ hecho) |

Todas las respuestas llevan un `request_id`. Los errores tienen la forma `{error: <code>, message_key}` para que el frontend los traduzca.

### 3.5 Tabla `events` (G21)

✅ Ya existe (commit `d8a728d`). Sin cambios: `id UUID`, `event_name`, `properties BYTEA` (cifrado AES-256-GCM), `occurred_at TIMESTAMPTZ`. La retención es de 3 meses con `purge.sql`. **No** se crean índices (regla del `CLAUDE.md`).

**Catálogo de `EventName`** (el de la v1, ya implementado en `krtr/back/security/audit/event_names.py`; ampliarlo si aparecen eventos nuevos):
- **HTTP:** `http_request` (método, ruta, estado, latencia, IP, user-agent, request_id).
- **Login:** `auth_login_started`, `auth_login_succeeded`, `auth_login_failed`, `auth_logout`, `auth_*` (importados de Keycloak), `session_created`, `session_revoked_by_new_login`, `session_idle_warning_shown`, `session_absolute_warning_shown`, `session_extended`, `session_expired_idle`, `session_expired_absolute`.
- **Interfaz:** `page_view`, `language_changed`, `support_clicked`, `case_mode_selected`, `case_list_viewed`, `case_created`, `case_resume_succeeded`, `case_resume_failed`.
- **Chat:** `chat_message_sent`, `chat_response_received` (metadatos del turno que devuelve el agente: resultado, intención, tipo de coincidencia, alertas, idioma y latencia total y por paso; **nunca el texto**, que va a `messages`), `typing_indicator_shown`.
- **Voz:** `voice_recording_started`, `voice_recording_cancelled`, `voice_recording_sent`, `voice_permission_denied`.
- **Seguridad:** `rate_limit_exceeded`, `csrf_rejected`, `unauthorized_request`, `client_error`, `server_error`.

Nunca se guardan contraseñas, tokens ni cookies en `properties`.

### 3.6 Tabla `messages` (G17, G21) 🆕

🟡 **Código listo (5-oct):** los SQL de `krtr/database/queries/messages/`, `NeonMessageStore` en `krtr/back/ia/messages/store.py` y `KRTR_MESSAGES_KEY`.

✅ **Tabla creada (5-oct)** en `production` y en `dev` con `uv run krtr database neon create-schema messages` (como `neondb_owner`, dueño de `events` y `app_sessions`), con el permiso de `krtr_app` de abajo. Verificado en las dos ramas: 8 columnas, la llave primaria, el índice `messages_incident_customer_idx` y `SELECT, INSERT, DELETE` para `krtr_app`.

Falta:
- generar `KRTR_MESSAGES_KEY` en `.env` (y en el secreto `krtr-web`, 6.1);
- conectarla a la app servida (4.9) y a la purga diaria (4.10 / 6.5).

Guarda el texto de la conversación, separado de `events`, por dos razones:

- **Datos financieros:** las respuestas traen saldos y números de tarjeta enmascarados, que no deben quedar en el log de auditoría.
- **Lectura por caso:** `events` solo se puede consultar por `event_name` y `occurred_at`, así que no permite leer la conversación de un caso para retomarlo.

| Columna | Tipo | Significado |
|---|---|---|
| `message_id` | `UUID` PK | Identificador único del mensaje, generado por la app. |
| `incident_id` | `VARCHAR(30)` | El caso al que pertenece el mensaje (G17). |
| `customer_id` | `VARCHAR(20)` | El cliente dueño del caso. Toda lectura filtra por `incident_id` + `customer_id`. |
| `sender` | `VARCHAR(10)` | Quién lo escribió: `customer` o `agent`. |
| `content` | `BYTEA` | El texto, cifrado con AES-256-GCM (nonce + texto cifrado), como `events.properties`. Nunca se puede leer desde SQL. |
| `language` | `VARCHAR(5)` | `es` o `pt-BR`. |
| `outcome` | `VARCHAR(30)` | Solo en los mensajes del agente: cómo terminó el turno (`resolved`, `needs_clarification`, `escalated`, `closed`). |
| `sent_at` | `TIMESTAMPTZ` | Momento en que se envió, en UTC. |

- **Cifrado:** con una llave propia, `KRTR_MESSAGES_KEY`, separada de `KRTR_EVENTS_KEY` y `KRTR_TOKENS_KEY`, como ya se hace con las otras dos. Va en el secreto `krtr-web` (6.1).
- **Retención:** 3 meses, igual que `events`. La purga (`messages/purge.sql`) corre en la misma función diaria `purge_events` (6.5), así que no hace falta un cron nuevo.
- **Índice:** en `(incident_id, customer_id)`, porque retomar un caso lee por esas dos columnas. Es una excepción **pedida explícitamente** (5-oct) a la regla del `CLAUDE.md` de no crear índices.
- **Permisos:** `GRANT SELECT, INSERT, DELETE ON messages TO krtr_app`, en la rama principal y en `dev`, al crear la tabla (como en 1.3).
- **Quién la implementa:** el vertical de IA (`krtr/back/ia/`, ver [`docs/ia-proposal.md`](ia-proposal.md) y `tasks/todo.md`). Esta guía solo fija el contrato.
- **Pendiente:** dónde vive el resumen del caso (G17). La propuesta es la tabla de casos (4.8), no `messages`.

---

## 4. Estado y calendario

### 4.1 Lo que ya está hecho (rama `web-develop-security`)

| Tarea | Estado | Commit |
|---|---|---|
| Esta guía (v2) | ✅ | `473da5a` |
| 0.2 Retirar artefactos de GCP · 0.3 Quitar referencias a Cloud Run | ✅ | `24d7dba` · `cd2704d` (+ `5a69dc9`: referencias a esta guía) |
| 0.1 Cuenta de Modal · 0.4 Comportamiento de Modal | ✅ 0.4 · 0.1 parcial (faltan créditos y revisar GCP) | — · `0d17496` |
| 4.11 Registrar eventos · 5.11 Lint · 5.12 Favicon | ✅ | `1634b54` · `ea27df2` · `fa1c646` |
| 1.1 Herramientas (Docker con Colima) · 1.3 Neon (roles, base `keycloak`, tablas, rama `dev`) | ✅ (el permiso de auditoría ya está en `dev`; en `production` va en 6.3) | — (configuración fuera del repo) |
| 3.2 Realm `krtr` como código | ✅ | `d272e96` |
| 3.4 Credenciales · 3.5 Importación · 3.6 Prueba en `dev` · 3.7 Gateway | ✅ | `8b327c6` · `7e2ac1f` · `b7c62a4` · `e82b168` |
| 4.5 CSRF · 4.6 Límites · 4.8 Casos · 4.9 Chat (motor de IA) · mensajes de error en el front | ✅ | `827f4b5` · `9491fd7` · `ac6355d` · `a3e60a2` · `48b4641` |
| `customer_id` en mayúsculas al iniciar sesión | ✅ | `01e6854` |
| 4.10 Purga (eventos y mensajes) · 6.1–6.5 App de Modal | ✅ (falta la sincronización de eventos de Keycloak) | `fa1354c` |
| 8.1 Runbook, contrato de la API y README · 6.8 Registro de gasto | ✅ · 🟡 (el registro sigue a diario) | `b4afaae` · `3e1c086` |
| 4.3 Cliente OIDC (BFF) · 4.4 Sesiones del servidor | ✅ | `a7c601a` (clave) · `0af3a00` (OIDC) · `a26970f` (sesiones) · `0f89cd5` (endpoints) |
| 0.5 Reglas de Modal en el `CLAUDE.md` · 3.1 Imagen de Keycloak (local y Modal) | ✅ | `2d8d921` · `a4c2a4e` (CI) · `983cebb` · `bd88576` |
| Test inestable de `chat-page` (fuera de la guía; fallaba 2 de cada 3 veces) | ✅ | `a52ae22` |
| 1.4 Estructura del repo · 1.5 Reglas del front en `CLAUDE.md` · 1.6 Dependencias | ✅ | `43d598d` · `dd51ee2` · `88c3fe9` |
| 2.1 SQL `events` · 2.2 SQL `app_sessions` · 2.3 Pool en `NeonClient` | ✅ | `d8a728d` · `685129f` · `1c4436a` |
| 4.1 Base FastAPI · 4.2 Cabeceras · 4.7 Eventos cifrados | ✅ | `4766468` · `e6e2e3c` · `51d7de8` |
| 5.1–5.10 Frontend completo + diseño visual · quitar mocks | ✅ | `5ed04d1` … `9ebe3b5` · `6543970` · `138ad97` |
| 7.1 Escáneres en CI | ✅ (falta verlo en verde en GitHub) | `43b3d82` |
| 6.1 v1 `Dockerfile` | ❌ retirada en 0.2 (D18) | `67a7a2c` → `24d7dba` |
| 6.2 v1 script de GCP | ❌ retirada en 0.2; la reemplaza 6.1 v2 | `ee70fdb` → `24d7dba` |
| 1.2 Proyecto de GCP · 6.5 Dominio · 6.6 Load Balancer · 6.7 Cloud Armor | ❌ cancelada | — |

### 4.2 Calendario nuevo (D23)

| Día | Qué | Nota |
|---|---|---|
| Jue 1-oct (noche) | Fase 0 | 0.2, 0.3 y 0.4 ✅ (0.4 desbloquea 4.6). De 0.1 faltan los pasos 👤. 0.5 desbloquea la fase 6. |
| Vie 2-oct | Fases 3 y 4 (lo pendiente) + 5.11–5.13 | Fase 3 y fase 4 en paralelo; se juntan en 5.13. |
| Sáb 3-oct | Fase 6 → **salida al aire** + 7.2 y 7.3 | Encender el modo demo (6.8) al salir al aire. |
| Dom 4-oct | 7.4–7.6, 8.1 | **Congelar a las 18:00**: cada deploy reinicia Keycloak. |
| Lun 5-oct | 8.2 Entrega | Colchón. |

---

## 5. Tareas

### Fase 0 — Correcciones por el cambio a Modal 🆕

#### 0.1 👤 Preparar la cuenta de Modal
- **Objetivo:**
  - Confirmar el nombre del **workspace** (define las URLs, D11) y los créditos disponibles este mes. Revisar en *Usage & Billing* cuándo se renuevan.
  - Crear un **token de Modal para CI** y guardarlo como `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` en GitHub Secrets.
  - Si llegó a crearse algo en Google Cloud, cerrarlo para que no genere cobros.
- **Aceptación:** con el extra instalado (`uv sync --extra modal`), `uv run krtr compute modal doctor` pasa y el workspace queda anotado en el PR de la fase 0.
- **Estado (1-oct):** ✅ cuenta creada, token en `.env`, workspace `juan-alvarezo-2002` (D11) y `doctor` en verde (Neon, credenciales y secreto `krtr-neon`). ✅ `MODAL_TOKEN_ID` y `MODAL_TOKEN_SECRET` creados en GitHub Secrets: lo confirmó el usuario, porque sin `gh` no se puede ver desde aquí; se comprobará en la primera corrida de 6.7. ⬜ Falta confirmar: los créditos y su renovación, y que no quedó nada en Google Cloud.
- **Depende de:** —

#### 0.2 🤖 Eliminar los artefactos de GCP ✅ `24d7dba`
- **Objetivo:** borrar `deploy/gcp/` (script de la 6.2 v1), y el `Dockerfile` y el `.dockerignore` (D18). Quitar cualquier referencia a ellos en el README y en el CI.
- **Aceptación:** los tres ya no existen, el README y el CI no los mencionan, y pytest y los linters pasan. El grep de GCP pasó a la 0.3, porque `krtr/` conserva menciones hasta que esa tarea termina.
- **Commit:** `chore(repo): remove Google Cloud deployment artifacts`
- **Depende de:** revisión de D18 (✅ aprobada)

#### 0.3 🤖 Actualizar comentarios y configuración que mencionan Cloud Run ✅ `cd2704d` · `5a69dc9`
- **Objetivo:** dejar los docstrings y comentarios sin referencia a una plataforma concreta, o apuntando a Modal. Archivos:
  - `krtr/database/queries/app_sessions/table.sql`, `krtr/database/queries/events/purge.sql` (Cloud Scheduler → cron `purge_events` de Modal), `krtr/database/neon/config.py`
  - `krtr/back/security/crypto/config.py` (Secret Manager → secreto `krtr-web` de Modal)
  - `krtr/back/security/headers/config.py` y `middleware.py` (`KRTR_AUTH_ORIGIN` = URL de `krtr-auth` en Modal)
  - `krtr/back/web/app.py`, `artifacts.py`, `routers/health.py`
  - `krtr/cli/back/web/handler.py` (`$PORT` se mantiene para desarrollo local)
  - `.github/workflows/ci.yml` (el despliegue continuo ahora es la tarea 6.7, no la 6.8)
- Marcar `docs/pending.md` como reemplazado por la §4.1 de esta guía.
- Apuntar a esta guía las referencias a la v1 en el código, los tests, el CI, el `CLAUDE.md` y el README del front, y poner en la v1 un aviso de que esta guía la reemplaza (commit `5a69dc9`).
- **Aceptación:**
  - No cambia ningún comportamiento; pytest y lint pasan.
  - `grep -rniE "gcp|google cloud|cloud run|run\.app|artifact registry|secret manager|cloud armor|cloud scheduler|us-east4|gcloud|<dominio>" krtr tests .github README.md CLAUDE.md --exclude-dir=node_modules --exclude-dir=dist` no devuelve nada.
- **Commit:** `docs(repo): drop Cloud Run references` (scope `repo` y no `back`: también toca `database/`, `cli/`, el CI y `docs/`)
- **Depende de:** 0.2

#### 0.4 👤🤖 Verificar el comportamiento de la plataforma Modal ✅ `0d17496`
- **Objetivo:** desplegar una app temporal `krtr-probe` (un endpoint que devuelve los headers que recibe) y anotar en `docs/modal-platform.md`:
  - **(a)** Qué cabecera trae la IP real del cliente (`X-Forwarded-For` u otra) y si se puede confiar en ella. Lo necesitan D6 y 4.6.
  - **(b)** Qué versiones de TLS acepta `*.modal.run` (`openssl s_client -tls1`, `-tls1_1`, `-tls1_2`, `-tls1_3`).
  - **(c)** Si `http://` redirige a `https://`.
  - **(d)** Si `modal.run` está en la Public Suffix List (afecta D22).
  - **(e)** Cuánto tarda el arranque en frío de un contenedor pequeño.
  - **(f)** Qué cabeceras agrega Modal a las respuestas (`curl -sI` contra la app de prueba), en especial `Server`: 4.2 y 7.2 exigen no filtrarla, y `server_header=False` solo aplica a `krtr back web serve`. También con qué usuario corre el proceso dentro del contenedor (el `Dockerfile` retirado usaba uno sin privilegios).
- Al terminar, `uv run --env-file .env modal app stop krtr-probe --yes` (sin `--yes`, fuera de una terminal interactiva el comando se cancela).
- **Aceptación:** el documento existe con las 6 respuestas y la evidencia (comandos y salida).
- **Resultado:** [`docs/modal-platform.md`](modal-platform.md). En corto: la IP real llega en `request.client.host` y no en una cabecera, solo se acepta TLS 1.2 y 1.3, `http://` redirige con 308, `modal.run` no está en la Public Suffix List, el arranque en frío toma de 3,6 a 5,8 s, no se agrega `Server` en HTTPS y el contenedor corre como root. Sin región fija, los contenedores cayeron en `us-east` (AWS y Azure) y en `us-central` (GCP).
- **Commit:** `docs(back/deploy): record Modal platform behaviour`
- **Depende de:** 0.1

#### 0.5 🤖 Reglas de `krtr/back/deploy/` en el `CLAUDE.md` 🆕 ✅ `2d8d921` · `a4c2a4e`
- **Objetivo:** hoy el `CLAUDE.md` solo permite importar `modal` dentro de `krtr/compute/modal/`, y solo exceptúa ese entrypoint de la regla de logging. La app de Modal de D21 vive en `krtr/back/deploy/`, así que hay que ampliar ambas reglas, como hizo 1.5 para el frontend:
  - `krtr/back/deploy/` puede importar `modal` a nivel de módulo: solo lo cargan `modal deploy` / `modal serve` y los contenedores de Modal.
  - Los comandos de la CLI que hablan con Modal (`krtr back deploy push-secrets`, `krtr back security import-users`) importan `modal` solo dentro de la función que lo usa, como `krtr/compute/modal/secrets.py`.
  - Las funciones de `krtr/back/deploy/` configuran el logging una sola vez al arrancar el contenedor.
  - El camino local (`krtr back web serve`, pytest) sigue funcionando sin el extra `modal`.
  - Los tests de `krtr/back/deploy/` usan `pytest.importorskip("modal")`, como `tests/compute/modal/test_app.py`. El CI no instala el extra, así que allí esos tests se saltan: decidir si el job `lint-and-test` lo instala.
- **Aceptación:** el revisor humano aprueba el texto.
- **Resultado:** el revisor aprobó el texto (`2d8d921`). Además decidió que el CI instale el extra `modal`, así esos tests corren en GitHub (`a4c2a4e`).
- **Commit:** `docs(repo): add Modal deploy rules to CLAUDE.md`
- **Depende de:** revisión de D21 (✅ aprobada)

### Fase 1 — Preparación

- **1.1** 👤 Herramientas locales: `uv`, Python 3.13, Node LTS, Docker (solo para Keycloak local), `gh`, `git` y la **CLI de Modal** (`uv sync --extra modal` y luego `uv run modal --version`: `modal` es una dependencia opcional). `gcloud` ya no hace falta. ✅ **Estado (2-oct):** Node 24, `uv`, `git` y la CLI de Modal funcionan. Docker funciona con **Colima** (Homebrew, 4 CPU / 8 GB), que arranca solo al iniciar sesión (`brew services`). Se eligió Colima y no Docker Desktop porque la licencia gratuita de Docker Desktop tiene condiciones de tamaño de empresa. ⬜ Falta `gh`, que es opcional.
- **1.2** ❌ Proyecto de GCP: cancelada.
- **1.3** 👤 Preparar Neon: base `keycloak`, rama `dev`, roles `krtr_app`, `krtr_keycloak`, `krtr_audit_reader`, scale-to-zero desactivado. ✅ **Hecha (2-oct)**, salvo el permiso de `krtr_audit_reader` (abajo):
  - La rama principal de Neon se llama **`production`** (no `main`). Proyecto "Hackathon", región AWS **us-east-2** (Ohio). Compute `ep-dawn-forest-b53h756c` (0,25–8 CU) con **scale-to-zero desactivado**: queda encendido 24/7, con su costo.
  - Los roles `krtr_app`, `krtr_keycloak` y `krtr_audit_reader` se crearon **por SQL**. Los creados desde la consola entran en `neon_superuser`, que en este proyecto puede leer y escribir todas las tablas (`pg_read_all_data`, `pg_write_all_data`). Las contraseñas están en `.env` (`KRTR_APP_DB_PASSWORD`, `KRTR_KEYCLOAK_DB_PASSWORD`, `KRTR_AUDIT_DB_PASSWORD`) y en el gestor de contraseñas.
  - La base `keycloak` tiene como dueño a `krtr_keycloak`. Se creó con `SET createrole_self_grant = 'set, inherit'` porque, desde Postgres 16, `CREATE DATABASE … OWNER` exige poder actuar como ese rol.
  - La rama `dev` (compute `ep-wispy-fire-b5ixpa32`, sin borrado automático) se creó desde `production` **después** de todo lo anterior y lo heredó: roles, contraseñas, base, tablas y permisos. Su conexión de administrador está en `.env` como `NEON_DEV_DB_HOST`.
  - Verificado entrando con cada rol en las dos ramas: `krtr_app` solo usa `events` y `app_sessions` (no puede leer `products`); `krtr_keycloak` puede crear tablas en `keycloak`; `krtr_audit_reader` solo entra.
  - ✅ 🆕 **Tablas de la app**, en la rama principal y en `dev`: con el rol dueño, `uv run krtr database neon create-schema events` y `uv run krtr database neon create-schema app_sessions` (el SQL es el de 2.1 y 2.2). Después, `GRANT SELECT, INSERT, UPDATE, DELETE ON events, app_sessions TO krtr_app`. Sin esto, la 4.11 no puede guardar eventos ni la 4.4 sesiones.
  - ✅ en `dev` (3.1) · ✅ en `production` (5-oct, 6.5) — 🆕 **Permiso de `krtr_audit_reader`:** `GRANT SELECT ON event_entity` en la base `keycloak` se da **después del primer arranque de Keycloak** (3.1 en `dev`, 6.3 en producción), porque esa tabla la crea Keycloak. No usar `ALTER DEFAULT PRIVILEGES`: también le daría lectura de `credential`, donde están los hashes de las contraseñas.
- **1.4 · 1.5 · 1.6** ✅

### Fase 2 — Base de datos

- **2.1 · 2.2 · 2.3** ✅

### Fase 3 — Identidad (Keycloak)

#### 3.1 🤖 Imagen de Keycloak (local y en Modal) ✅ `983cebb` · `bd88576`
- **Objetivo:**
  - **Local:** `krtr/back/security/keycloak/docker-compose.yml` con la imagen oficial `quay.io/keycloak/keycloak:<tag>` (fijar la última estable y anotarla) apuntando a la rama `dev` de Neon.
  - **Modal:** en `krtr/back/deploy/images.py`, una imagen `modal.Image.from_registry("quay.io/keycloak/keycloak:<tag>", add_python="3.13")` que ejecuta `kc.sh build --db=postgres --health-enabled=true` y copia el tema y el realm.
  - **Plan B**, si `add_python` falla sobre la imagen oficial (es ubi9-micro): `Image.from_dockerfile` con base `ubi9` y `/opt/keycloak` copiado desde la imagen oficial (multi-etapa), solo para esta imagen.
  - **Configuración en tiempo de ejecución:** `KC_HOSTNAME=https://<ws>--krtr-auth.modal.run`, `KC_HTTP_ENABLED=true`, `KC_HTTP_HOST=127.0.0.1`, `KC_HTTP_PORT=8081`, `KC_PROXY_HEADERS=xforwarded`, `--cache=local`.
- **Aceptación:**
  - En local, `docker compose up` responde `/health/ready` 200.
  - En Modal, la imagen construye (`modal deploy` de prueba o `modal shell` + `kc.sh --version`).
- **Resultado:**
  - **Versión fijada:** Keycloak **26.8.0**, la última estable (salió el 1-oct). La misma versión en local y en Modal, y un test lo verifica.
  - **Local** (`983cebb`): `docker compose --env-file .env -f krtr/back/security/keycloak/docker-compose.yml up -d`, en modo dev, contra la base `keycloak` de `dev` (host directo, sin *pooler*). Los puertos solo escuchan en `127.0.0.1`: 8080 para OIDC y 9000 para `/health/ready`, que responde `UP`.
  - **Primer arranque en local:** tardó unos 10 minutos (237 migraciones a unos 200 ms por consulta). Al final, el `idle_in_transaction_session_timeout` de 5 minutos de Neon cortó la conexión del candado de Liquibase; el candado quedó liberado y los arranques siguientes reutilizan el esquema. Esa misma latencia hará lento el login en local; en Modal no debería pasar, porque está cerca de Neon.
  - **Modal** (`bd88576`): `krtr/back/deploy/images.py` usa la imagen oficial con `add_python`, vacía su `ENTRYPOINT` (`kc.sh`) y corre `kc.sh build --db=postgres --health-enabled=true`. Verificado en un *sandbox*: quedan fijados `kc.db=postgres`, `kc.health-enabled=true` y `kc.optimized=true`; corre como root. El plan B no hizo falta.
  - **`--cache=local`:** en la 26.8 es una opción de arranque y no de construcción, así que va en la 6.3.
  - **Realm y tema:** se agregan a la imagen en la 3.2 y la 3.3.
  - **Permiso de `krtr_audit_reader`:** dado en `dev` (pendiente de la 1.3). Puede leer `event_entity`, pero no `credential` ni `user_entity`.
- **Commit:** `feat(back/security/keycloak): add Keycloak images for local and Modal` (quedó en dos: la parte local y la de Modal, porque la segunda necesitaba la 0.5)
- **Depende de:** 1.3, 0.1, 0.5 (para la parte de Modal)

#### 3.2 🤖 Realm `krtr` como código ✅ `d272e96`
- **Objetivo:** `realm-krtr.json` importable, **sin secretos**. Igual que la v1:
  - Registro, "olvidé mi contraseña", "recordarme" y consola de cuenta desactivados (D5).
  - i18n `es` / `pt-BR`, por defecto `es`.
  - `length(8)`.
  - Protección contra fuerza bruta: 5 fallos → 15 min.
  - SSO Idle 5 min, SSO Max 30 min, access token de 5 min.
  - **User Session Count Limiter** (máximo 1, cierra la más antigua) y **Conditional OTP**.
  - User Profile con email, nombre y apellido opcionales; emails duplicados permitidos (no se importan, D5).
  - Eventos de login y de administración activos, con expiración de 90 días.
  - **Master realm:** fuerza bruta activada, y la contraseña del admin bootstrap sale de un Modal Secret.
- **Clientes:**
  - `krtr-web`: confidencial, PKCE S256, redirect URIs **exactos** `http://localhost:8000/auth/callback` y `https://<ws>--krtr.modal.run/auth/callback`; web origins y post-logout exactos. **No** se incluyen las URLs `-dev` de `modal serve`, salvo que el revisor lo pida.
  - **Ya no** existe el cliente `krtr-importer` (D20).
- **Aceptación:** en local, un usuario de prueba entra con `customer_id` + contraseña, queda bloqueado al sexto intento y un segundo login cierra la sesión anterior.
- **Resultado:**
  - **Cómo se armó:** `krtr/back/security/keycloak/realm-krtr.json` (unas 2.850 líneas) se configuró en el Keycloak local con la API de administración y se exportó. Se probó borrando el realm y reimportándolo desde el archivo: **22 de 22 verificaciones OK**, entre ellas la aceptación (login con `customer_id`, canje del código con secreto y PKCE, 1 sola sesión, bloqueo al 6.º intento, ES/PT, sin registro ni recuperación).
  - **Flujo de login:** `krtr browser` es la copia del flujo de la 26.8, que ya trae el OTP condicional ("Conditional 2FA"), más `user-session-limits` (1 sesión, cierra la más antigua).
  - **Secretos:** el de `krtr-web` es el placeholder `${KRTR_WEB_OIDC_CLIENT_SECRET}`, que Keycloak resuelve del entorno al importar (en `.env`, y en producción por los secretos de la 6.1). Las llaves del realm no están en el archivo: Keycloak las genera al importar.
  - **Ojo:** la importación usa la estrategia **IGNORE_EXISTING**. Si el realm ya existe, los cambios al JSON no se aplican: en local hay que borrar el realm y reiniciar; en producción solo cuenta la primera importación.
  - **Realm `master`:** la protección contra fuerza bruta se activó a mano en local; la 6.3 la repite en producción.
  - **Tests** (`tests/back/security/keycloak/`): fallan si un nuevo export filtra un secreto o pierde estos ajustes, y si el `docker-compose.yml` publica puertos fuera de `127.0.0.1`.
- **Commit:** `feat(back/security/keycloak): add krtr realm configuration`
- **Depende de:** 3.1

#### 3.3 🤖 Tema de login mínimo "krtr" ✅ `a6b1b8f` · `dec1d57`
- **Objetivo:** `themes/krtr/login` extendiendo el tema base, con el nombre krtr, el selector ES/PT y CSS sin estilos inline. Debe seguir la línea visual de `docs/krtr diseño.html` en lo básico (colores y tipografía).
- **Aceptación:** la pantalla de login se ve en ES y en PT según `ui_locales`.
- **Commit:** `feat(back/security/keycloak): add krtr login theme`
- **Resultado (5-oct):**
  - `krtr/back/security/keycloak/themes/krtr/login` hereda de `base` (no de `keycloak.v2`) y copia la pantalla de login de `docs/krtr diseño.html`: cabecera con la marca y el selector ES/PT, título a la izquierda y formulario a la derecha. Usa la tipografía Archivo (servida desde el tema, sin Google Fonts) y los colores del diseño, todo en `css/krtr.css` y sin estilos inline. Las propiedades `kc*Class` de `theme.properties` aplican las mismas clases a las demás páginas de `base` (OTP, acciones requeridas, errores).
  - Textos propios en `messages_es` y `messages_pt_BR` ("Número de cliente", la pista del bloqueo tras 5 intentos); el resto sale de `base`.
  - **Local:** el `docker compose` monta el tema (en modo dev, los cambios se ven sin reiniciar). Verificado con Chrome en escritorio y en móvil: ES, PT y el error de credenciales, sin errores de consola; CSS, fuentes, logo y JS responden 200.
  - **Producción:** la imagen de Keycloak copia el tema a `/opt/keycloak/themes/krtr` (`images.py`; un test comprueba que la carpeta coincide con el `loginTheme` del realm). Como el realm ya existía (IGNORE_EXISTING), `loginTheme=krtr` se aplicó con `kcadm.sh` dentro del contenedor de `auth`. Verificado en `https://<ws>--krtr-auth.modal.run`: la pantalla sale en ES y en PT según `ui_locales`, y no quedó `/tmp/kc.cfg` en el contenedor.
- **Depende de:** 3.2

#### 3.4 🤖 Generador de credenciales (G6) ✅ `8b327c6`
- **Objetivo:** comando `krtr back security generate-credentials`. Mismo comportamiento que en la v1:
  - **(a)** Contraseña aleatoria de 8 caracteres (mayúsculas, minúsculas y dígitos) con `secrets`, para los 150.000 `customer_id`.
  - **(b)** Hash argon2id en el formato que importa Keycloak (verificar con la versión fijada en 3.1). Usar multiproceso.
  - **(c)** JSON por lotes de 1.000, **en el formato de `kc.sh import --dir`** (archivos `krtr-users-N.json` con `"realm": "krtr"`), en `data/credentials/import/`.
  - **(d)** Elige al azar, con semilla registrada, **50 Active para el jurado** y **50 Active para QA**, sin que se repitan.
  - **(e)** Escribe `data/credentials/jury_credentials.csv` y `qa_credentials.csv`.
  - **(f)** **No guarda** las demás contraseñas en claro.
- **Aceptación:** los tests de comportamiento de la v1 + un test que comprueba que los JSON cumplen el formato de `kc.sh import`.
- **Commit:** `feat(back/security/credentials): generate customer credentials`
- **Resultado:** `uv run krtr back security credentials generate` (se agrupa bajo `credentials`, como manda el espejo del CLI). Lee `data/customers.parquet` (150.000 IDs `CLI-XXXXXXXXXXXX`, 127.700 Active), y escribe 150 archivos `krtr-users-N.json`, `jury_credentials.csv`, `qa_credentials.csv` y `manifest.json` (con la semilla), todos con permisos `600`. El hash es argon2id con los parámetros por defecto de Keycloak 26.8 (5 iteraciones, 7 MB); se verificó iniciando sesión con el formulario real del Keycloak local. Las 150.000 cuentas tardan 3 min 52 s con 15 procesos. No reescribe una corrida anterior sin `--overwrite`.
- **Depende de:** 1.6

#### 3.5 🤖 Importación de usuarios con `partialImport` (D20) ✅ `7e2ac1f` · `b7c62a4`
- **Objetivo:** comando `krtr back security import-users --source data/credentials/import [--local]`.
  - **Local:** monta la carpeta en el `docker compose` y ejecuta `kc.sh import --dir … --override false`.
  - **Modal:** **reutiliza `krtr/compute/modal/volume.py` y `staging.py`** para subir los JSON al Volume `krtr-credentials-import`. Luego llama a la función `auth_import` (6.4), que ejecuta `kc.sh import` contra la base `keycloak` de producción. Al terminar, borra el contenido del Volume.
  - Al final muestra un resumen: archivos procesados y usuarios importados.
  - Es idempotente (`--override false` omite los que ya existen).
- **Aceptación:**
  - Los tests (con Volume y ejecutor simulados) cubren la subida, la invocación y la limpieza del Volume aunque la importación falle.
  - Si Keycloak está corriendo, el comando avisa y pide `--force`.
- **Commit:** `feat(back/security/credentials): import users with kc.sh import`
- **Resultado (cambia D20):** `uv run krtr back security credentials import` (local) y `... import --remote` (producción). Cada archivo se manda en tramos de 100 usuarios por `partialImport`, porque Keycloak aborta una petición a los 300 s. En remoto sube los archivos al Volume `krtr-credentials-import`, ejecuta `auth_import` y vacía el Volume siempre; se niega si `auth` tiene contenedores, salvo con `--force`. El cliente de administración renueva su token de 60 s durante la importación.
- **Depende de:** 3.2, 3.4

#### 3.6 👤🤖 Probar la importación en `dev` ✅
- **Objetivo:** importar primero 1.000 usuarios y después los 150.000 en local (Neon `dev`).
- **Aceptación:**
  - 3 cuentas del jurado entran bien y una contraseña incorrecta es rechazada.
  - Se anota cuánto tardó (sirve para planear 6.7).
- **Depende de:** 3.5
- **Resultado:** en `dev` se importaron 2.000 usuarios (los dos archivos con 3 cuentas del jurado) en 293 s: desde Colombia cada consulta a Ohio tarda ~200 ms, así que los 150.000 en local tardarían ~6 h y no se hizo. Las 3 cuentas del jurado entran con el formulario real, una contraseña incorrecta se rechaza, y una segunda corrida no agrega a nadie (2.000 ya existentes).

#### 3.7 🤖 Gateway delante de Keycloak (D19) 🆕 ✅ `e82b168`
- **Objetivo:** `krtr/back/security/keycloak/gateway.py`, una app ASGI (Starlette + `httpx.AsyncClient`) que:
  - Reenvía todo a `http://127.0.0.1:8081`, conservando el método, el cuerpo, los headers (incluidos varios `Set-Cookie`) y las redirecciones.
  - Agrega `X-Forwarded-Proto: https`, `X-Forwarded-Host` y `X-Forwarded-For`, **reemplazando** lo que mande el cliente: `X-Forwarded-For` sale de `request.client.host`. Descarta `Forwarded` y `X-Real-IP`, que Modal deja pasar sin tocar (0.4a).
  - Responde **404** a `/admin/*`, `/realms/master/*`, `/metrics`, `/health*`.
  - Aplica las cabeceras de seguridad del vertical `headers/` que correspondan, reutilizando ese código.
- **Aceptación:** los tests (con `respx`) cubren las rutas bloqueadas (404, sin llegar a Keycloak), el reenvío de `Set-Cookie` múltiples, las redirecciones 302 sin reescribir y un timeout (→ 504).
- **Commit:** `feat(back/security/keycloak): add gateway that hides admin endpoints`
- **Resultado:** `krtr/back/security/keycloak/gateway.py`. Normaliza la ruta antes de comparar (barras repetidas, `.`/`..`, parámetros `;`, mayúsculas) y reenvía a Keycloak exactamente la ruta revisada, así `//admin`, `/x/../admin` o `/ADMIN` también dan 404. Agrega las cabeceras de seguridad que Keycloak no pone, quita `Server`, y responde 413 a cuerpos de más de 64 KB y 502 si Keycloak no está.
- **Depende de:** 1.6

### Fase 4 — Backend (FastAPI)

- **4.1 · 4.2 · 4.7** ✅

#### 4.3 🤖 Cliente OIDC (BFF) ✅ `0af3a00` · `0f89cd5`
- **Objetivo:** `/auth/login`, `/auth/callback` y `/auth/logout` con Authlib.
  - `state`, `nonce` y PKCE S256 guardados en `__Host-krtr_oidc` (cifrada, **SameSite=Lax**, 10 min, D22).
  - `ui_locales` según `lang`.
  - Validar el ID token (issuer, audience, firma, `nonce`, expiración).
  - Logout RP-initiated y revocación del refresh token.
  - Las URLs de Keycloak salen de la configuración (`KRTR_AUTH_ORIGIN`).
- **Aceptación:**
  - Los tests con Keycloak simulado cubren el callback correcto, el `state` inválido y el `nonce` inválido (→ 400 + evento; desde la 4.4, → 302 a `/?login=failed` + evento), y que el logout limpia la sesión.
  - La cookie temporal es `Lax` y se borra después del callback.
  - Se registran `auth_login_started`, `auth_login_succeeded`, `auth_login_failed` y `auth_logout`.
- **Commit:** `feat(back/security/oidc): add OIDC login flow` (quedó en `0af3a00`, el núcleo, y `0f89cd5`, los endpoints junto con los de la 4.4)
- **Cómo quedó:**
  - El ID token se valida con **joserfc** (de los autores de Authlib), porque `authlib.jose` está deprecado. De Authlib solo se usa el reto PKCE.
  - La cookie temporal se cifra con `KRTR_TOKENS_KEY` (`a7c601a`), la misma clave que cifra los tokens de las sesiones. Cambiarla cierra todas las sesiones.
  - El callback compara el `state` en tiempo constante **antes** de mirar `error` o `code`. Los motivos de rechazo de `auth_login_failed` son los de `LoginFailureReason`.
  - En producción la app no arranca sin `KRTR_WEB_OIDC_CLIENT_SECRET` y `KRTR_TOKENS_KEY`. Con `KRTR_WEB_ENVIRONMENT=development` arranca igual, y las rutas de login responden 503 `auth_unavailable`.
- **Depende de:** 3.2, 4.1

#### 4.4 🤖 Sesiones del servidor (G15) ✅ `a26970f` · `0f89cd5`
- Igual que la v1:
  - Token de 256 bits en `__Host-krtr_session` (`HttpOnly`, `Secure`, `Strict`); en la base solo el hash; tokens OIDC cifrados.
  - Inactividad de 5 min, máximo de 30 min, revocar la sesión anterior.
  - `/api/me` y `/api/session/activity`; refrescar el access token cuando falte menos de 60 s; rotar el id al hacer login.
- **Aceptación:** los tests de la v1 + se registran `session_created`, `session_revoked_by_new_login`, `session_expired_idle`, `session_expired_absolute` y `unauthorized_request` (cubre P5.4).
- **Commit:** `feat(back/security/sessions): add server-side sessions` (quedó en `a26970f` y `0f89cd5`)
- **Cómo quedó:**
  - `GET /api/me` **no** cuenta como actividad; solo `POST /api/session/activity` corre el plazo de inactividad. Así, consultar el estado no mantiene viva una sesión ociosa.
  - Si Keycloak rechaza el refresh (por ejemplo, porque un admin desactivó al usuario), la sesión se revoca y la petición responde 401 `unauthorized`.
  - Verificado de punta a punta: login con el formulario real de Keycloak, `/api/me`, actividad, sesión única y logout (13 de 13).
- **Puntos abiertos:**
  - **CSRF:** `POST /auth/logout` y `POST /api/session/activity` todavía no exigen el token CSRF. La 4.5 debe cubrirlos.
  - **Frontend:** los locales tienen `session_expired_idle_message` y `session_expired_absolute_message`, pero faltan `unauthorized`, `login_failed` y `auth_unavailable`. Además, un callback rechazado responde 400 con JSON (como pide la aceptación), y el navegador lo muestra tal cual. Hay que decidir si conviene redirigir a la página de inicio con un aviso.
  - ✅ **Resuelto (5-oct):** las tres claves ya estaban en los locales. Un callback rechazado ahora responde **302 a `/?login=failed`** y la landing muestra un aviso (`role="alert"`) con `login_failed`, en ES o PT según el idioma guardado. El motivo no viaja en la URL: sigue solo en el evento `auth_login_failed`, que no cambió. Se quitó el código de error `login_failed` de la API, que ya nadie usaba. ⬜ Requiere desplegar.
- **Depende de:** 2.2, 2.3, 4.3

#### 4.5 🤖 Protección CSRF ✅ `827f4b5`
- Igual que la v1: validar `Origin`/`Referer` contra la URL pública de la app (configurable) + double-submit (`__Host-krtr_csrf` + cabecera `X-KRTR-CSRF`).
- **Importante:** como `modal.run` es un dominio compartido entre muchas apps, `SameSite` **no basta**; estos dos controles son obligatorios.
- **Aceptación:** sin cabecera, con token distinto o con Origin ajeno (incluso otro `*.modal.run`) → 403 + `csrf_rejected`.
- **Commit:** `feat(back/security/csrf): add CSRF protection`
- **Resultado:** la cookie `__Host-krtr_csrf` se crea al iniciar sesión (no es `HttpOnly`, porque la SPA la copia en `X-KRTR-CSRF`) y se borra con la sesión. `POST /api/events` solo exige el `Origin` (la landing manda eventos antes de que haya sesión). Sin sesión la respuesta es 401, no 403, para que la SPA vuelva a la landing.
- **Depende de:** 4.4

#### 4.6 🤖 Límites de peticiones ✅ `9491fd7`
- **Objetivo:**
  - 20 mensajes por minuto por `customer_id` en `/api/chat/*`.
  - Un límite moderado por sesión en `/api/*`.
  - **🆕 Un límite por IP de 600 peticiones por minuto** en todo el sitio (D6), con la IP tomada **solo** de la fuente confirmada en 0.4(a): `request.client.host`, nunca de una cabecera.
  - Respuesta 429 con `Retry-After` y evento `rate_limit_exceeded`.
- **Aceptación:**
  - El mensaje 21 da 429.
  - La petición 601 desde la misma IP da 429.
  - Un `X-Forwarded-For`, `X-Real-IP` o `Forwarded` falsificado por el cliente no evade el límite (0.4a).
- **Commit:** `feat(back/security/rate_limit): add per-user and per-IP rate limiting`
- **Resultado:** ventanas deslizantes en memoria (un solo contenedor, D8): 20 mensajes por minuto por cliente en el chat, 240 por minuto por sesión en `/api/*` y 600 por minuto por IP. Los límites corren dentro del log, la auditoría y las cabeceras, así que un 429 también queda registrado y endurecido.
- **Depende de:** 4.4, 0.4

#### 4.8 🤖 Casos (datos de prueba, G18) ✅ `ac6355d`
- Igual que la v1: interfaz `CaseRepository` + `StubCaseRepository`; coincidencia exacta `incident_id` + `customer_id`; un caso inexistente y uno ajeno dan **el mismo 404**.
- **Commit:** `feat(back/web/cases): add case endpoints with stub repository`
- **Resultado:** `StubCaseRepository` en memoria: 2 casos de prueba por cliente más los que abra; IDs `INC-` + 10 caracteres aleatorios. Abrir y retomar exigen CSRF.
- **Depende de:** 4.4, 4.5

#### 4.9 🤖 Chat de texto y voz ✅ `a3e60a2`
- Igual que la v1: `ChatResponder` + `StubChatResponder` (D15); validación de texto, idioma, content-type, **magic bytes**, 2 MB y 60 s; el audio no se guarda.
- **Commit:** `feat(back/web/chat): add chat endpoints with stub responder`
- **Resultado:** la app servida responde con el **motor de IA** de `krtr/back/ia/` (`AgentChatResponder`), sobre lectores de Neon nuevos para `products` y `complaints` y la tabla `messages` cifrada; sin Neon, en desarrollo, responde el texto de D15. El patrón del ID de queja sigue el formato real (`CMP-` + 20 caracteres). La voz se valida (tipo, bytes mágicos, 2 MB) y responde el texto de D15, porque la voz a texto está fuera de alcance; la duración no se valida en el servidor (el front corta a 60 s). Cada respuesta registra `chat_response_received` con los metadatos del turno y la latencia, nunca el texto. Un límite global de `Content-Length` rechaza cuerpos grandes antes de leer el multipart.
- **Depende de:** 4.5, 4.6

#### 4.10 🤖 Jobs de eventos (como funciones, sin programación) ✅ `fa1354c` · `95d22ab`
- **Objetivo:**
  - Funciones del vertical `audit/`: `purge_expired_events()` (ejecuta `purge.sql` y registra cuántas filas borró) y `sync_auth_events()` (lee `event_entity` desde la última marca y los inserta como `auth_*` cifrados, D3).
  - Comandos CLI `krtr back security purge-events` y `sync-auth-events` que las llaman.
  - **La programación la pone Modal** (6.5).
- **Aceptación:** los tests cubren la idempotencia de la sincronización y que la purga no borra eventos recientes.
- **Commit:** `feat(back/security/audit): add purge and Keycloak event sync jobs` (quedó en `fa1354c`, la purga, y `95d22ab`, la sincronización)
- **Resultado (5-oct):**
  - `sync_auth_events()` en `krtr/back/security/audit/keycloak_sync.py`. Lee `event_entity` como `krtr_audit_reader` (variable `KRTR_AUDIT_DB_URL`) y guarda cada evento como **`auth_keycloak_<tipo>`** (`auth_keycloak_login`, `auth_keycloak_login_error`, `auth_keycloak_logout`, `auth_keycloak_user_disabled_by_temporary_lockout`…). El prefijo evita que choque con los `auth_*` de la app, como su `auth_logout`.
  - **Marca e idempotencia:** la fila conserva el id del evento de Keycloak, y `events/insert_new.sql` usa `ON CONFLICT (id) DO NOTHING`. La marca es el último `auth_keycloak_*` de `events` menos 15 min de solape, para atrapar eventos que Keycloak confirme tarde. No hace falta tabla nueva. La primera corrida copia todo lo que Keycloak guarda (90 días).
  - `properties` (cifrado) lleva el tipo, el realm, el cliente, el usuario y la sesión de Keycloak, la IP, el error y los detalles (que traen el `customer_id` en `username`). Se descarta cualquier detalle con nombre de credencial, igual que en `EventRecorder`.
  - **CLI:** `uv run krtr back security audit sync-auth-events`. Va bajo `audit` por el espejo del CLI, como `credentials`. Para correrlo a mano hace falta `KRTR_AUDIT_DB_URL` en `.env` (ver `.env.example`). No se hizo un comando `purge-events`: la purga se corre con `modal run` (README).
  - Verificado contra `dev`: la primera corrida copió 45 eventos y la segunda 0 nuevos; las propiedades se descifran con `KRTR_EVENTS_KEY`.

#### 4.11 🤖 Registrar eventos en la app servida 🆕 ✅ `1634b54`
- **Objetivo:** hoy `krtr/back/web/app.py` crea `app = create_app()` sin `EventRecorder`, así que la app servida (con `krtr back web serve` o en Modal) descarta todos los eventos y solo deja un warning en el log. Ninguna tarea lo conectaba. Hay que construir el `EventRecorder` (pool de `NeonClient` + `AesGcmCipher` con `KRTR_EVENTS_KEY`) desde el entorno para la app servida. Los tests siguen inyectando el suyo.
  - Ojo: `krtr/back/web/app.py` ejecuta `create_app()` al importarse, y los tests importan ese módulo. La conexión a Neon no puede exigirse al importar.
- **Aceptación:**
  - Con `NEON_DB_HOST` y `KRTR_EVENTS_KEY` definidos, cada petición deja un `http_request` en `events` y `POST /api/events` guarda el evento.
  - En producción, si falta alguna de las dos variables, la app no arranca y el error dice cuál falta, en lugar de descartar eventos (G21). _Aprobado el 1-oct._
- **Resultado:** `EventRecorder.from_environment()` valida la clave antes de abrir Neon. `create_served_app()` carga `.env` y conecta el grabador; en desarrollo, si falta algo, solo avisa. `krtr back web serve` usa esa fábrica (uvicorn `factory=True`) y ya no existe el `app` a nivel de módulo. Verificado con tests y arrancando el servidor real. ⬜ Falta ver los eventos en Neon, que requiere las tablas de la 1.3; queda para 5.13.
- **Commit:** `feat(back/web): record events in the served app`
- **Depende de:** 4.7

### Fase 5 — Frontend

- **5.1–5.10** ✅ (incluye el diseño visual y la eliminación de los mocks)

#### 5.11 🤖 Lint sin advertencias (P5.2) ✅ `ea27df2`
- **Objetivo:** mover `buttonVariants` fuera de `components/ui/button.tsx`, o desactivar la regla solo para los componentes de shadcn, con una justificación.
- **Aceptación:** `npm run lint` da 0 advertencias.
- **Resultado:** nadie importaba `buttonVariants`, así que se dejó de exportar; no hizo falta ninguna de las dos opciones.
- **Commit:** `style(front): fix react-refresh lint warning`

#### 5.12 🤖 Servir el favicon (P5.5) ✅ `fa1c646`
- **Objetivo:** mover `favicon.svg` a `src/assets/` y referenciarlo desde `index.html`.
- **Aceptación:** `/assets/…favicon….svg` responde 200 con `image/svg+xml`.
- **Resultado:** Vite lo publica como `/assets/favicon-<hash>.svg`, que responde 200 con `image/svg+xml` en `krtr back web serve`. La carpeta `public/` ya no existe.
- **Commit:** `fix(front): serve favicon from assets`

#### 5.13 👤🤖 Recorrido completo en local (P5.3)
- **Objetivo:** con `krtr back web serve` + Keycloak en `docker compose` + Neon `dev`, recorrer login → soporte → caso → chat → voz → cerrar sesión, en ES y en PT.
- **Aceptación:** el recorrido funciona sin errores en la consola y aparecen en `events` tanto los eventos del front como los del servidor (P5.4).
- **Depende de:** 3.6, 3.7, 4.3–4.11

### Fase 6 — Despliegue en Modal 🆕 (reemplaza toda la fase 6 de la v1)

#### 6.1 🤖 Secretos de Modal ✅ `fa1354c`
- **Objetivo:** comando `krtr back deploy push-secrets`, que **reutiliza `krtr/compute/modal/secrets.push_secret`**. Crea o actualiza 3 secretos:

  | Secreto | Contenido | Lo usa |
  |---|---|---|
  | `krtr-web` | URL de Neon (app, pooled), `KRTR_EVENTS_KEY`, `KRTR_TOKENS_KEY`, `KRTR_MESSAGES_KEY` (🆕 v2.5, §3.6), secreto del cliente OIDC, `KRTR_PUBLIC_URL`, `KRTR_AUTH_ORIGIN` | `web` |
  | `krtr-auth` | `KC_DB_URL`/usuario/contraseña (base `keycloak`, directa), contraseña del admin bootstrap, secreto del cliente OIDC (para el realm) | `auth`, `auth_import` |
  | `krtr-jobs` | URL de Neon (app), URL de auditoría (rol de solo lectura), `KRTR_EVENTS_KEY` | `purge_events`, `sync_auth_events` |

  - Las URLs de Neon se leen de `.env` con una **lista explícita de variables permitidas**.
  - Las llaves AES y los secretos se generan con `secrets` **solo si no existen** (no rota sin `--rotate`).
  - **Nunca** imprime valores.
- **Aceptación:**
  - Los tests (con Modal simulado) verifican qué variables van a cada secreto y que nada se escribe en los logs.
  - `uv run --env-file .env modal secret list` muestra los 3 secretos.
- **Commit:** `feat(back/deploy): push Modal secrets for web, auth and jobs`
- **Depende de:** 0.1, 0.2, 0.5

#### 6.2 🤖 Función `web` ✅ `fa1354c`
- **Objetivo:** `krtr/back/deploy/app.py` define `app = modal.App("krtr-web")` y la función `web`:
  - Imagen: **extraer** la construcción de imagen de `krtr/compute/modal/app.py` a una función compartida (DRY) y agregarle `add_local_dir("krtr/front/dist", "/app/frontend")`.
  - 🆕 v2.6: la imagen también **incluye los pesos del modelo de embeddings** del agente (`multilingual_minilm`, unos 220 MB, ver `tasks/todo.md`, fase 2 de IA). Se descargan al construir la imagen, no en el arranque en frío, y `KRTR_IA_EMBEDDING_MODEL` elige el modelo.
  - 🆕 v2.7: la imagen también incluye el **build ONNX int4 de Qwen2.5-1.5B-Instruct** (el LLM local del agente, unos 1 GB en disco y cerca de 2 GB de memoria; ver `tasks/todo.md`, fase 3 de IA). Se convierte una vez a partir del repo oficial y se copia a la imagen; nunca se descarga en el arranque. La función `web` necesita más memoria (Q3-B), lo que consume más rápido los créditos (D17). `KRTR_IA_LLM_MODEL=none` la desactiva.
  - 🆕 v2.6: **origen de los textos del agente.** En producción, el texto del cliente llega directo desde la página (`/api/chat/messages`), y el agente no lee textos de los datos. Los textos de Neon (quejas, categorías) solo se usan **fuera de línea**, para armar el catálogo y el conjunto de evaluación.
  - Conservar lo que hacía el `Dockerfile` retirado en 0.2:
    - Las variables `KRTR_WEB_FRONTEND_DIST_DIR=/app/frontend` y `KRTR_WEB_ENVIRONMENT=production`. Sin la primera, la app busca el front en la ruta relativa `krtr/front/dist`.
    - Instalar sin el grupo `dev` (`uv_sync(..., extra_options="--no-dev")`). El `uv_sync` de Modal no lo excluye por defecto, así que bandit, locust, playwright y las demás herramientas de desarrollo llegarían a producción.
  - `@modal.asgi_app(label="krtr")` + `@modal.concurrent(max_inputs=50)`.
  - `cpu=0.25`, `memory=512`, `max_containers=1`, `min_containers` según `KRTR_WARM` (D17), `region` según D16, `secrets=[krtr-web]`.
  - Sirve `create_served_app()` (4.11), la misma fábrica que usa `krtr back web serve`, que ya incluye el registro de eventos.
- **Aceptación:**
  - `uv run --env-file .env modal serve krtr/back/deploy/app.py` sirve la SPA y `/healthz` en la URL `-dev`.
  - Hay un test que comprueba la configuración de la función (recursos, etiqueta, secretos) sin llamar a Modal.
- **Commit:** `feat(back/deploy): serve krtr-web on Modal`
- **Depende de:** 6.1, 4.11

#### 6.3 🤖 Función `auth` (Keycloak + gateway) ✅ `fa1354c`
- **Objetivo:** en la misma app:
  - Función `auth` con la imagen de 3.1, `cpu=1`, `memory=1536`, `max_containers=1`, `min_containers` según `KRTR_WARM`, región según D16, `secrets=[krtr-auth]`.
  - Un `@modal.enter` arranca `kc.sh start --optimized --import-realm` (escuchando en `127.0.0.1:8081`) y **espera** a que `/health/ready` responda (timeout de 180 s).
  - Lo aprendido en la 3.1 que afecta a esta tarea:
    - `/health/ready` está en el **puerto de gestión 9000**, no en el 8081.
    - `--cache=local` va en el arranque.
    - El **primer** arranque contra `production` aplica 237 migraciones. Si tarda más que el timeout, hay que hacer un arranque de calentamiento antes de salir al aire.
    - Después de ese arranque, como `krtr_keycloak`, dar `GRANT SELECT ON event_entity TO krtr_audit_reader` (1.3).
    - Activar la protección contra fuerza bruta del realm `master` (5 fallos → 15 min) con `kcadm.sh` (3.2).
    - Pasarle a la función `auth` la variable `KRTR_WEB_OIDC_CLIENT_SECRET` (secreto `krtr-auth`), que el realm usa al importarse (3.2).
  - `@modal.asgi_app(label="krtr-auth")` devuelve el gateway de 3.7.
- **Aceptación:**
  - Desplegado, `https://<ws>--krtr-auth.modal.run/realms/krtr/.well-known/openid-configuration` responde 200 y su `issuer` es esa URL.
  - `/admin/` responde 404.
- **Commit:** `feat(back/deploy): run Keycloak behind the gateway on Modal`
- **Depende de:** 3.1, 3.2, 3.3, 3.7, 6.1

#### 6.4 🤖 Función `auth_import` ✅ `fa1354c`
- **Objetivo:** función con la imagen de Keycloak, que monta el Volume `krtr-credentials-import` y ejecuta `kc.sh import --dir /import --override false`. `timeout` amplio (según lo medido en 3.6) y `secrets=[krtr-auth]`. Solo se invoca desde 3.5; no se publica en la web.
- **Aceptación:** con 1.000 usuarios en Neon `dev` (cambiando el secreto de forma temporal), la importación termina y el comando de 3.5 muestra el resumen.
- **Commit:** `feat(back/deploy): add Keycloak import function`
- **Depende de:** 3.5, 6.3

#### 6.5 🤖 Crons 🟡 purga programada (`fa1354c`) · sincronización lista sin desplegar (`ec237aa`)
- **Objetivo:** funciones `purge_events` con `schedule=modal.Cron("0 8 * * *")` (03:00 COT) y `sync_auth_events` con `schedule=modal.Period(minutes=15)`. Ambas con `cpu=0.125`, `secrets=[krtr-jobs]`, y llaman a las funciones de 4.10.
  - 🆕 v2.5: `purge_events` también ejecuta `messages/purge.sql` (retención de 3 meses, §3.6). Siguen siendo 2 crons.
- **Aceptación:** al ejecutarlas a mano (`uv run --env-file .env modal run …`), terminan bien y dejan logs.
- **Commit:** `feat(back/deploy): schedule event purge and Keycloak sync` (quedó en `fa1354c`, la purga, y `ec237aa`, la sincronización)
- **Depende de:** 4.10, 6.2
- **Resultado (5-oct):**
  - `sync_auth_events` está en `krtr/back/deploy/app.py` con `modal.Period(minutes=15)`, `cpu=0.125` y `krtr-jobs`, y llama a la función de 4.10.
  - `krtr-jobs` lleva ahora `KRTR_AUDIT_DB_URL` (la base `keycloak` en el host directo, como `krtr_audit_reader`), armada en `krtr/back/deploy/secrets.py` desde `KRTR_AUDIT_DB_PASSWORD`. Subido con `push-secrets` el 5-oct.
  - `GRANT SELECT ON event_entity TO krtr_audit_reader` dado en `production` el 5-oct, como `krtr_keycloak` y sin `ALTER DEFAULT PRIVILEGES`. Verificado: el rol lee `event_entity` (120 eventos) y no puede leer `credential` ni `user_entity`.
  - ⬜ **Falta desplegar** (`KRTR_WARM=true uv run --env-file .env modal deploy -m krtr.back.deploy.app`) y correrla una vez a mano. La rama `keycloak-theme` ya incluye `security-tests`, que es lo que corre hoy en producción (v9). Quien despliegue después tiene que partir de una rama con las dos; si no, el cron desaparece.

#### 6.6 👤🤖 Primer despliegue y datos de producción ✅ (5-oct)
- **Objetivo:**
  1. `npm run build --workspace krtr/front` y `KRTR_WARM=false uv run --env-file .env modal deploy krtr/back/deploy/app.py`.
  2. Anotar las 2 URLs reales. Confirmar que coinciden con `KRTR_PUBLIC_URL`, `KRTR_AUTH_ORIGIN`, los redirect URIs del realm y `KC_HOSTNAME`; si no, corregirlas y volver a desplegar.
  3. **Importar usuarios** (3.5 contra producción) mientras Keycloak no tiene contenedores activos (D20).
  4. Crear la **cuenta con MFA**: `uv run --env-file .env modal container exec <id> /opt/keycloak/bin/kcadm.sh …` contra `127.0.0.1:8081`, con la acción requerida "Configure OTP"; enrolar TOTP.
  5. Guardar las credenciales QA en GitHub Secrets.
- **Aceptación:**
  - En `https://<ws>--krtr.modal.run`, el recorrido login → soporte → chat → voz → cerrar sesión funciona en ES y en PT.
  - Una cuenta del jurado entra, la cuenta con MFA pide TOTP y una cuenta QA entra.
- **Depende de:** 6.2–6.5, 5.13
- **Resultado (5-oct):**
  - Desplegado con `KRTR_WARM=true uv run --env-file .env modal deploy -m krtr.back.deploy.app`. Por ruta de archivo fallaba (`No module named 'app'`), porque la imagen lleva las fuentes de `krtr` y no el archivo suelto. Las URLs reales coinciden con D11.
  - Primer arranque de Keycloak contra `production`: unos 3 minutos (migraciones, realm `master` y `realm-krtr.json`). `issuer` correcto; `/admin`, `/realms/master`, `/health*` y `/metrics` dan 404.
  - **150.000 usuarios importados** con `import --remote` en ~30 min (1,5 de subida y 26 de importación, 8 peticiones en paralelo), con `auth` detenido (desplegado con `KRTR_WARM=false`). El Volume quedó vacío.
  - Realm `master`: protección contra fuerza bruta (5 fallos → 15 min) activada con `kcadm.sh` vía `modal container exec`.
  - **Cuenta con MFA:** `CLI-MFA000000001`, con la acción obligatoria "Configure OTP". El TOTP se enrola en su primer login. Su contraseña está en `data/credentials/mfa_credentials.csv` (fuera de git, `600`).
  - Medido: página 0,4 s con el contenedor encendido (6 s en frío), login 1,8 s, chat 0,5 s con saldos reales enmascarados en ES y PT.
  - ⬜ Falta: guardar las credenciales QA en GitHub Secrets (para 6.7). El `GRANT SELECT ON event_entity TO krtr_audit_reader` en `production` quedó dado el 5-oct (6.5).

#### 6.7 🤖 Despliegue continuo ✅
- **Objetivo:** `.github/workflows/deploy.yml`:
  - Al hacer push a `master`, espera que pasen `lint-and-test` y `security`.
  - Luego: `npm ci` + build del front → `uv sync --locked --extra modal` → `uv run modal deploy krtr/back/deploy/app.py`, con `MODAL_TOKEN_ID` y `MODAL_TOKEN_SECRET` y `KRTR_WARM` desde una variable del repositorio.
  - Smoke test: `/healthz` de la app y `/.well-known/openid-configuration` de Keycloak.
- **Aceptación:** un merge de prueba despliega sin intervención manual.
- **Commit:** `ci(deploy): deploy to Modal on master`
- **Resultado (5-oct):** `.github/workflows/deploy.yml` corre con `workflow_run` cuando el workflow `CI` termina **en verde** sobre un push a `master` (nunca en un PR), y también a mano (`workflow_dispatch`). Despliega exactamente el commit que probó el CI, con `modal deploy -m krtr.back.deploy.app`, y uno a la vez (`concurrency`). El smoke test espera hasta 10 min a `/healthz` y al `.well-known` de Keycloak (que se reinicia en cada despliegue), y comprueba que `/admin/` siga en 404. `KRTR_WARM` sale de la variable del repositorio, con `true` por defecto mientras dure la evaluación.
  - 👤 Requisitos en GitHub: los secretos `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` (0.1 dice que ya existen) y, al terminar la evaluación, la variable `KRTR_WARM=false`.
  - ⬜ Sin verificar todavía: la primera corrida real. Si el job `security` del CI no está en verde (7.1), el despliegue nunca arranca.
- **Depende de:** 6.6, 7.1

#### 6.8 👤 Modo demo y control de costos (D17)
- **Objetivo:**
  - Al salir al aire, poner `KRTR_WARM=true` en las variables del repositorio y volver a desplegar.
  - Cada día, revisar el uso en el panel de Modal y anotarlo. También el de Neon: `production` no se apaga (scale-to-zero desactivado en 1.3) y puede escalar hasta 8 CU.
  - Cuando termine la evaluación, volver a `KRTR_WARM=false`.
  - Configurar un límite de gasto en el workspace, si Modal lo ofrece.
- **Aceptación:** existe un registro diario del gasto en `docs/modal-platform.md` y el gasto proyectado queda dentro de los créditos.
- **Depende de:** 6.7
- **Estado (5-oct):** 🟡 `3e1c086`.
  - El registro empezó en [`docs/modal-platform.md`](modal-platform.md#registro-de-gasto-diario). Primera entrada: 0,35 USD medidos en octubre, cubiertos por créditos (0,00 USD cobrados). Proyección con el modo demo: ≈ 3,15 USD/día, ≈ 9 días.
  - **Desde el CLI** se lee el gasto: `modal billing summary` (mes) y `modal billing report` (por día u hora y por recurso).
  - **Solo en el dashboard** (Settings → Usage and Billing): el saldo de créditos que queda y, si existe, el límite de gasto. `modal workspace settings` no tiene ninguno de los dos.
  - **Neon:** sin CLI ni API key; se lee en la consola (Billing y Monitoring).
  - ⬜ 👤 Completar en la primera entrada los créditos restantes y el consumo de Neon, y anotar una fila por día. La variable `KRTR_WARM` del repositorio no hace falta mientras dure la evaluación: el workflow usa `true` si no existe.

### Fase 7 — Seguridad y pruebas

- **7.1** ✅ (`43b3d82`). Pendiente: verlo en verde en GitHub y decidir sobre el hallazgo medio de Semgrep en `krtr/compute/modal/secrets.py:87`. Agregar `krtr/back/deploy/` al alcance de bandit (ya lo cubre `-r krtr/back`).

#### 7.2 🤖 Pruebas de seguridad contra producción 🟡
- **Objetivo:** `e2e/security/` con pytest y `--base-url` / `--auth-url` apuntando a Modal. Casos:
  - Cabeceras y flags de las cookies (todas `__Host-`; sesión `Strict`; la del OIDC `Lax`).
  - `/api/*` sin sesión → 401.
  - Sin CSRF → 403. Origin de otro `*.modal.run` → 403.
  - IDOR: un caso de otro cliente → 404.
  - Segundo login cierra el primero.
  - Límite de 20 mensajes → 429. Límite por IP → 429.
  - Voz con tipo de archivo falso → 415.
  - `/docs` → 404.
  - **`/admin` y `/realms/master` en `krtr-auth` → 404.**
  - Bloqueo tras 5 intentos con una cuenta QA. Se comprueba el desbloqueo con `kcadm.sh` vía `modal container exec`, o esperando 15 min.
  - Cierre por inactividad a los 5 min (test lento, marcado).
  - `properties` cifrado en la base.
- **TLS:** **no** se exige; se anota lo hallado en 0.4(b) como evidencia o como excepción (7.6).
- **Aceptación:** todo en verde. Se ejecuta después de cada despliegue y a mano antes de la demo.
- **Commit:** `test(e2e/security): add production security suite` ✅ `e48606a`
- **Resultado (5-oct):** `uv run pytest e2e/security`: **20 de 20** en producción. Cubre cabeceras, sin `/docs`, 401 sin sesión, `Origin` ajeno → 403, rutas ocultas de Keycloak → 404, cookies `__Host-` (sesión segura, la del OIDC `Lax`), login real con cuentas QA, contraseña incorrecta, sesión única, CSRF, IDOR, límite de 20 mensajes → 429 y voz falsa → 415. Quedan para después: el bloqueo de Keycloak tras 5 intentos, la inactividad de 5 min y el cifrado de `properties`.
- **Resultado (5-oct, segunda parte):** **26 de 26** más 1 lento, todos en verde en producción.
  - **Bloqueo:** 5 contraseñas malas y la buena ya no entra. Usa **solo la fila 50 de `qa_credentials.csv`** (`LOCKOUT_ACCOUNT_ROW` en `e2e/security/conftest.py`), que queda **bloqueada 15 min** después de cada corrida (la última, el 5-oct a las 22:44 COT). Primero entra bien, así prueba que la cuenta funciona y deja el contador en 0; si sigue bloqueada de una corrida anterior, el test falla y dice que hay que esperar.
  - **Contraseña incorrecta:** ahora termina con un login correcto. Keycloak recuerda los fallos 12 h (`maxDeltaTimeSeconds`), así que antes cinco corridas de la suite en un día habrían bloqueado la fila 2.
  - **Inactividad:** `@pytest.mark.slow`, corre solo con `--run-slow` (5 min 30 s). A los 4:30 sin actividad `/api/me` sigue en 200; a los 5:30 da 401 `session_expired_idle`. Usa la fila 9.
  - **Cifrado en la base** (`e2e/security/test_encryption_at_rest.py`): lee las últimas 50 filas de `events.properties` y de `messages.content` con `NEON_DB_HOST` (solo lectura, SQL en `select_latest_*.sql`) y comprueba que cada valor tiene al menos nonce + tag (28 bytes), que ningún nonce se repite, que nada se lee como UTF-8/JSON, que todos abren con la llave de la app (`KRTR_EVENTS_KEY`, `KRTR_MESSAGES_KEY`) y ninguno con otra, y que `properties` descifrado es un objeto JSON. Los fallos solo muestran conteos, nunca los bytes ni el texto.
- **Depende de:** 6.6

#### 7.3 🤖 Pruebas E2E de navegador
- Igual que la v1 (pytest-playwright, Chromium y WebKit, micrófono falso, modal de inactividad), contra las URLs de Modal.
- **Commit:** `test(e2e/browser): add end-to-end user journeys`
- **Depende de:** 6.6

#### 7.4 🤖 ZAP
- **Objetivo:** workflow con el ZAP baseline scan contra las 2 URLs de Modal, después de cada despliegue y a mano. Las reglas aceptadas van en `.zap/rules.tsv`.
- **Aceptación:** 0 alertas altas; cada alerta media está justificada.
- **Commit:** `ci(security): add OWASP ZAP baseline scan`
- **Depende de:** 6.7
- **Resultado (5-oct):** `.github/workflows/zap.yml` corre a mano (`workflow_dispatch`) y cuando el workflow `Deploy` termina en verde (`workflow_run`; como todo `workflow_run`, solo se activa cuando el archivo esté en `master`). Un job por URL: la app desde `/` y Keycloak desde su página de login real (la URL a la que redirige `/auth/login`, porque la raíz de `krtr-auth` lleva a `/admin`, que da 404). Ambos usan `.zap/baseline.sh`, que corre ZAP 2.17.0 (imagen fijada por digest) y aplica la aceptación: **ninguna alerta alta y ninguna media fuera de `.zap/rules.tsv`**. El mismo script corre en local con Docker (Colima) y deja los reportes en `.zap/reports/` (fuera de git); en GitHub se suben como artefactos.
  - **Corrida local (5-oct, 23:15) — app:** 0 altas, 0 medias. Avisos bajos o informativos: directivas de caché (10015, 10049) en el HTML y los assets, un comentario sospechoso en el JS compilado (10027), COEP ausente (90004) y "Modern Web Application" (10109).
  - **Keycloak:** 0 altas. Dos reglas medias, aceptadas en `rules.tsv`:
    - **10202** (sin token anti-CSRF): falso positivo. El formulario está atado a la cookie `AUTH_SESSION_ID` y al `session_code`/`execution`/`tab_id` de un solo uso de su URL.
    - **10055** (CSP): Keycloak pone una CSP mínima (`frame-src 'self'; frame-ancestors 'self'; object-src 'none'`) y el tema usa un `onsubmit` en línea. Se aceptó como **pendiente**: arreglarla requiere quitar el `onsubmit` del tema, fijar la CSP del realm con `kcadm.sh` y desplegar ([checklist](security-checklist.md) §5).
  - Bajas en Keycloak: las respuestas 404 del gateway (`/`, `/admin/`) no llevan HSTS; las cookies de Keycloak usan `SameSite=None` y `KC_AUTH_SESSION_HASH` no es `HttpOnly` (así las define Keycloak).

#### 7.5 🤖 Pruebas de carga
- Igual que la v1: Locust con cuentas QA. Base de 20 usuarios por 10 min, pico de 50 y prueba sostenida de 30 min con 20. El objetivo es D7.
- Se corren **con el modo demo encendido**. Ojo: Modal limita las cuentas nuevas a unas 200 peticiones por segundo; la prueba no debe pasar de eso.
- **Commit:** `test(e2e/load): add Locust load scenarios`
- **Depende de:** 6.8
- **Resultado (5-oct):** `e2e/load/locustfile.py`, un usuario de Locust por cuenta QA, con el login real de Keycloak. Perfiles con `--load-profile`: `smoke` (20 usuarios, 3 min), `baseline` (20 × 10 min) y `spike` (20 → 50 → 20 en 5 min). La prueba sostenida de 30 min no se corrió (no se pidió en esta tarea).
  - **Límite por IP:** Locust sale de una sola IP, así que todas las peticiones a la app, incluidas las del login, pasan por un regulador común de **8 por segundo** (480/min, el 80% de los 600). Más usuarios significa más sesiones simultáneas, no más tráfico. Un 429 cuenta como fallo de la prueba.
  - **Qué mide D7:** el grupo `api` (todo `/api/*` y `/app`). El login (Keycloak) y el chat (motor de IA, ~1 mensaje por minuto por usuario) se reportan aparte. Al terminar, se registra el veredicto y el código de salida es 1 si el p95 pasa de 300 ms, o si hubo algún 5xx o 429.
  - **Números** (desde Colombia; unos 130 ms de cada petición son la ida y vuelta a us-east):

    | Perfil | Peticiones `api` | p50 | **p95 `api`** | 5xx | 429 | Chat p95 | Login p95 |
    |---|---:|---:|---:|---:|---:|---:|---:|
    | smoke | 1.281 | 170 ms | **250 ms** | 0 | 0 | 360 ms | 1,1 s |
    | baseline | 4.365 | 170 ms | **250 ms** | 0 | 0 | 300 ms | 1,5 s |
    | spike (pico de 50) | 2.060 | 170 ms | **240 ms** | 0 | 0 | 300 ms | 1,2 s |

  - ✅ **D7 se cumple** en los tres. El endpoint más lento es `/api/session/activity` (p95 330–430 ms), porque a veces renueva el token con Keycloak.
  - **Ojo:** en la base hubo 405 respuestas 401 (9%). Mientras corría, otra persona o proceso inició sesión con las filas 1–9 de `qa_credentials.csv` (el patrón de `e2e/security`), y cada login cerró la sesión de un usuario de Locust (G15). Se comprobó con los eventos `session_created` y `session_revoked_by_new_login` en `events`. No es un fallo de la app, pero **no hay que correr `e2e/security` al mismo tiempo que Locust**. El pico, sin interferencias, tuvo 0 fallos.

#### 7.6 👤 Revisión contra ASVS nivel 2
- **Objetivo:** `docs/security-checklist.md` con los controles aplicables de ASVS 5.0 L2. Cada control con estado y evidencia.
- **Excepciones documentadas** por la plataforma: sin WAF, política TLS que no controlamos (0.4b), sin dominio propio, la administración de Keycloak solo por `modal container exec`, y lo que haya encontrado 0.4(f) (cabeceras que agrega Modal y usuario del contenedor).
- **Aceptación:** no queda ningún control aplicable sin evidencia ni sin excepción justificada.
- **Depende de:** 7.2–7.5
- **Borrador (5-oct):** [`docs/security-checklist.md`](security-checklist.md), con los 253 controles L1 + L2 de ASVS 5.0.0, cada uno una sola vez: 152 ✅, 27 🟡, 16 ⚠️ (8 excepciones: E1–E6 de la plataforma, E7–E8 de diseño), 1 ❌ (V15.1.1, plazos para dependencias vulnerables) y 57 que no aplican. Incluye el inventario criptográfico, la clasificación de datos, el inventario de registros y 11 pendientes priorizados. ⬜ Falta la revisión y la firma de una persona del equipo.

### Fase 8 — Entrega

#### 8.1 🤖 Documentación ✅ `b4afaae`
- **Objetivo:**
  - Actualizar el `README.md` (cómo levantar en local, comandos nuevos, `modal serve` / `modal deploy`, modo demo).
  - `docs/runbook.md`: desplegar, rotar secretos, volver a importar usuarios, desbloquear una cuenta con `kcadm.sh`, ejecutar los crons a mano, y encender o apagar el modo demo.
  - `docs/api.md` con el contrato de la §3.4.
- **Commit:** `docs(repo): add web runbook and API contract`
- **Depende de:** 7.x
- **Resultado (5-oct):** se adelantó a 7.3–7.6 porque la entrega es hoy.
  - [`docs/runbook.md`](runbook.md): desplegar (CI, workflow `Deploy`, comando de emergencia, `modal app rollback`), modo demo, rotar cada secreto con sus efectos, reimportar usuarios, desbloquear cuentas y correr la purga a mano.
  - El desbloqueo con `kcadm.sh` vía `modal container exec` se verificó en producción hasta la lectura del estado; el `DELETE` y la rotación de los secretos de Keycloak no se probaron.
  - Ojo: `modal container exec` no reenvía stdin, y hay que poner `--` antes del comando.
  - [`docs/api.md`](api.md): la §3.4 tal como está en el código. Diferencias con la §3.4: `POST /api/cases` responde 201; el `request_id` va en la cabecera `X-Request-Id` y no en el cuerpo; los 422 de validación y el 413 de `/api/events` usan el cuerpo de FastAPI (`{"detail": …}`), no `{error, message_key}`.

#### 8.2 👤 Congelar y entregar
- **Objetivo:**
  - Correr 7.2 y 7.3 en verde y revocar las sesiones QA.
  - Confirmar que el **modo demo** está encendido.
  - Publicar las cuentas del jurado en `JURY_ACCESS.md` (raíz del repo), con la URL `https://<ws>--krtr.modal.run` y las instrucciones.
  - Etiquetar la versión.
  - **No hacer merges a `master` durante la evaluación**: cada deploy reinicia Keycloak.
- **Aceptación:** checklist firmado por el revisor humano.
- **Depende de:** 8.1
- **Checklist (preparada el 5-oct).** Se marca en orden. Los procedimientos están en [`docs/runbook.md`](runbook.md).

  **A. Código en `master` y desplegado**
  - [ ] El PR de los docs de entrega (`delivery-docs`) está mergeado en `web-finish-guide`, para que todo entre con **un solo** despliegue.
  - [ ] PR `web-finish-guide` → `master`: los jobs `lint-and-test` y `security` del CI están en verde.
  - [ ] GitHub tiene los secretos `MODAL_TOKEN_ID` y `MODAL_TOKEN_SECRET`. La variable `KRTR_WARM` no existe o vale `true`.
  - [ ] Después del merge: el CI de `master` y el workflow `Deploy` están en verde, con el smoke test incluido.
  - [ ] `uv run --env-file .env modal app history krtr-web` muestra arriba el commit del merge **sin** asterisco (es decir, no se desplegó desde un árbol con cambios sin commit).
  - [ ] El workflow `Release` creó la etiqueta de la versión (ver "Etiquetar" abajo).

  **B. Producción verificada**
  - [ ] El modo demo está encendido: `uv run --env-file .env modal container list` muestra 2 contenedores de `krtr-web`.
  - [ ] `uv run pytest e2e/security` da 20 de 20 contra producción, después del último despliegue.
  - [ ] Recorrido a mano con una cuenta del jurado, en ES y en PT: la página de login con el tema krtr → soporte → caso → chat → voz → cerrar sesión. La cuenta con MFA pide TOTP.
  - [ ] 7.3 (pruebas de navegador): no existe todavía. El revisor decide si el recorrido a mano la reemplaza para esta entrega.
  - [ ] Sesiones QA cerradas: no hay un comando para revocarlas, pero las sesiones de la app y las de Keycloak vencen a los 30 min como máximo. Basta con no usar las cuentas QA en los 30 min antes de avisar al jurado.

  **C. Costos**
  - [ ] Hay una fila del día en el [registro de gasto](modal-platform.md#registro-de-gasto-diario), con los créditos restantes leídos en el dashboard. La proyección (≈ 3,15 USD/día) alcanza hasta el final de la evaluación.

  **D. Entrega al jurado**
  - [ ] Se publica `JURY_ACCESS.md` en la raíz del repo (URL, instrucciones y cuentas). Son cuentas de prueba: el riesgo está aceptado en la excepción E9 de `docs/security-checklist.md`. Las cuentas QA y la de MFA siguen fuera del repo.
  - [ ] Se confirma que lo recibieron y que una cuenta entra.

  **E. Congelar**
  - [ ] Se avisa a **todo el equipo**, incluido el vertical de IA (que también hace merges a `master`), que no hay merges a `master` hasta que termine la evaluación. Cada merge despliega y reinicia Keycloak. Un PR abierto no despliega; solo el merge.
  - [ ] Si hay que corregir algo durante la evaluación: un merge y nada más, en un momento acordado con el jurado. El despliegue a mano solo se hace en emergencias (runbook §1.4).

  **F. Al terminar la evaluación**
  - [ ] `KRTR_WARM=false` en las variables del repositorio y correr `Deploy` (runbook §2).
  - [ ] Última fila del registro de gasto.

  **Etiquetar la versión.** No hace falta crear la etiqueta a mano. Al hacer merge a `master`, el workflow `Release` (semantic-release) crea `vX.Y.Z` y su release en GitHub: con los commits `feat` de `web-finish-guide`, pasará de `v1.8.0` a **`v1.9.0`**. Esa es la versión entregada. Si además se quiere un nombre fijo para la entrega, se agrega una etiqueta anotada sobre **el mismo commit que desplegó `Deploy`** (no sobre el `chore(release)`). Subir una etiqueta no dispara ni el CI ni el despliegue.

  ```bash
  git fetch origin --tags
  git tag -a hackathon-entrega <sha-del-merge> -m "Entrega de la hackathon: krtr-web en Modal"
  git push origin hackathon-entrega
  ```

  **Firma del revisor:** ______________________ · Fecha: __________

---

## 6. Fuera de alcance

- Lógica de IA, enrutamiento por dificultad, escalamiento a humanos, reglas duras y ambigüedad (G11–G13, G19, G20).
- La tabla de casos, sus estados y los resúmenes (G17). La web usa `CaseRepository` y `ChatResponder` para conectarlos después.
  - 🆕 v2.5: la tabla `messages` sí tiene contrato en esta guía (§3.6), pero la implementa el vertical de IA.
- El procesamiento del audio (voz a texto).
- Dominio propio y WAF: requieren pagar (plan Team de Modal u otro proveedor).

## 7. Riesgos

| Riesgo | Mitigación |
|---|---|
| **Se acaban los créditos de Modal** y la página se cae durante la evaluación | Modo demo solo en la ventana necesaria (D17); revisión diaria del gasto (6.8); sin región fija si hace falta ahorrar (D16). |
| Cada `modal deploy` reinicia Keycloak (unos 20–40 s sin login) | No hacer merges durante la evaluación (8.2); los smoke tests esperan el arranque. |
| Arranque en frío fuera del modo demo | Encender el modo demo antes de avisar a los jurados. |
| `add_python` no funciona sobre la imagen oficial de Keycloak | Plan B de 3.1 (base `ubi9` en varias etapas). |
| Importar 150.000 usuarios toma mucho tiempo | Medirlo en local (3.6); `timeout` amplio en 6.4; es idempotente, así que se puede reintentar. |
| Sin WAF ni restricción por IP de la plataforma | Gateway que oculta `/admin` (3.7), límites por usuario y por IP en la app (4.6), bloqueo de Keycloak, CSRF + Origin. |
| Dominio compartido `modal.run` | Prefijo `__Host-` en todas las cookies; CSRF que no depende de SameSite (4.5). |
| No podemos fijar TLS ≥ 1.2 | Verificarlo en 0.4(b) y documentarlo como excepción (7.6). |

## 8. Costos estimados en Modal

Precios publicados por Modal: CPU 0,0000131 USD/núcleo/s; memoria 0,00000222 USD/GiB/s. La región fija `us-east` cuesta ×1,75. Recursos de D8: `web` 0,25 CPU / 0,5 GiB y `auth` 1 CPU / 1,5 GiB. **Desde el 6-oct, `web` usa 2 CPU / 4 GiB** para correr MiniLM y el LLM Qwen.

| Escenario (ambos contenedores encendidos 24 h) | USD/día | Días que alcanzan 30 USD |
|---|---:|---:|
| Sin región fija | ≈ 1,80 | ≈ 16 |
| Región `us-east` (D16) | ≈ 3,15 | ≈ 9 |
| Región `us-east` con `web` a 2 CPU / 4 GiB (6-oct, MiniLM + Qwen) | ≈ 7,8 | ≈ 3,8 |

- Los crons, las compilaciones y el modo apagado (`KRTR_WARM=false`) cuestan centavos al día.
- **Del 3 al 5 de octubre con región fija: ≈ 9,5 USD.** Cada día extra de evaluación sumaba unos 3,15 USD; **con el LLM en `web`, unos 7,8 USD**. Revisar el saldo cada día (6.8) y, si no alcanza, volver a `KRTR_IA_LLM_MODEL=none` y a 0,25 CPU / 0,5 GiB, o apagar el modo demo.
