# Pendientes de las fases 5 y 6

_Corte: 1-oct-2026 · Rama `web-develop` (último commit `ee70fdb`) · Referencia: [`guia-web-seguridad.md`](guia-web-seguridad.md)_

Este documento lista lo que falta para cerrar las fases 5 (frontend) y 6 (contenedores y despliegue) de la guía. Usa la misma notación de la guía: **🤖** Claude Code · **👤** una persona del equipo · **👤🤖** Claude Code prepara los comandos y la persona los ejecuta.

---

## Resumen

| Fase | Estado | Qué falta |
|---|---|---|
| 5 — Frontend | Las 10 tareas tienen commit, pero **hoy no pasan sus pruebas** | Quitar los mocks de demo (P5.1), limpiar el lint (P5.2) y probar contra el backend real (P5.3) |
| 6 — Despliegue | 2 de 10 tareas preparadas (6.1 y 6.2), **sin verificar en GCP ni con Docker** | Verificar 6.1 y 6.2; 6.5 no tiene bloqueos; el resto depende de las fases 3, 4 y 7 |

**Lo más urgente:**
1. Quitar los mocks de demo del frontend (P5.1). Mientras sigan, cualquier imagen que se construya los incluye.
2. Comprar el dominio (6.5). El calendario de la guía pone hoy, 1-oct, como fecha límite.
3. Terminar las fases 3 y 4. Sin ellas no se puede desplegar nada de la fase 6 más allá de 6.1 y 6.2.

---

## Fase 5 — Frontend

Las tareas 5.1 a 5.10 están hechas (commits `5ed04d1` a `9ebe3b5`), además del diseño visual (`6543970`). Pero ese último commit dejó cambios temporales que rompen las pruebas.

### P5.1 🤖 Quitar los mocks de demo (bloqueante)

El commit `6543970` (diseño visual) agregó bloques `// TEMP DEMO MOCK — revert before continuing real work.` que devuelven datos inventados **antes** de llamar al backend. El código real quedó debajo como código inalcanzable.

| Archivo | Función | Qué hace el mock |
|---|---|---|
| `krtr/front/src/api/session.ts` | `fetchCurrentSession` | Siempre devuelve el cliente `48213` con una sesión válida |
| `krtr/front/src/api/session.ts` | `reportActivity` | Devuelve el mock anterior en lugar de llamar a `/api/session/activity` |
| `krtr/front/src/api/cases.ts` | `listOpenCases` | 2 casos fijos |
| `krtr/front/src/api/cases.ts` | `createCase` | ID aleatorio `CASE-2026-XXXX` |
| `krtr/front/src/api/cases.ts` | `resumeCase` | Acepta cualquier ID que no contenga "wrong" |
| `krtr/front/src/api/chat.ts` | `sendChatMessage` | Respuesta fija tras 900 ms |
| `krtr/front/src/api/voice.ts` | envío de voz | Respuesta fija |

**Por qué importa:**
- `npm test` falla: **14 de 91 pruebas** en 4 archivos (`api/cases`, `api/session`, `components/app-shell`, `pages/chat-page`).
- No se cumple la aceptación de 5.5 ("sin sesión, la página redirige a la landing"): con el mock, `/app` siempre se muestra.
- El backend sigue protegiendo los datos, pero si este código se despliega, la interfaz muestra un usuario y casos falsos a cualquiera que entre a `/app`.
- Rompe el `CLAUDE.md` (no hay código muerto) y genera 7 advertencias de lint por `eslint-disable` sin efecto.

**Aceptación:** no queda ningún `TEMP DEMO MOCK` en `krtr/front/src`, `npm test` pasa en verde (91/91) y `npm run lint` no muestra esas advertencias.
**Commit sugerido:** `fix(front/api): remove temporary demo mocks`

> Si el equipo necesita seguir haciendo demos sin backend, la alternativa es un modo de mocks activado solo en `npm run dev` (por ejemplo, con MSW o con una variable de Vite que no entra al build de producción). No debe quedar en el código que se compila para producción.

### P5.2 🤖 Limpiar las advertencias de lint

`npm run lint` muestra 8 advertencias (0 errores):
- 7 por los `eslint-disable-next-line no-unreachable` de P5.1. Desaparecen al quitar los mocks.
- 1 en `krtr/front/src/components/ui/button.tsx:55` (`react-refresh/only-export-components`): el archivo exporta algo además del componente. Se resuelve moviendo `buttonVariants` a un archivo aparte o ignorando la regla solo en los componentes generados por shadcn.

