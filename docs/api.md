# API de krtr-web

_Tarea 8.1 de [`guia-web-seguridad_modal.md`](guia-web-seguridad_modal.md) · Contrato de la §3.4, actualizado con lo que hace el código el 5-oct-2026_

Es el contrato entre la SPA (`krtr/front/`) y el backend FastAPI (`krtr/back/web/`). Los dos se sirven desde el mismo origen: `https://juan-alvarezo-2002--krtr.modal.run` en producción y `http://localhost:8000` en local. No hay documentación interactiva en producción: `/docs` y `/openapi.json` responden 404.

## Endpoints

| Método y ruta | Protección | Entrada | Respuesta correcta | Errores propios |
|---|---|---|---|---|
| `GET /auth/login?lang=` | — | `lang`: `es` (por defecto) o `pt-BR` | 302 a Keycloak con `ui_locales`; crea `__Host-krtr_oidc` | 422 si `lang` no es válido |
| `GET /auth/callback` | — | `code`, `state` (o `error`) que manda Keycloak | 302 a `/app`; crea `__Host-krtr_session` y `__Host-krtr_csrf` y borra `__Host-krtr_oidc` | 400 `login_failed` |
| `POST /auth/logout` | Sesión + CSRF | — | 204; cierra la sesión en Keycloak y borra las cookies | — |
| `GET /api/me` | Sesión | — | `{customer_id, idle_expires_at, absolute_expires_at}` | — |
| `POST /api/session/activity` | Sesión + CSRF | — | Igual que `/api/me`, con el plazo de inactividad renovado | — |
| `GET /api/cases?status=open` | Sesión | `status` obligatorio; solo se acepta `open` | 200 `[{incident_id, opened_at, summary}]`, los más nuevos primero | 422 con otro `status` |
| `POST /api/cases` | Sesión + CSRF | — | **201** `{incident_id}` | — |
| `POST /api/cases/resume` | Sesión + CSRF | `{incident_id}` (1–30 caracteres) | 200 `{incident_id}` | 404 `case_not_found` |
| `POST /api/chat/messages` | Sesión + CSRF + límite del chat | `{incident_id, text, language}`: `text` de 1 a 2.000 caracteres (sin contar los espacios de los extremos), `language` `es` o `pt-BR` | 200 `{incident_id, reply, responded_at}` | 404 `case_not_found` |
| `POST /api/chat/voice` | Sesión + CSRF + límite del chat | `multipart/form-data`: `audio`, `incident_id`, `language` | Igual que `/api/chat/messages` | 404 `case_not_found` · 413 `audio_too_large` · 415 `unsupported_audio` |
| `POST /api/events` | `Origin` propio (no exige sesión) | `{event_name, properties}`: `event_name` del catálogo (§3.5 de la guía), `properties` de 4 KB como máximo en JSON | 202 sin cuerpo | 413 y 422 con el cuerpo de FastAPI (ver abajo) |
| `GET /healthz` | — | — | 200 `{"status": "ok"}` | — |

Los archivos del frontend compilado se sirven en `/assets/`. Cualquier otra ruta que no empiece por `/api/`, `/auth/`, `/healthz`, `/docs`, `/redoc` ni `/openapi.json` devuelve la SPA (`index.html`).

- Las fechas van en ISO 8601 con zona horaria (UTC).
- Un caso que no existe y uno de otro cliente dan **el mismo** 404, para no revelar cuáles existen.
- `GET /api/me` **no** cuenta como actividad. Solo `POST /api/session/activity` renueva el plazo de 5 minutos.
- **Voz:** solo se aceptan `audio/webm` (Opus) y `audio/mp4` (AAC), por el tipo declarado **y** por los bytes mágicos. Un archivo vacío también da 415. El servidor no guarda el audio, no lo transcribe (responde el texto de D15) y no mide la duración: el límite de 60 s lo aplica el frontend al grabar.

## Errores

Los errores de la app tienen siempre esta forma:

```json
{"error": "<código>", "message_key": "<clave i18n>"}
```

`error` es un código estable para el programa. `message_key` es la clave que el frontend traduce con sus archivos de idioma (`krtr/front/src/i18n/locales/`). Los dos salen de `ApiErrorCode` y `MessageKey` en `krtr/back/web/errors.py`.

