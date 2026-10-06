# Checklist de seguridad — OWASP ASVS 5.0, nivel 2

_Tarea 7.6 de la [guía](guia-web-seguridad_modal.md) · 5-oct-2026 · Rama `security-tests` · Lo revisa y firma una persona del equipo (👤)._

## Cómo leer este documento

- **Alcance:** la web de krtr en producción: la app `krtr-web` (FastAPI + SPA, `https://juan-alvarezo-2002--krtr.modal.run`), Keycloak detrás de su gateway (`https://juan-alvarezo-2002--krtr-auth.modal.run`), la base Neon y el despliegue en Modal. El motor de IA queda fuera, salvo en lo que toca a la web (la tabla `messages` y el endpoint del chat).
- **Fuente:** los 253 controles de nivel 1 y 2 de ASVS 5.0.0 ([JSON oficial](https://github.com/OWASP/ASVS/releases/tag/v5.0.0_release)). Nivel 2 incluye los de nivel 1.
- **Estados:** ✅ cumple · 🟡 cumple en parte (dice qué falta) · ⚠️ excepción justificada (ver §2) · ❌ no cumple · ➖ no aplica (§4).
- **Evidencia:** archivo, test o commit. `e2e/…` son las pruebas que corren contra producción (7.2); `tests/…`, las unitarias que corren en el CI.
- El texto de cada control está resumido en español; el original manda.

## 1. Resumen

| Estado | Controles |
|---|---:|
| ✅ Cumple | 152 |
| 🟡 Parcial | 27 |
| ⚠️ Excepción justificada | 16 |
| ❌ No cumple | 1 |
| ➖ No aplica | 57 |
| **Total L1 + L2** | **253** |

Lo más importante que queda abierto (detalle en §5):

1. **V15.1.1 ❌** — no hay plazos definidos para corregir dependencias vulnerables.
2. **V12.3.2 🟡** — las conexiones a Neon usan `sslmode=require`, que cifra pero no valida el certificado.
3. **V10.4.1 🟡** — el cliente `krtr-web` de producción acepta también `http://localhost:8000/auth/callback`.
4. **V16.3.1 🟡** — los intentos fallidos de login quedan en Keycloak (`event_entity`) pero todavía no se copian a `events` (4.10).
5. **V3.4.3 🟡** — la CSP de la página de login de Keycloak es mínima (ZAP 10055, aceptada como pendiente).

## 2. Excepciones

### Por la plataforma (Modal, sin presupuesto para un plan pago)

| # | Excepción | Por qué | Cómo se mitiga | Controles |
|---|---|---|---|---|
| E1 | **Sin WAF** ni filtrado de red en el borde. | Modal no lo ofrece en el plan Starter; un WAF externo exige dominio propio (E3). | Todo vive en la app: límites por IP, sesión y chat (4.6), bloqueo de Keycloak, CSRF + `Origin` (4.5), gateway que oculta `/admin` (3.7), validación estricta de entradas. | V2.4.1, V13.2.4, V13.2.5, V16.4.3 |
| E2 | **TLS que no controlamos** (0.4b). | Modal termina el TLS de `*.modal.run`. | Medido en [`modal-platform.md`](modal-platform.md): solo acepta TLS 1.2 y 1.3, y `http://` redirige con 308. HSTS de 1 año con `includeSubDomains`. | V4.1.2, V4.2.1, V12.1.1, V12.1.2 |
| E3 | **Sin dominio propio.** | Modal solo permite dominio propio desde el plan Team (250 USD/mes). | `modal.run` no está en la Public Suffix List, así que otras apps de `*.modal.run` son "del mismo sitio": todas las cookies llevan el prefijo `__Host-` y CSRF no depende de `SameSite` (D22, 4.5). La app y Keycloak están en hosts distintos. | V3.5.4, V12.2.2 |
| E4 | **Administración de Keycloak solo por `modal container exec`** (`kcadm.sh` contra `127.0.0.1:8081`). | El gateway responde 404 a `/admin/*` y `/realms/master/*` (D19); no hay red privada ni restricción por IP. | Solo quien tiene el token de Modal del workspace puede entrar al contenedor. | V6.3.2, V7.4.5, V10.4.9 |
| E5 | **El contenedor corre como root** (0.4f). | Las imágenes de Modal corren como uid 0 y no se puede cambiar. | Contenedores efímeros y aislados por Modal (gVisor); el proceso no ejecuta nada que venga del usuario. | V13.2.2 (nota) |
| E6 | **Cabeceras que agrega Modal:** `modal-function-call-id` (identificador interno de cada llamada) y, solo en la redirección de `http://`, `Server: Caddy` (0.4f). | Las pone el borde de Modal, no la app. | La app y el gateway quitan `Server` en todas sus respuestas por HTTPS (`e2e/security/test_production.py::test_security_headers_are_present_and_server_is_hidden`). | V13.4.2 (nota) |

### Por diseño del producto (decisiones de la guía)

| # | Excepción | Por qué | Cómo se mitiga | Controles |
|---|---|---|---|---|
| E7 | **Contraseñas generadas por el sistema, sin cambio ni recuperación** (G6, D5). | Los 150.000 clientes son datos de prueba y no tienen email real; cada uno recibe una contraseña aleatoria de 8 caracteres. | Contraseñas de 62⁸ combinaciones generadas con `secrets` y guardadas con argon2id; bloqueo tras 5 fallos; sesiones de 5/30 min; las cuentas del jurado se entregan por un canal privado. Un administrador puede cambiar una contraseña con `kcadm.sh` (E4). | V6.2.2, V6.4.1, V6.4.3, V6.4.4, V7.5.2 |
| E8 | **MFA solo en una cuenta** (`CLI-MFA000000001`, G5). | G5 pide demostrar MFA con TOTP en una sola cuenta; exigirlo a 150.000 cuentas de prueba no tiene sentido para la demo. | Lo mismo que E7. Ninguna función de la app exige un factor más fuerte (V6.8.4). | V6.3.3 |

## 3. Controles aplicables

### V1 Codificación y saneamiento

| ID | Control | Estado | Evidencia |
|---|---|---|---|
| V1.1.1 | Decodificar la entrada una sola vez, antes de validarla | ✅ | Starlette decodifica la petición y pydantic valida después; nada se decodifica dos veces. |
| V1.1.2 | Codificar la salida al final, o que lo haga el intérprete | ✅ | React escapa al renderizar; FastAPI serializa JSON; SQL con parámetros. |
| V1.2.1 | Codificación según el contexto (HTML, atributos, cabeceras) | ✅ | JSX de React (`krtr/front/src/`) y FreeMarker en el tema de Keycloak (`krtr/back/security/keycloak/themes/krtr/`). |
| V1.2.2 | URLs dinámicas codificadas; solo protocolos seguros | ✅ | `urlencode` en `krtr/back/web/routers/auth.py` y `krtr/back/security/oidc/client.py`; `encodeURIComponent` en `krtr/front/src/lib/routes.ts`. Ninguna URL lleva un protocolo elegido por el usuario. |
| V1.2.3 | JSON/JS generado con codificación | ✅ | Solo JSON serializado por FastAPI; no se genera JavaScript. |
| V1.2.4 | Consultas parametrizadas | ✅ | Todo el SQL está en `krtr/database/queries/**.sql` con `%(name)s` (regla del `CLAUDE.md`); `NeonClient.execute_params` / `fetch_all`. |
| V1.2.5 | Sin inyección de comandos del SO | ✅ | El único proceso es `kc.sh` con argumentos fijos (`krtr/back/deploy/keycloak_process.py`). |
| V1.2.9 | Escapar metacaracteres en expresiones regulares | ✅ | Ninguna expresión regular se arma con texto del usuario (`krtr/back/ia/text.py`; el patrón de `complaint_status.py` sale de la configuración). |
| V1.3.2 | Sin `eval()` ni ejecución dinámica | ✅ | No hay `eval` ni equivalentes en `krtr/` ni en `krtr/front/src/`. |
| V1.3.3 | Sanear antes de contextos peligrosos (longitud, caracteres) | ✅ | Texto ≤ 2.000, idioma por enum, `incident_id` con patrón (§3.4; `krtr/back/web/chat/artifacts.py`). |
| V1.3.6 | Protección contra SSRF | ✅ | El backend solo llama a `KRTR_AUTH_ORIGIN` y a Neon, ambos de la configuración; el usuario nunca da una URL. |
| V1.3.7 | Sin plantillas construidas con entrada no confiable | ✅ | Las plantillas del motor de IA están en el repo (`krtr/back/ia/writing/templates/`); el usuario solo aporta valores. |
| V1.3.10 | Cadenas de formato saneadas | ✅ | `str.format` solo sobre plantillas del repo; los valores nunca se usan como formato. |
| V1.4.1 | Manejo de memoria seguro | ✅ | Python y TypeScript gestionan la memoria. |
| V1.4.2 | Evitar desbordamiento de enteros | ✅ | Enteros de Python sin límite; tamaños y longitudes validados (2 MB, 2.000 caracteres, 4 KB). |
| V1.4.3 | Liberar memoria y recursos | ✅ | Memoria gestionada; las conexiones vuelven al pool en `finally` (`krtr/database/neon/client.py`). |
| V1.5.2 | Deserialización segura | ✅ | Solo JSON (pydantic y `json`); la cookie de login es JSON cifrado y autenticado (`krtr/back/security/oidc/login_cookie.py`). Sin `pickle`. |

### V2 Validación y lógica de negocio

| ID | Control | Estado | Evidencia |
|---|---|---|---|
| V2.1.1 | Reglas de validación documentadas | ✅ | §3.4 de la guía (contrato de la API) y D6. |
| V2.1.2 | Consistencia de datos combinados documentada | ✅ | Un caso solo existe para la pareja `incident_id` + `customer_id` (4.8, §3.6). |
| V2.1.3 | Límites de negocio documentados, por usuario y globales | ✅ | §1 (20 mensajes/min), D6 (2.000 caracteres, 60 s, 2 MB, 600/min por IP), 4.6 (240/min por sesión). |
| V2.2.1 | Validación positiva de toda entrada | ✅ | Modelos pydantic y enums en `krtr/back/web/*/artifacts.py`; catálogo cerrado de eventos (`krtr/back/security/audit/event_names.py`). |
| V2.2.2 | Validación en el servidor | ✅ | La del front es solo de usabilidad; `tests/back/web/routers/test_chat.py`, `test_events.py`. |
| V2.2.3 | Combinaciones de datos razonables | ✅ | Retomar un caso ajeno da el mismo 404 que uno inexistente (`e2e/security/test_production.py::test_another_customers_case_is_404`). |
| V2.3.1 | Pasos de la lógica en orden | ✅ | El callback solo vale con el `state` del login de ese navegador (`tests/back/web/routers/test_auth.py`); el chat exige un caso propio. |
| V2.3.2 | Límites de negocio implementados | ✅ | `tests/back/web/test_rate_limit.py`; `e2e/security/test_production.py::test_the_chat_answers_and_limits_to_20_messages_a_minute`. |
| V2.3.3 | Operaciones atómicas | ✅ | Cada operación es una sentencia. Abrir sesión revoca las anteriores y luego crea la nueva (`krtr/back/security/sessions/service.py`): si falla en medio, el cliente queda sin sesión (falla del lado seguro). |
| V2.4.1 | Controles anti-automatización | 🟡 | 600/min por IP, 240/min por sesión y 20/min de chat (`9491fd7`); bloqueo de Keycloak (5 → 15 min). Falta: el formulario de Keycloak no tiene límite por IP (solo el bloqueo por cuenta) y no hay WAF (E1). |

### V3 Seguridad del frontend web

| ID | Control | Estado | Evidencia |
|---|---|---|---|
| V3.2.1 | El navegador no interpreta contenido fuera de contexto | ✅ | `nosniff` y CSP en todas las respuestas; la API solo responde JSON; el audio subido nunca se sirve. |
| V3.2.2 | Texto renderizado como texto | ✅ | React; no hay `dangerouslySetInnerHTML` en `krtr/front/src/`. |
| V3.3.1 | Cookies `Secure` con prefijo `__Host-`/`__Secure-` | ✅ | `krtr/back/web/cookies.py`; `e2e/security/test_production.py::test_the_login_cookie_is_host_prefixed_and_lax`, `test_a_qa_account_logs_in_with_a_strict_session`. |
| V3.3.2 | `SameSite` según el propósito | ✅ | Sesión `Strict`, login OIDC `Lax` (D22), CSRF `Strict`; `tests/back/web/routers/test_auth.py`. |
| V3.3.3 | Prefijo `__Host-` salvo que se compartan | 🟡 | Las 3 cookies de la app lo llevan. Las de Keycloak (`AUTH_SESSION_ID`, `KEYCLOAK_IDENTITY`…) no, y no se puede configurar; son del host (sin `Domain`), `Secure` y con `Path=/realms/krtr/`. |
| V3.3.4 | `HttpOnly` en cookies que el script no necesita | ✅ | Sesión y login OIDC `HttpOnly`; la de CSRF no lo es a propósito (la SPA la copia en `X-KRTR-CSRF`, 4.5). |
| V3.4.1 | HSTS ≥ 1 año con subdominios | 🟡 | `max-age=31536000; includeSubDomains` en la app y en las respuestas de Keycloak (`krtr/back/security/headers/middleware.py`; `e2e/…::test_security_headers_are_present_and_server_is_hidden`). ZAP (`6b54337`): los 404 propios del gateway (`/`, `/admin/`) salen sin HSTS. |
| V3.4.2 | CORS fijo o con lista permitida | ✅ | La app no responde cabeceras CORS (sin `CORSMiddleware`; todo es del mismo origen). En Keycloak, `webOrigins` exactos (`realm-krtr.json`). |
| V3.4.3 | CSP con `object-src 'none'`, `base-uri 'none'` y lista permitida | 🟡 | App ✅: `build_content_security_policy` en `krtr/back/security/headers/middleware.py` (solo `'self'` y el origen de Keycloak en `form-action`; ZAP sin alertas). Keycloak ❌: su CSP es solo `frame-src 'self'; frame-ancestors 'self'; object-src 'none'` y el tema usa un `onsubmit` en línea (ZAP 10055, aceptada como pendiente en `.zap/rules.tsv`). |
| V3.4.4 | `nosniff` en todas las respuestas | ✅ | Middleware de cabeceras; también en los 429 (`tests/back/web/test_rate_limit.py::test_a_429_still_carries_the_security_headers`). |
| V3.4.5 | `Referrer-Policy` | ✅ | `no-referrer`. |
| V3.4.6 | `frame-ancestors` en todas las respuestas | ✅ | `frame-ancestors 'none'` en la app (`e2e/…::test_security_headers_are_present_and_server_is_hidden`); Keycloak pone el suyo. |
| V3.5.1 | Peticiones de otro origen rechazadas (CSRF) | ✅ | `Origin` + double-submit (`827f4b5`; `tests/back/web/test_csrf.py`; `e2e/…::test_posts_without_csrf_are_rejected`, `test_another_modal_app_cannot_post_events`). |
| V3.5.2 | Si se depende del preflight de CORS, que no se pueda saltar | ✅ | No se depende de él; además `X-KRTR-CSRF` no es una cabecera *safelisted*. |
| V3.5.3 | Funciones sensibles solo con métodos no seguros | ✅ | Todo cambio de estado es `POST` (§3.4). |
| V3.5.4 | Aplicaciones distintas en hosts distintos | ⚠️ E3 | La app y Keycloak están en hosts distintos, pero bajo el dominio compartido `modal.run`. |
| V3.5.5 | `postMessage` solo de orígenes confiables | ✅ | La SPA no escucha `postMessage`. |
| V3.7.1 | Solo tecnologías de cliente vigentes | ✅ | React + Vite + TypeScript; sin plugins. |
| V3.7.2 | Redirecciones a otros hosts solo a una lista permitida | ✅ | Solo se redirige a Keycloak (`KRTR_AUTH_ORIGIN`); el callback va siempre a `/app` o a `/?login=failed` (`0ae23d9`). No hay parámetro de redirección abierto. |

### V4 API y servicios web

| ID | Control | Estado | Evidencia |
|---|---|---|---|
| V4.1.1 | `Content-Type` correcto, con `charset` | ✅ | FastAPI: `application/json` (UTF-8 por definición, RFC 8259) y `text/html; charset=utf-8` para la SPA. |
| V4.1.2 | Solo lo que usa el navegador redirige de HTTP a HTTPS | ⚠️ E2 | Modal redirige todo con 308, también `/api/*`. HSTS evita que el navegador llegue a mandar HTTP. |
| V4.1.3 | Cabeceras de intermediarios no falsificables | ✅ | La app usa `request.client.host` y nunca `X-Forwarded-For`, `X-Real-IP` ni `Forwarded` (0.4a; `tests/back/web/test_rate_limit.py::test_a_spoofed_client_ip_header_does_not_evade_the_limit`); el gateway las reemplaza (`tests/back/security/keycloak/test_gateway.py::test_forwarding_headers_come_from_the_connection_not_the_client`). |
| V4.2.1 | Sin *request smuggling* | ⚠️ E2 | Los límites de cada mensaje los decide el borde de Modal; detrás, uvicorn (h11). No se puede verificar ni configurar. |

### V5 Manejo de archivos (notas de voz)

| ID | Control | Estado | Evidencia |
|---|---|---|---|
| V5.1.1 | Tipos, extensiones y tamaño documentados | ✅ | §3.4 y §1: WebM/Opus o MP4/AAC, ≤ 60 s, ≤ 2 MB; el audio no se guarda. |
| V5.2.1 | Tamaño máximo procesable | ✅ | Límite global de `Content-Length` y 2 MB por nota (`a3e60a2`; `tests/back/web/chat/test_audio.py`). |
| V5.2.2 | Extensión/tipo coherentes con el contenido (bytes mágicos) | ✅ | `krtr/back/web/chat/audio.py`; `e2e/…::test_a_fake_voice_file_is_415`. |
| V5.3.2 | Rutas de archivo sin datos del usuario | ✅ | El audio se procesa en memoria; ninguna ruta usa el nombre del archivo. |

### V6 Autenticación

| ID | Control | Estado | Evidencia |
|---|---|---|---|
| V6.1.1 | Defensas contra fuerza bruta documentadas, sin facilitar bloqueos maliciosos | 🟡 | §1, 3.2 y 4.6. El bloqueo es temporal (15 min), pero quien conozca un `customer_id` puede bloquearlo: Keycloak no tiene límite por IP (E1). |
| V6.1.3 | Todas las vías de autenticación documentadas | ✅ | Una sola: el formulario de Keycloak (contraseña + OTP condicional), §3.2. |
| V6.2.1 | Contraseñas de al menos 8 caracteres | ✅ | `passwordPolicy: length(8)` (`realm-krtr.json`); las generadas tienen 8 (3.4). |
| V6.2.2 | El usuario puede cambiar su contraseña | ⚠️ E7 | No hay cambio de contraseña (D5). |
| V6.2.5 | Sin reglas de composición | ✅ | La política del realm solo exige la longitud. |
| V6.2.6 | Campo `type=password` | ✅ | `themes/krtr/login/login.ftl`. |
| V6.2.7 | Se permite pegar y usar gestores de contraseñas | ✅ | `autocomplete="current-password"`; nada bloquea pegar. |
| V6.2.8 | La contraseña se verifica tal cual | ✅ | Keycloak no la transforma. Solo el `customer_id` pasa a mayúsculas (`01e6854`). |
| V6.2.10 | Sin rotación periódica obligatoria | ✅ | Sin política de expiración en el realm. |
| V6.3.1 | Controles contra *credential stuffing* y fuerza bruta | ✅ | 5 fallos → 15 min en `krtr` y en `master` (3.2, 6.6); `e2e/…::test_five_wrong_passwords_lock_the_account` (`cbcc9fc`). |
| V6.3.2 | Sin cuentas por defecto | ⚠️ E4 | Existe el admin del realm `master` (con contraseña de un Modal Secret y bloqueo por fuerza bruta), pero `/admin` y `/realms/master` dan 404 desde internet (`e2e/…::test_keycloak_admin_and_operational_paths_are_hidden`). |
| V6.3.3 | MFA para entrar | ⚠️ E8 | Solo una cuenta tiene TOTP. |
| V6.3.4 | Sin vías no documentadas | ✅ | Desactivados: *implicit*, *direct access grants* (contraseña), registro, recuperación y "recordarme" (`realm-krtr.json`; `tests/back/security/keycloak/test_realm_krtr.py`). |
| V6.4.1 | Contraseñas iniciales aleatorias, que caducan tras el primer uso | ⚠️ E7 | Aleatorias con `secrets` (`krtr/back/security/credentials/generator.py`), pero son la contraseña definitiva. |
| V6.4.2 | Sin pistas ni preguntas secretas | ✅ | No existen. |
| V6.4.3 | Recuperación segura de contraseña | ⚠️ E7 | No hay recuperación (D5); un administrador la cambia con `kcadm.sh` (E4). |
| V6.4.4 | Recuperar un factor MFA perdido exige comprobar la identidad | ⚠️ E7 | Se resuelve a mano por el equipo con `kcadm.sh`. |
| V6.5.1 | Un TOTP sirve una sola vez | ✅ | `otpPolicyCodeReusable: false`. |
| V6.5.3 | Semillas TOTP con CSPRNG | ✅ | Las genera Keycloak (`SecureRandom`). |
| V6.5.5 | TOTP con vida de 30 s | ✅ | `otpPolicyPeriod: 30`. |
| V6.8.2 | Firma de las aserciones siempre validada | ✅ | `krtr/back/security/oidc/client.py::_validate_id_token` (joserfc); `tests/back/security/oidc/test_client.py`. |
| V6.8.4 | Fuerza de autenticación exigida por función, o *fallback* documentado | ✅ | Ninguna función exige más que contraseña; la app asume un factor (este documento, E8). |

### V7 Gestión de sesiones

| ID | Control | Estado | Evidencia |
|---|---|---|---|
| V7.1.1 | Tiempos de inactividad y máximo documentados y justificados frente a NIST 800-63B | ✅ | §1 (G15): 5 min sin actividad y 30 min como máximo. Es más estricto que lo que NIST SP 800-63B pide para AAL2 (30 min de inactividad, 24 h como máximo). |
| V7.1.2 | Sesiones simultáneas documentadas | ✅ | Una por usuario; un nuevo login cierra la anterior (G15). |
| V7.1.3 | Sesiones federadas documentadas | ✅ | La sesión SSO de Keycloak tiene los mismos tiempos (5/30 min, 3.2) y el logout la cierra (4.3). |
| V7.2.1 | Verificación del token de sesión en el backend | ✅ | Sesiones del servidor (`a26970f`). |
| V7.2.2 | Tokens dinámicos, no secretos fijos | ✅ | Un token nuevo por login. |
| V7.2.3 | Tokens de referencia con CSPRNG y ≥ 128 bits | ✅ | `secrets.token_urlsafe(32)` = 256 bits; en la base solo su SHA-256 (`krtr/back/security/sessions/`). |
| V7.2.4 | Token nuevo en cada autenticación; el anterior se termina | ✅ | `tests/back/web/routers/test_auth.py::test_a_new_login_closes_the_customers_previous_session`; `e2e/…::test_a_second_login_closes_the_first`. |
| V7.3.1 | Cierre por inactividad | ✅ | 5 min; `e2e/…::test_an_idle_session_closes_after_5_minutes` (`--run-slow`, `cbcc9fc`). |
| V7.3.2 | Duración máxima absoluta | ✅ | 30 min; `tests/back/security/sessions/test_service.py`. |
| V7.4.1 | La sesión terminada deja de servir | ✅ | El logout revoca la fila, cierra la sesión en Keycloak y revoca el refresh token (`krtr/back/web/routers/auth.py`, `oidc/client.py::end_session`). |
| V7.4.2 | Se cierran las sesiones de una cuenta desactivada | 🟡 | Se cierran al siguiente refresco del access token (≤ 5 min), cuando Keycloak lo rechaza (4.4). No es inmediato. |
| V7.4.4 | Cerrar sesión visible en toda página autenticada | ✅ | `krtr/front/src/components/app-header.tsx`. |
| V7.4.5 | Un administrador puede cerrar sesiones | 🟡 E4 | Sin interfaz: con `app_sessions/revoke_by_customer.sql` en la base y con `kcadm.sh` en Keycloak. |
| V7.5.2 | El usuario ve y cierra sus otras sesiones | ⚠️ E7 | Solo puede haber una sesión; iniciar sesión de nuevo cierra la otra. |
| V7.6.1 | Duración coordinada entre la app y el IdP | ✅ | Ver V7.1.3. |
| V7.6.2 | Crear una sesión exige una acción explícita | ✅ | Solo con el formulario de Keycloak; las dos sesiones caducan juntas, así que no hay inicio silencioso. |

### V8 Autorización

| ID | Control | Estado | Evidencia |
|---|---|---|---|
| V8.1.1 | Reglas de acceso documentadas | ✅ | §3.4 (columna "Autenticación") y 4.8 (cada cliente solo ve sus casos). |
| V8.1.2 | Reglas por campo documentadas | ✅ | Un solo tipo de usuario (cliente); cada respuesta tiene campos fijos (§3.4). |
| V8.2.1 | Acceso por función solo con permiso | ✅ | Dependencias de sesión en cada ruta de `/api/*`; `e2e/…::test_the_api_needs_a_session`. |
| V8.2.2 | Acceso por dato (IDOR/BOLA) | ✅ | `incident_id` + `customer_id` (`bdaa661`; `tests/back/web/routers/test_cases.py`; `e2e/…::test_another_customers_case_is_404`); `messages` siempre filtra por los dos (`select_by_case.sql`). |
| V8.2.3 | Acceso por campo (BOPLA) | ✅ | Las respuestas solo traen los campos del contrato; las entradas son modelos pydantic cerrados. |
| V8.3.1 | Autorización en el servidor | ✅ | Toda la decide el backend; la SPA no decide nada. |

### V9 Tokens autocontenidos (el ID token de Keycloak)

| ID | Control | Estado | Evidencia |
|---|---|---|---|
| V9.1.1 | Firma validada antes de usar el token | ✅ | `jwt.decode` con las llaves del realm (`krtr/back/security/oidc/client.py`). |
| V9.1.2 | Lista de algoritmos, sin `none` | ✅ | `ID_TOKEN_ALGORITHMS = ["RS256"]`. |
| V9.1.3 | Llaves de una fuente preconfigurada | ✅ | JWKS del emisor configurado; no se siguen `jku`, `x5u` ni `jwk`. |
| V9.2.1 | Vigencia (`exp`) verificada | ✅ | `exp` esencial en `_claims_registry`. |
| V9.2.2 | Tipo de token correcto para su propósito | ✅ | El ID token solo identifica; la app autoriza con su propia sesión, nunca con el access token. |
| V9.2.3 | Audiencia validada | ✅ | `aud` = `krtr-web`. |
| V9.2.4 | Audiencias distintas con la misma llave | ✅ | Keycloak emite `aud`/`azp` por cliente, y el realm solo tiene el cliente `krtr-web`. |

### V10 OAuth y OIDC

| ID | Control | Estado | Evidencia |
|---|---|---|---|
| V10.1.1 | Tokens solo donde se necesitan (BFF) | ✅ | El navegador nunca los ve; en la base van cifrados con `KRTR_TOKENS_KEY` (`tests/back/web/routers/test_auth.py::test_the_session_cookie_holds_no_token_from_keycloak`). |
| V10.1.2 | `state`, `nonce` y PKCE ligados al navegador y la transacción | ✅ | Cookie `__Host-krtr_oidc` cifrada, 10 min, comparación en tiempo constante (`0af3a00`; `tests/back/security/oidc/test_login_cookie.py`). |
| V10.2.1 | Protección CSRF del flujo de código | ✅ | PKCE S256 + `state`. |
| V10.4.1 | Redirect URIs exactas y registradas | 🟡 | Exactas (`realm-krtr.json`, `test_realm_krtr.py`), pero el cliente de producción también acepta `http://localhost:8000/auth/callback`. Conviene quitarla en producción. |
| V10.4.2 | Código de un solo uso | ✅ | Comportamiento de Keycloak. |
| V10.4.3 | Código de vida corta (≤ 10 min) | ✅ | `accessCodeLifespan: 60`. |
| V10.4.4 | Solo los *grants* necesarios; sin `token` ni `password` | ✅ | `standardFlowEnabled` sí; `implicitFlowEnabled` y `directAccessGrantsEnabled` no. |
| V10.4.6 | PKCE obligatorio, sin `plain` | ✅ | `pkce.code.challenge.method: S256`. |
| V10.4.7 | Registro dinámico anónimo controlado | ✅ | Política *Trusted Hosts* sin hosts de confianza (`realm-krtr.json`, componentes de `clientregistration`). |
| V10.4.8 | Refresh tokens con caducidad absoluta | ✅ | Atados a la sesión SSO: 30 min (`ssoSessionMaxLifespan: 1800`). |
| V10.4.9 | El usuario puede revocar tokens desde el servidor de autorización | ⚠️ E4 | Sin consola de cuenta (D5). El logout revoca el refresh token. |
| V10.4.10 | Cliente confidencial autenticado en el canal trasero | ✅ | `client_secret_basic` en token, logout y revocación (`oidc/client.py::_post`). |
| V10.4.11 | Solo los *scopes* necesarios | 🟡 | La app pide solo `openid`, pero el cliente tiene *scopes* opcionales que no usa (`offline_access`, `address`, `phone`, `organization`, `microprofile-jwt`) y `fullScopeAllowed: true`. |
| V10.5.1 | Protección contra reuso del ID token (`nonce`) | ✅ | `nonce` esencial; `tests/back/web/routers/test_auth.py::test_a_code_keycloak_rejects_does_not_log_in`. |
| V10.5.2 | Identificar al usuario por un claim no reasignable | 🟡 | La app usa `preferred_username` (el `customer_id`), no `sub`. En este realm no se puede reasignar (`editUsernameAllowed: false`, sin registro), y `sub` también se valida y se guarda. |
| V10.5.3 | Rechazar metadatos con otro `issuer` | ✅ | No se leen metadatos: los endpoints salen del `issuer` configurado y `iss` se valida. |
| V10.5.4 | `aud` = `client_id` | ✅ | Ver V9.2.3. |
| V10.6.1 | Solo `code` como tipo de respuesta | ✅ | Ver V10.4.4. |
| V10.6.2 | Protección contra logout forzado | ✅ | El logout va por el canal trasero con el refresh token; un logout desde el navegador sin `id_token_hint` pide confirmación (comportamiento de Keycloak 26). |

### V11 Criptografía

| ID | Control | Estado | Evidencia |
|---|---|---|---|
| V11.1.1 | Política de gestión de llaves | 🟡 | Se generan con `secrets` solo si no existen y se rotan con `--rotate` (6.1); están en Modal Secrets y en el gestor de contraseñas; hay una llave por propósito. Falta un ciclo de vida formal (NIST SP 800-57). |
| V11.1.2 | Inventario criptográfico | ✅ | §6 de este documento. |
| V11.2.1 | Implementaciones validadas | ✅ | `cryptography` (OpenSSL), joserfc, y argon2/RSA de Keycloak. |
| V11.2.2 | Agilidad criptográfica | 🟡 | El blob no guarda la versión de la llave: rotar `KRTR_EVENTS_KEY` o `KRTR_MESSAGES_KEY` deja ilegibles las filas viejas (se purgan a los 3 meses). |
| V11.2.3 | ≥ 128 bits de seguridad | 🟡 | AES-256 y SHA-256 sí; la llave RSA del realm es de 2048 bits (≈ 112 bits, lo que trae Keycloak por defecto). Conviene una de 3072. |
| V11.3.1 | Sin modos inseguros (ECB) | ✅ | Solo AES-GCM. |
| V11.3.2 | Solo cifrados aprobados | ✅ | AES-256-GCM (`krtr/back/security/crypto/cipher.py`). |
| V11.3.3 | Cifrado autenticado | ✅ | GCM; `e2e/security/test_encryption_at_rest.py::test_stored_values_open_only_with_the_app_key` (`cbcc9fc`). |
| V11.4.1 | Solo funciones hash aprobadas | 🟡 | SHA-256 en la app. El TOTP usa HMAC-SHA1 (RFC 6238, por compatibilidad con las apps de autenticación). |
| V11.4.2 | Contraseñas con una función de hash lenta | ✅ | argon2id con los parámetros por defecto de Keycloak 26.8 (3.4). |
| V11.4.3 | Hashes resistentes a colisiones, ≥ 256 bits | ✅ | SHA-256 (hash del token de sesión). |
| V11.5.1 | Aleatorios con CSPRNG y ≥ 128 bits | ✅ | `secrets` para la sesión (256), CSRF, `state` y `nonce` (256) y PKCE (512). Los UUID solo identifican filas. |
| V11.6.1 | Generación de llaves y firmas aprobadas | ✅ | RS256 con llaves generadas por Keycloak. |

### V12 Comunicaciones seguras

| ID | Control | Estado | Evidencia |
|---|---|---|---|
| V12.1.1 | Solo TLS 1.2 y 1.3 | ⚠️ E2 | Medido en 0.4(b): solo 1.2 y 1.3; no lo configuramos nosotros. |
| V12.1.2 | Solo suites de cifrado recomendadas | ⚠️ E2 | No se pueden configurar. |
| V12.2.1 | TLS en todo lo externo, sin bajar a HTTP | ✅ | HTTPS + HSTS; `http://` → 308 (0.4c). |
| V12.2.2 | Certificados de confianza pública | ⚠️ E3 | El certificado `*.modal.run` de Modal; sin dominio propio. |
| V12.3.1 | Cifrado en todas las conexiones internas | 🟡 | App → Neon con `sslmode=require&channel_binding=require`; Keycloak → Neon con `sslmode=require` (`krtr/back/deploy/secrets.py`); app → Keycloak por HTTPS. El gateway llega a Keycloak por HTTP en `127.0.0.1`, dentro del mismo contenedor. |
| V12.3.2 | Los clientes TLS validan el certificado | 🟡 | httpx valida por defecto. Hacia Neon, `sslmode=require` cifra pero **no valida** el certificado: conviene `verify-full`. |
| V12.3.3 | Cifrado entre servicios HTTP internos | 🟡 | Ver V12.3.1: el tramo gateway → Keycloak es *loopback* dentro del contenedor. |
| V12.3.4 | Certificados de confianza en conexiones internas | ✅ | Neon y Modal usan certificados públicos. |

### V13 Configuración

| ID | Control | Estado | Evidencia |
|---|---|---|---|
| V13.1.1 | Comunicaciones documentadas | ✅ | §3.1 de la guía; el usuario nunca indica un destino. |
| V13.2.1 | Autenticación entre componentes sin credenciales fijas | ⚠️ E1 | Neon usa contraseña por rol (no ofrece credenciales de corta vida en este plan); un rol por servicio. |
| V13.2.2 | Mínimo privilegio entre componentes | ✅ | `krtr_app` solo usa sus tablas, `krtr_keycloak` su base y `krtr_audit_reader` solo lee `event_entity` (1.3). Nota: el contenedor corre como root (E5). |
| V13.2.3 | Sin credenciales por defecto | ✅ | Todas generadas (6.1). |
| V13.2.4 | Lista de destinos permitidos | 🟡 E1 | Implícita por configuración (`KRTR_AUTH_ORIGIN`, `NEON_DB_HOST`); Modal no permite filtrar la salida. |
| V13.2.5 | Servidor limitado a esos destinos | 🟡 E1 | Igual que V13.2.4. |
| V13.3.1 | Gestor de secretos; nada en el código | ✅ | Modal Secrets (6.1); `.env` y `data/credentials/` fuera de git; gitleaks en el CI (`43b3d82`). |
| V13.3.2 | Acceso a secretos con mínimo privilegio | ✅ | Un secreto por función: `krtr-web`, `krtr-auth`, `krtr-jobs` (6.1; `tests/back/deploy/test_secrets.py`). |
| V13.4.1 | Sin metadatos de control de versiones | ✅ | La imagen solo lleva el paquete `krtr` y el front compilado (`krtr/back/deploy/images.py`). |
| V13.4.2 | Sin modos de depuración | ✅ | `KRTR_WEB_ENVIRONMENT=production`; FastAPI sin `debug`. Nota E6 sobre las cabeceras de Modal. |
| V13.4.3 | Sin listado de directorios | ✅ | `StaticFiles` sin listado; las rutas desconocidas devuelven la SPA. |
| V13.4.4 | Sin `TRACE` | ✅ | Ninguna ruta acepta `TRACE` (FastAPI responde 405). |
| V13.4.5 | Sin documentación ni monitoreo expuestos | ✅ | `/docs`, `/openapi.json` y `/redoc` dan 404; en Keycloak `/metrics` y `/health*` también (`e2e/…::test_api_docs_are_not_published`, `test_keycloak_admin_and_operational_paths_are_hidden`). |

### V14 Protección de datos

| ID | Control | Estado | Evidencia |
|---|---|---|---|
| V14.1.1 | Datos sensibles identificados y clasificados | ✅ | §7 de este documento. |
| V14.1.2 | Requisitos de protección por nivel | 🟡 | §3.5, §3.6 y §7: cifrado, retención y qué nunca se registra. Falta el control de acceso a los registros de Modal. |
| V14.2.1 | Sin datos sensibles en la URL | ✅ | El token de sesión va en una cookie. `code` y `state` viajan en la URL del callback porque así es OAuth (vida de 60 s, un solo uso). |
| V14.2.2 | Sin datos sensibles en cachés del servidor | ✅ | `Cache-Control: no-store` en `/api/*` (`tests/back/security/headers/test_middleware.py::test_api_routes_get_cache_control_no_store`); Modal no cachea. |
| V14.2.3 | Sin enviar datos a terceros (rastreadores) | ✅ | Sin analítica externa; CSP `connect-src 'self'`. |
| V14.2.4 | Controles implementados según la clasificación | ✅ | `e2e/security/test_encryption_at_rest.py`; purga a los 3 meses (`tests/back/security/audit/test_retention.py`). |
| V14.3.1 | Datos borrados del cliente al cerrar sesión | 🟡 | La SPA guarda los datos solo en memoria y el logout recarga la landing; no hay `Clear-Site-Data`. |
| V14.3.2 | Cabeceras anti-caché | ✅ | `no-store` en toda la API; el HTML y los assets no llevan datos del cliente. |
| V14.3.3 | Nada sensible en el almacenamiento del navegador | ✅ | `localStorage` solo guarda el idioma (D14). |

### V15 Código y arquitectura

| ID | Control | Estado | Evidencia |
|---|---|---|---|
| V15.1.1 | Plazos para corregir dependencias vulnerables | ❌ | No están definidos (§5). |
| V15.1.2 | Inventario de dependencias (SBOM) | 🟡 | `uv.lock` y `package-lock.json` con versiones exactas, de PyPI y npm; no se genera un SBOM. |
| V15.1.3 | Funciones costosas identificadas | ✅ | El chat (motor de IA, D7), la voz (2 MB), el login (argon2id en Keycloak, 1 CPU) y la importación (6.4). |
| V15.2.1 | Dependencias dentro de los plazos | 🟡 | `pip-audit` y `npm audit` en el CI (7.1); falta verlos en verde en GitHub y fijar los plazos (V15.1.1). |
| V15.2.2 | Defensas de disponibilidad | ✅ | Límites de 4.6, de `Content-Length` y de 2 MB. Carga de 7.5 (`e2e/load/locustfile.py`, `aba9ffd`): p95 de 240–250 ms y 0 respuestas 5xx con 20 y 50 usuarios. |
| V15.2.3 | En producción solo lo necesario | ✅ | Sin el grupo `dev` (`--no-dev`, 6.2); sin `/docs`. |
| V15.3.1 | Solo los campos necesarios | ✅ | `/api/me` devuelve 3 campos; los casos, 3 (§3.4). |
| V15.3.2 | El backend no sigue redirecciones salvo que se quiera | ✅ | httpx no las sigue por defecto (cliente OIDC); el gateway las devuelve sin seguirlas (`test_gateway.py::test_a_redirect_is_passed_on_unchanged`). |
| V15.3.3 | Protección contra asignación masiva | ✅ | Modelos pydantic con campos explícitos por endpoint. |
| V15.3.4 | La IP original viene de una fuente confiable | ✅ | Ver V4.1.3. |
| V15.3.5 | Tipos estrictos y comparaciones seguras | ✅ | pydantic y enums; `secrets.compare_digest` para `state` y CSRF. |
| V15.3.6 | Sin contaminación de prototipos en JS | 🟡 | La SPA no fusiona objetos que vengan de fuera, pero no se revisó a fondo con este control en mente. |
| V15.3.7 | Sin contaminación de parámetros HTTP | ✅ | FastAPI declara de dónde sale cada parámetro (query, cuerpo, cookie). |

### V16 Registro de eventos y errores

| ID | Control | Estado | Evidencia |
|---|---|---|---|
| V16.1.1 | Inventario de registros | ✅ | §8 de este documento. |
| V16.2.1 | Metadatos suficientes (cuándo, dónde, quién, qué) | ✅ | `http_request` con método, ruta, estado, latencia, IP, user-agent y `request_id`; `occurred_at`; `customer_id` en los eventos de login y sesión (§3.5). |
| V16.2.2 | Hora sincronizada y en UTC | ✅ | `TIMESTAMPTZ` en UTC (`krtr/back/security/clock.py`). |
| V16.2.3 | Solo los destinos del inventario | ✅ | La tabla `events` y los registros de los contenedores de Modal. |
| V16.2.4 | Registros legibles por el procesador | 🟡 | `properties` está cifrado y solo se lee con la llave; no hay un procesador de registros. |
| V16.2.5 | Datos sensibles registrados según su nivel | ✅ | Nunca contraseñas, tokens ni cookies (§3.5); el texto del chat va a `messages`, cifrado. |
| V16.3.1 | Todas las autenticaciones registradas | 🟡 | La app registra `auth_login_started`, `auth_login_succeeded` y `auth_login_failed`. Las contraseñas incorrectas solo quedan en `event_entity` de Keycloak (90 días); falta copiarlas a `events` (4.10). |
| V16.3.2 | Autorizaciones fallidas registradas | ✅ | `unauthorized_request`, `csrf_rejected`, `case_resume_failed`. |
| V16.3.3 | Intentos de saltarse controles registrados | ✅ | `rate_limit_exceeded`, `csrf_rejected`, `client_error`. |
| V16.3.4 | Errores inesperados registrados | ✅ | `server_error` y `logger.exception`. |
| V16.4.1 | Sin inyección en los registros | ✅ | Los eventos se guardan como JSON cifrado, nunca como texto concatenado. |
| V16.4.2 | Registros protegidos contra acceso y cambios | 🟡 | Cifrados, pero `krtr_app` puede hacer `UPDATE` y `DELETE` en `events` (1.3): no son *append-only*. |
| V16.4.3 | Registros en un sistema separado | ⚠️ E1 | Viven en Neon y en Modal; no hay SIEM. |
| V16.5.1 | Mensaje genérico en errores | ✅ | Forma `{error, message_key}` (§3.4); sin trazas en producción. |
| V16.5.2 | Seguir operando seguro si falla un recurso externo | ✅ | El gateway responde 502/504 (`test_gateway.py`); si Keycloak falla, el login se rechaza. |
| V16.5.3 | Fallar de forma segura (sin *fail-open*) | ✅ | Un login con error vuelve a la landing sin sesión (`0ae23d9`); una sesión inválida da 401; sin CSRF, 403. |

## 4. Controles que no aplican

| Controles | Por qué |
|---|---|
| V1.2.6, V1.2.7, V1.2.8, V1.3.8, V1.3.9, V1.3.11, V1.5.1 | No hay LDAP, XPath, LaTeX, JNDI con datos del usuario, memcache, correo ni XML. |
| V1.3.1, V1.3.4, V1.3.5 | No se acepta HTML, SVG ni Markdown del usuario; el chat se muestra como texto. |
| V2.3.4 | No hay recursos de cantidad limitada que reservar. |
| V4.3.1, V4.3.2, V4.4.1–V4.4.4 | No hay GraphQL ni WebSockets. |
| V5.2.3, V5.3.1, V5.4.1–V5.4.3 | El audio no se descomprime, no se guarda y no se descarga. |
| V6.1.2, V6.2.3, V6.2.4, V6.2.9, V6.2.11, V6.2.12 | Los usuarios no crean ni cambian contraseñas: las genera el sistema (E7). |
| V6.5.2, V6.5.4, V6.6.1–V6.6.3 | Sin códigos de respaldo, SMS ni autenticación fuera de banda. |
| V6.8.1, V6.8.3 | Un solo proveedor de identidad; sin SAML. |
| V7.4.3, V7.5.1 | El usuario no puede cambiar factores ni atributos de su cuenta. |
| V8.4.1 | No es una aplicación multi-inquilino (el aislamiento entre clientes está en V8.2.2). |
| V10.2.2 | Un solo servidor de autorización. |
| V10.3.1–V10.3.4 | La app no es un servidor de recursos: no acepta access tokens. |
| V10.4.5 | Aplica a clientes públicos; `krtr-web` es confidencial. |
| V10.5.5 | No se usa *back-channel logout*. |
| V10.7.1–V10.7.3 | `krtr-web` es un cliente propio (*first-party*), sin consentimiento (`consentRequired: false`). |
| V11.4.4 | No se derivan llaves de contraseñas. |
| V12.1.3 | Sin mTLS. |
| V17.1.1, V17.2.1–V17.2.4, V17.3.1, V17.3.2 | No hay WebRTC: la voz se sube como archivo. |

Total: 57 controles.

## 5. Pendientes y recomendaciones

| # | Control | Qué hacer | Prioridad |
|---|---|---|---|
| 1 | V15.1.1 ❌ / V15.2.1 | Fijar plazos: crítica en 48 h, alta en 7 días, media en 30. Ver el job `security` en verde en GitHub. | Alta |
| 2 | V12.3.2 / V12.3.1 | Cambiar `sslmode=require` por `verify-full` (app y Keycloak) para validar el certificado de Neon. | Alta |
| 3 | V10.4.1 | Quitar `http://localhost:8000/…` de las URIs del cliente en el realm de producción (con `kcadm.sh`, E4). | Media |
| 4 | V16.3.1 | Programar `sync_auth_events` (4.10 / 6.5) para que los fallos de login lleguen a `events`. | Media |
| 5 | V10.4.11 | Quitar los *scopes* opcionales que no se usan y desactivar `fullScopeAllowed`. | Baja |
| 6 | V16.4.2 | Quitar `UPDATE` sobre `events` a `krtr_app` y dejar `DELETE` solo a la purga. | Baja |
| 7 | V11.2.3 | Agregar una llave RSA de 3072 bits al realm. | Baja |
| 8 | V11.2.2 / V11.1.1 | Guardar un identificador de llave en cada blob para poder rotar sin perder datos. | Baja |
| 9 | V2.4.1 / V6.1.1 | Límite por IP en el gateway de Keycloak, para frenar bloqueos masivos de cuentas. | Baja |
| 10 | V3.4.3 | CSP de Keycloak: quitar el `onsubmit` en línea de `login.ftl`, fijar `browserSecurityHeaders.contentSecurityPolicy` del realm (con `default-src 'self'`) con `kcadm.sh` y desplegar; luego sacar la regla 10055 de `.zap/rules.tsv`. | Media |
| 11 | V3.4.1 | Que el gateway agregue las cabeceras de seguridad también a sus propios 404. | Baja |

## 6. Inventario criptográfico (V11.1.2)

| Qué | Algoritmo | Llave / secreto | Dónde vive | Protege |
|---|---|---|---|---|
| `events.properties` | AES-256-GCM, nonce de 96 bits | `KRTR_EVENTS_KEY` | Secretos `krtr-web` y `krtr-jobs` | Metadatos de eventos |
| `messages.content` | AES-256-GCM | `KRTR_MESSAGES_KEY` | Secreto `krtr-web` | Texto del chat |
| Tokens OIDC en `app_sessions` y cookie `__Host-krtr_oidc` | AES-256-GCM | `KRTR_TOKENS_KEY` | Secreto `krtr-web` | Access, refresh e ID tokens; `state`, `nonce` y PKCE |
| Token de sesión | 256 bits de `secrets`; en la base, SHA-256 | — | Cookie `__Host-krtr_session` | Identifica la sesión |
| Token CSRF | `secrets` (`CSRF_TOKEN_BYTES`) | — | Cookie `__Host-krtr_csrf` | Double-submit |
| Contraseñas | argon2id (Keycloak 26.8) | — | Base `keycloak` | Credenciales |
| Firma de tokens | RS256, RSA 2048 | Llaves del realm (las genera Keycloak) | Base `keycloak` | ID y access tokens |
| TOTP | HMAC-SHA1, 6 dígitos, 30 s | Semilla por usuario | Base `keycloak` | Segundo factor (1 cuenta) |
| Cliente OIDC | Secreto compartido (`client_secret_basic`) | `KRTR_WEB_OIDC_CLIENT_SECRET` | Secretos `krtr-web` y `krtr-auth` | Canal trasero con Keycloak |
| TLS | TLS 1.2/1.3 (Modal, Neon) | Certificados públicos | Borde de Modal y Neon | Tránsito |

## 7. Clasificación de datos (V14.1.1)

| Dato | Nivel | Dónde | Protección |
|---|---|---|---|
| Contraseñas en claro (jurado, QA, MFA) | Secreto | `data/credentials/` (fuera de git, `600`) | Nunca en el repo; se entregan por canal privado. Las demás se descartan (3.4). |
| Tokens OIDC y de sesión | Secreto | `app_sessions`, cookies | Cifrados o hasheados; el navegador solo tiene el token de sesión, `HttpOnly`. |
| Texto del chat (saldos, tarjetas enmascaradas) | Confidencial | `messages` | AES-256-GCM, 3 meses, lectura por `incident_id` + `customer_id`. |
| Eventos (IP, user-agent, `customer_id`, rutas) | Interno | `events` | AES-256-GCM, 3 meses, sin contraseñas, tokens ni cookies. |
| `customer_id`, casos | Interno | `app_sessions`, repositorio de casos | Solo los ve su dueño (V8.2.2). |
| Productos y quejas | Confidencial | Tablas de Neon | `krtr_app` solo las lee; el motor filtra por cliente. |

## 8. Inventario de registros (V16.1.1)

| Registro | Qué guarda | Dónde | Acceso | Retención |
|---|---|---|---|---|
| `events` | El catálogo de §3.5 (HTTP, login, sesión, UI, chat, voz, seguridad) | Neon, cifrado | `krtr_app` escribe; `neondb_owner` administra | 3 meses (`purge_events`, diario) |
| `messages` | Texto del chat | Neon, cifrado | `krtr_app` | 3 meses (misma purga) |
| `event_entity` | Eventos de login y de administración de Keycloak | Base `keycloak` | `krtr_keycloak`; `krtr_audit_reader` solo lee (permiso en `dev`; en `production`, pendiente de 6.6) | 90 días (`eventsExpiration`) |
| Registros de los contenedores | `logging` de la app, de Keycloak y de los crons | Panel de Modal | Miembros del workspace | La que define Modal |