### P5.3 👤🤖 Probar el frontend contra el backend real

Hoy el frontend solo se ha probado con `fetch` simulado. Varios endpoints que usa **todavía no existen** en el backend:

| Endpoint (§3.4) | Tarea del backend | Estado |
|---|---|---|
| `GET /auth/login`, `/auth/callback`, `POST /auth/logout` | 4.3 | Pendiente |
| `GET /api/me`, `POST /api/session/activity` | 4.4 | Pendiente |
| Cookie y cabecera CSRF | 4.5 | Pendiente |
| 429 por límite de mensajes | 4.6 | Pendiente |
| `/api/cases`, `/api/cases/resume` | 4.8 | Pendiente |
| `/api/chat/messages`, `/api/chat/voice` | 4.9 | Pendiente |
| `POST /api/events` | 4.7 | ✅ Hecho |

**Aceptación:** con el backend local (`krtr back web serve`) y Keycloak en Docker, el recorrido login → soporte → caso → chat → voz → cerrar sesión funciona en ES y PT. Es la misma prueba que pide 6.4, pero en local.

### P5.4 👤 Confirmar el reparto de eventos con el backend

El commit de 5.10 (`9ebe3b5`) dejó **sin emitir desde el frontend**, a propósito, los eventos que corresponden al servidor:
- Seguridad: `rate_limit_exceeded`, `csrf_rejected`, `unauthorized_request`, `client_error`, `server_error`.
- Sesión y login: `auth_*`, `session_created`, `session_revoked_by_new_login`.

Quien haga 4.3 a 4.6 tiene que confirmar que el backend registra estos eventos. Si no, la tabla `events` queda incompleta (G21).

### P5.5 🤖 Detalle menor: favicon

`favicon.svg` queda en la raíz de `krtr/front/dist/`, pero FastAPI solo publica `/assets`. Por eso `/favicon.svg` devuelve el `index.html` de la SPA. Se arregla moviendo el ícono a `src/assets/` (Vite lo publica en `/assets`) o agregando una ruta para él en el backend.

---

## Fase 6 — Contenedores y despliegue

### Estado por tarea

| Tarea | Quién | Estado | Bloqueada por |
|---|---|---|---|
| 6.1 Imagen de la app | 🤖 | ⚠️ Hecha (`67a7a2c`), falta verificarla con Docker | — |
| 6.2 Registro, cuentas de servicio y secretos | 👤🤖 | ⚠️ Script listo (`ee70fdb`), falta ejecutarlo | 1.2 (proyecto de GCP) |
| 6.3 Desplegar Keycloak | 👤🤖 | ⛔ Bloqueada | 3.1, 3.2, 3.3 |
| 6.4 Desplegar la app | 👤🤖 | ⛔ Bloqueada | 4.3–4.6, 4.8–4.10, P5.1, 6.3 |
| 6.5 Dominio y DNS | 👤 | 🔴 Sin empezar; **no tiene bloqueos** | — |
| 6.6 Load Balancer HTTPS | 👤🤖 | ⛔ Bloqueada | 6.4, 6.5 |
| 6.7 Cloud Armor | 👤🤖 | ⛔ Bloqueada | 6.6 |
| 6.8 Despliegue continuo | 🤖 | ⛔ Bloqueada | 6.4, 7.1 |
| 6.9 Jobs programados | 👤🤖 | ⛔ Bloqueada | 4.10, 6.4 |
| 6.10 Datos de producción y MFA | 👤 | ⛔ Bloqueada | 6.3 (y 3.4, 3.5 para importar) |

### 6.1 Imagen de la app — falta verificar

**Qué hay:** `Dockerfile` en tres etapas (Node 24 compila el frontend → `uv sync --frozen --no-dev` → `python:3.13-slim` con usuario sin privilegios, arranca con `krtr back web serve` en `$PORT`) y `.dockerignore` (deja fuera `.env`, `data/`, `.git` y `node_modules`).

**Qué se probó sin Docker:** cada etapa se repitió a mano con los mismos comandos. La app así instalada responde `/healthz` 200, sirve la SPA y sus assets, `/docs` da 404 y no envía la cabecera `Server`. `pip-audit` no encuentra vulnerabilidades en las dependencias de producción.