| HTTP | `error` | `message_key` | Cuándo |
|---|---|---|---|
| 400 | `login_failed` | `login_failed` | Se rechaza el callback de OIDC: falta la cookie de login, vale otra o pasaron más de 10 min; `state` o `nonce` no coinciden; Keycloak devolvió `error`; o falla el canje del código o la validación del ID token. El motivo queda en el evento `auth_login_failed` (`LoginFailureReason`). |
| 401 | `unauthorized` | `unauthorized` | No hay sesión, o fue revocada (por ejemplo, por un login nuevo en otro navegador) o falsificada. |
| 401 | `session_expired_idle` | `session_expired_idle_message` | Pasaron 5 minutos sin actividad. |
| 401 | `session_expired_absolute` | `session_expired_absolute_message` | Pasaron 30 minutos desde el login. |
| 403 | `csrf_rejected` | `csrf_rejected` | Falla la protección CSRF (ver abajo). |
| 404 | `case_not_found` | `support_case_not_found` | El caso no existe o es de otro cliente. |
| 413 | `audio_too_large` | `chat_error_voice_too_large` | La nota de voz pasa de 2 MB. |
| 413 | `request_too_large` | `request_too_large` | El `Content-Length` declarado pasa de 2 MB + 64 KB (2.162.688 bytes) o no es un número. Se rechaza antes de leer el cuerpo, en cualquier ruta. |
| 415 | `unsupported_audio` | `chat_error_voice_unsupported` | El audio no es WebM ni MP4, sus bytes no corresponden al tipo declarado, o está vacío. |
| 429 | `rate_limited` | `rate_limited` | Se superó el límite por IP o por sesión. |
| 429 | `rate_limited` | `chat_error_rate_limited` | Se superó el límite del chat. |
| 503 | `auth_unavailable` | `auth_unavailable` | El login no está configurado. Solo pasa en desarrollo: en producción la app no arranca sin esa configuración. |

Un 401 también borra las cookies de sesión y de CSRF. La SPA vuelve entonces a la landing.

**Errores de validación de FastAPI.** Un cuerpo o un parámetro inválido (texto vacío o de más de 2.000 caracteres, idioma desconocido, `event_name` fuera del catálogo, `status` distinto de `open`) da **422** con el cuerpo estándar de FastAPI, `{"detail": [...]}`, y no con la forma de arriba. Lo mismo pasa con el 413 de `POST /api/events` cuando `properties` pasa de 4 KB: responde `{"detail": "properties exceeds 4096 bytes"}`.

## CSRF

Aplica a todos los `POST` que exigen sesión (`/auth/logout`, `/api/session/activity`, `/api/cases`, `/api/cases/resume` y `/api/chat/*`). Como `modal.run` es un dominio compartido entre muchas apps, `SameSite` no basta, así que se exigen dos controles:

1. **Origen:** la cabecera `Origin` (o, si falta, `Referer`) tiene que ser exactamente el origen de la app (`KRTR_PUBLIC_URL`). Otra app de `*.modal.run` se rechaza.
2. **Double submit:** la cabecera `X-KRTR-CSRF` tiene que traer el mismo valor que la cookie `__Host-krtr_csrf`. La cookie se crea en el callback del login, no es `HttpOnly` (la SPA la lee para copiarla en la cabecera) y se borra con la sesión.

Las comprobaciones van en orden: primero la sesión (sin sesión, 401 y no 403), después el CSRF (403 `csrf_rejected`) y por último el límite del chat. `POST /api/events` solo exige el origen, porque la landing manda eventos antes de que haya sesión. Cada rechazo registra `csrf_rejected` en `events`.

## Límites de peticiones

Son ventanas deslizantes de 1 minuto, guardadas en memoria (hay un solo contenedor, D8):

| Ámbito | Límite | Aplica a | `message_key` del 429 |
|---|---|---|---|
| Por IP | 600 por minuto | Todo el sitio | `rate_limited` |
| Por sesión | 240 por minuto | `/api/*` | `rate_limited` |
| Por cliente | 20 mensajes por minuto | `/api/chat/*` (texto y voz juntos) | `chat_error_rate_limited` |

- El 429 lleva la cabecera **`Retry-After`** con los segundos que faltan para que se libere un cupo (como mínimo 1).
- La IP es la dirección desde la que conecta Modal (`request.client.host`). `X-Forwarded-For`, `X-Real-IP` y `Forwarded` nunca se leen, así que el cliente no puede falsificarla.
- El límite del chat se cuenta solo después de pasar la sesión y el CSRF.
- Cada 429 registra `rate_limit_exceeded`.
- Los contadores se pierden al reiniciar el contenedor, por ejemplo en cada despliegue.

## Cookies

Todas llevan el prefijo `__Host-`, así que van con `Secure`, `Path=/` y sin `Domain`. Ninguna otra app de `*.modal.run` puede sobrescribirlas.

| Cookie | `HttpOnly` | `SameSite` | Vida | Contenido |
|---|---|---|---|---|
| `__Host-krtr_oidc` | Sí | `Lax` | 10 min | `state`, `nonce` y verificador PKCE, cifrados con `KRTR_TOKENS_KEY`. |
| `__Host-krtr_session` | Sí | `Strict` | La sesión | Token aleatorio de 256 bits. En la base solo queda su hash. |
| `__Host-krtr_csrf` | No | `Strict` | La sesión | Token del double submit. |

El navegador nunca recibe los tokens de Keycloak: quedan cifrados en `app_sessions`.

## Cabeceras de respuesta

- **`X-Request-Id`** en todas las respuestas: un UUID que también aparece en el log del servidor y en el evento `http_request`. (La §3.4 pedía un `request_id`; va en esta cabecera, no en el cuerpo).
- Las cabeceras de seguridad de la tarea 4.2, verificadas en producción: `Content-Security-Policy` (todo `'self'`; los formularios solo pueden ir a Keycloak; `frame-ancestors 'none'`), `Strict-Transport-Security` (1 año, con subdominios), `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy: same-origin` y `Permissions-Policy: microphone=(self), camera=(), geolocation=()`. No se envía `Server`.
