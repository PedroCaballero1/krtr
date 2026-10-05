# Pendientes de las fases 5, 6 y 7

> **⚠️ Documento reemplazado.** Desde el 1-oct-2026, el estado vigente está en la §4.1 de [`guia-web-seguridad_modal.md`](guia-web-seguridad_modal.md). Este documento se escribió para la guía v1 (Google Cloud): sus números de tarea de la fase 6 y lo que dice sobre el dominio, el Load Balancer, Cloud Armor, el `Dockerfile` y `deploy/gcp/` ya no aplican. Se conserva como registro.

_Corte: 1-oct-2026 · Rama `web-develop-security` (último commit `dc4f241`) · Referencia: [`guia-web-seguridad.md`](guia-web-seguridad.md)_

Este documento lista lo que falta para cerrar las fases 5 (frontend), 6 (contenedores y despliegue) y 7 (seguridad y pruebas) de la guía. Usa la misma notación de la guía: **🤖** Claude Code · **👤** una persona del equipo · **👤🤖** Claude Code prepara los comandos y la persona los ejecuta.

---

## Resumen

| Fase | Estado | Qué falta |
|---|---|---|
| 5 — Frontend | Las 10 tareas tienen commit y las pruebas pasan (91/91) desde que se quitaron los mocks (P5.1) | Limpiar el lint (P5.2) y probar contra el backend real (P5.3) |
| 6 — Despliegue | 2 de 10 tareas preparadas (6.1 y 6.2), **sin verificar en GCP ni con Docker** | Verificar 6.1 y 6.2; 6.5 no tiene bloqueos; el resto depende de las fases 3, 4 y 7 |
| 7 — Seguridad y pruebas | 7.1 hecha (`43b3d82`), sin haber corrido todavía en GitHub | Ver que 7.1 pase en GitHub; 7.2 a 7.6 dependen del despliegue a producción |

**Lo más urgente:**
1. Comprar el dominio (6.5). El calendario de la guía pone hoy, 1-oct, como fecha límite.
2. Terminar las fases 3 y 4. Sin ellas no se puede desplegar nada de la fase 6 más allá de 6.1 y 6.2, y sin despliegue no se puede hacer nada de la fase 7 más allá de 7.1.

---

## Fase 5 — Frontend

Las tareas 5.1 a 5.10 están hechas (commits `5ed04d1` a `9ebe3b5`), además del diseño visual (`6543970`). Pero ese último commit dejó cambios temporales que rompen las pruebas.

### P5.1 🤖 Quitar los mocks de demo — ✅ hecho (`138ad97`)

> Ya no queda ningún `TEMP DEMO MOCK`, `npm test` pasa 91/91 y el lint solo muestra la advertencia de P5.2. Se deja la descripción como registro.

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

`npm run lint` muestra 1 advertencia (0 errores). Las otras 7 desaparecieron al quitar los mocks (P5.1):
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
| 6.4 Desplegar la app | 👤🤖 | ⛔ Bloqueada | 4.3–4.6, 4.8–4.10, 6.3 |
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
2. **Fase 4** (4.3 → 4.4 → 4.5 / 4.6 → 4.8 / 4.9; 4.10) → desbloquea **6.4** y **6.9**.
3. **6.4 + 6.5** → **6.6** → **6.7**.
4. **7.1** (escáneres en CI) + **6.4** → **6.8**.

Cuando cada tarea quede desbloqueada, Claude Code prepara sus comandos en `deploy/gcp/` como en 6.2.

---

## Fase 7 — Seguridad y pruebas

### Estado por tarea

| Tarea | Quién | Estado | Bloqueada por |
|---|---|---|---|
| 7.1 Escáneres en CI | 🤖 | ⚠️ Hecha (`43b3d82`), falta verla en verde en GitHub | — |
| 7.2 Pruebas de seguridad contra producción | 🤖 | ⛔ Bloqueada | 6.7, 6.10 (y 4.3–4.6, 4.8, 4.9 para tener qué probar) |
| 7.3 Pruebas E2E de navegador | 🤖 | ⛔ Bloqueada | 6.10 |
| 7.4 ZAP | 🤖 | ⛔ Bloqueada | 6.8 |
| 7.5 Pruebas de carga | 🤖 | ⛔ Bloqueada | 6.10 |
| 7.6 Revisión contra ASVS nivel 2 | 👤 | ⛔ Bloqueada | 7.2–7.5 |

### 7.1 Escáneres en CI — falta verificar en GitHub

**Qué hay:** un job `security` en `.github/workflows/ci.yml` que corre:
- `bandit -r krtr/back --severity-level high`.
- Semgrep 1.178.0 con `p/python`, `p/owasp-top-ten` y `p/typescript`, que falla solo con severidad `ERROR` (alta).
- `pip-audit --skip-editable` y `npm audit --audit-level=high`.
- gitleaks 8.28.0 sobre todo el historial; el binario se verifica con su SHA-256.
- Las pruebas del frontend (`npm --workspace krtr/front test`).

Además, se quitaron los filtros por ruta del CI: así se revisa cualquier cambio y 6.8 puede esperar al CI en todo push a `master`.

**Qué se probó en local:** todos los comandos pasan. Semgrep tiene 1 hallazgo de severidad media (no bloquea) en `krtr/compute/modal/secrets.py:87`. Es un falso positivo: el log muestra los nombres de las claves, no sus valores. gitleaks revisó 104 commits sin encontrar secretos.

**Qué falta:**
1. 👤 Abrir el PR o hacer push y confirmar que los jobs `lint-and-test` y `security` quedan en verde.
2. 👤 Decidir si se silencia el hallazgo medio de Semgrep con un `# nosemgrep` justificado o se deja visible.

### 7.2 a 7.5 — bloqueadas

No se empezaron, por la regla 2 de la guía. Todas corren **contra producción** (D9), así que dependen del despliegue completo (6.3 → 6.4 → 6.6 → 6.7, más 6.10 para las cuentas QA).

Hay una alternativa por decidir: Claude Code puede escribirlas ahora, basándose en el contrato de la §3.4, aunque no se puedan ejecutar todavía. El riesgo es que algunos detalles (nombres de cookies, cómo se ve el login de Keycloak, mensajes de error) cambien al implementar las fases 3 y 4, y haya que ajustarlas.

| Tarea | Qué necesita para poder ejecutarse |
|---|---|
| 7.2 | Dominio con LB y Cloud Armor (6.6, 6.7), cuentas QA (6.10), acceso de solo lectura a la base para comprobar el cifrado de `properties`, y la API de administración de Keycloak para comprobar el bloqueo |
| 7.3 | Cuentas QA en producción (6.10) y `uv run playwright install chromium webkit` |
| 7.4 | El workflow de despliegue (6.8), para dispararse después de cada despliegue |
| 7.5 | Cuentas QA (6.10); el reporte HTML va en `docs/reports/` |
| 7.6 | Los resultados de 7.2 a 7.5 como evidencia |

---

## Checklist rápido

- [x] P5.1 Quitar los mocks de demo del frontend (`138ad97`)
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
- [ ] 7.1 Jobs `lint-and-test` y `security` en verde en GitHub
- [ ] 7.2 Seguridad contra producción · 7.3 E2E de navegador · 7.4 ZAP · 7.5 Carga
- [ ] 7.6 Checklist ASVS nivel 2