**Qué falta (👤, en una máquina con Docker):**
```bash
docker build -t krtr-web .
docker run --rm -p 8080:8080 krtr-web
curl -i localhost:8080/healthz   # 200
trivy image krtr-web             # 0 vulnerabilidades críticas
```

> Ojo: construir la imagen antes de P5.1 empaqueta los mocks de demo.

**Nota:** el commit usa `chore(repo)` en lugar del `build(repo)` de la guía, porque el `CLAUDE.md` no permite el tipo `build`.

### 6.2 Registro, cuentas de servicio y secretos — falta ejecutar

**Qué hay:** `deploy/gcp/setup-registry-accounts-secrets.sh` (idempotente, compatible con el bash 3.2 de macOS). Crea:
- El repositorio `krtr` en Artifact Registry (us-east4).
- Las cuentas `krtr-web`, `krtr-auth`, `krtr-jobs` y `krtr-deployer`, con permisos mínimos.
- 8 secretos. Cada cuenta lee solo los suyos:

| Secreto | Origen del valor | Lo leen |
|---|---|---|
| `krtr-app-database-url` | Neon (prompt oculto) | web, jobs |
| `krtr-audit-database-url` | Neon (prompt oculto) | jobs |
| `krtr-keycloak-db-password` | Neon (prompt oculto) | auth |
| `krtr-events-key` | Generado (AES-256) | web, jobs |
| `krtr-tokens-key` | Generado (AES-256) | web |
| `krtr-web-oidc-client-secret` | Generado | web, auth |
| `krtr-keycloak-admin-password` | Generado | nadie (solo el equipo) |
| `krtr-importer-client-secret` | Generado | nadie (solo el equipo) |

**Qué falta (👤):**
1. Confirmar que 1.2 (proyecto de GCP) y 1.3 (roles de Neon) están hechos.
2. Revisar el script y correrlo: `deploy/gcp/setup-registry-accounts-secrets.sh`.
3. Verificar con `deploy/gcp/setup-registry-accounts-secrets.sh --verify` que cada secreto tiene solo los lectores de la tabla.

**Decisiones abiertas:**
- El script está en `deploy/gcp/`, una carpeta que no aparece en la §3.3. Si el equipo prefiere otra ubicación, se mueve.
- `krtr-auth` puede leer el secreto del cliente `krtr-web` porque se asume que el realm (3.2) lo toma de una variable de entorno al importarse. Si 3.2 lo resuelve de otra forma, hay que quitar ese permiso.

### 6.5 Dominio y DNS — sin empezar (👤, urgente)

No tiene dependencias. Según la guía: comprarlo (se recomienda Cloudflare Registrar), activar DNSSEC y comprobar con `dig NS <dominio>`. Los certificados gestionados de Google pueden tardar hasta 24 h, y 6.6 depende de esto.

### 6.3, 6.4 y 6.6 a 6.10 — bloqueadas

No se empezaron, por la regla 2 de la guía. Orden sugerido para desbloquearlas:

1. **Fase 3** (3.1 → 3.2 → 3.3; en paralelo 3.4 → 3.5 → 3.6) → desbloquea **6.3** y luego **6.10**.
2. **Fase 4** (4.3 → 4.4 → 4.5 / 4.6 → 4.8 / 4.9; 4.10) + **P5.1** → desbloquea **6.4** y **6.9**.
3. **6.4 + 6.5** → **6.6** → **6.7**.
4. **7.1** (escáneres en CI) + **6.4** → **6.8**.

Cuando cada tarea quede desbloqueada, Claude Code prepara sus comandos en `deploy/gcp/` como en 6.2.

---

## Checklist rápido

- [ ] P5.1 Quitar los mocks de demo del frontend
- [ ] P5.2 Lint sin advertencias
- [ ] P5.3 Recorrido completo contra el backend local
- [ ] P5.4 Confirmar qué eventos registra el backend
- [ ] P5.5 Servir el favicon
- [ ] 6.1 `docker build` + `/healthz` + Trivy sin críticas
- [ ] 6.2 Ejecutar el script y verificar el IAM de los secretos
- [ ] 6.5 Comprar el dominio y activar DNSSEC
- [ ] Fase 3 completa → 6.3, 6.10
- [ ] Fase 4 completa → 6.4, 6.9
- [ ] 6.6 Load Balancer · 6.7 Cloud Armor · 6.8 Despliegue continuo
