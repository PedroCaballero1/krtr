# Comportamiento de la plataforma Modal

_Tarea 0.4 de [`guia-web-seguridad_modal.md`](guia-web-seguridad_modal.md) · Medido el 1-oct-2026, de 23:02 a 23:07 (UTC−5) · Workspace `juan-alvarezo-2002`, entorno `main` · SDK `modal` 1.5.5_

Para responder estas preguntas se desplegó una app temporal, `krtr-probe`: un endpoint que devuelve lo que recibe el contenedor (el código está en el [anexo](#anexo-código-de-krtr-probe)). Quedó publicada en `https://juan-alvarezo-2002--krtr-probe.modal.run`, se probó con `curl` y `openssl`, y al terminar se detuvo: `modal app list` la muestra `stopped` y la URL responde 404.

> En la evidencia, la IP pública del equipo que hizo las pruebas aparece como `<IP pública>`. Es la misma en las tres salidas donde aparece.

## Resumen

| # | Pregunta | Respuesta |
|---|---|---|
| (a) | ¿Qué trae la IP real del cliente? ¿Es confiable? | La **dirección del cliente en ASGI** (`request.client.host`): Modal pone ahí la IP real. Modal **no** envía `X-Forwarded-For` y **descarta** el que mande el cliente. `X-Real-IP` y `Forwarded` llegan tal como los manda el cliente, así que **no son confiables**. |
| (b) | ¿Qué versiones de TLS acepta `*.modal.run`? | **TLS 1.2 y 1.3.** Rechaza TLS 1.0 y 1.1 con `alert protocol version`. |
| (c) | ¿`http://` redirige a `https://`? | **Sí**, con `308 Permanent Redirect` a la misma ruta. Esa respuesta la da el borde de Modal e incluye `Server: Caddy`. |
| (d) | ¿`modal.run` está en la Public Suffix List? | **No.** Para el navegador, todas las apps `*.modal.run`, de cualquier usuario, son el mismo sitio. |
| (e) | ¿Cuánto tarda un arranque en frío? | Entre **3,6 y 5,8 s** hasta la primera respuesta de un contenedor pequeño (FastAPI sobre `debian_slim`), contra 0,3–0,6 s en caliente. |
| (f) | ¿Qué cabeceras agrega Modal? ¿Con qué usuario corre el contenedor? | En HTTPS **no agrega `Server`**. Agrega `alt-svc` (HTTP/3), `modal-function-call-id` y `vary: accept-encoding`. El proceso corre como **root** (uid 0). |

Además, **sin fijar región, Modal ubicó cada contenedor en un sitio distinto**: `us-east` en AWS, `us-east` en Azure y `us-central` en GCP. Neon está en AWS `us-east-1`.

## Qué implica para otras tareas

- **4.6 (límite por IP, D6):** tomar la IP de `request.client.host`. No usar `X-Forwarded-For` (nunca llega), ni `X-Real-IP` ni `Forwarded` (los controla el cliente).
- **3.7 (gateway de Keycloak):** con `KC_PROXY_HEADERS=xforwarded`, Keycloak confía en las cabeceras `X-Forwarded-*`. El gateway tiene que fijar `X-Forwarded-For` (con `request.client.host`), `X-Forwarded-Proto` y `X-Forwarded-Host` reemplazando lo que mande el cliente, y descartar `Forwarded` y `X-Real-IP`.
- **D22 y 4.5:** como `modal.run` no es un sufijo público, cualquier otra app de Modal es "el mismo sitio" que la nuestra, y `SameSite` no la frena. Por eso son imprescindibles el prefijo `__Host-` en todas las cookies (otra app de `*.modal.run` no puede sobrescribirlas) y la validación exacta de `Origin`. La vuelta desde Keycloak también es del mismo sitio: `SameSite=Lax` en `__Host-krtr_oidc` funciona, aunque el motivo que da D22 ("navegación entre sitios distintos") no aplica.
- **4.2 y 7.2 (cabeceras y TLS):** Modal no agrega `Server` en HTTPS, así que la prueba "no se filtra `Server`" aplica tal cual. TLS 1.0 y 1.1 ya se rechazan, así que 7.2 puede comprobarlo como en la v1.
- **7.4 y 7.6 (excepciones de la plataforma):** el contenedor corre como root (el `Dockerfile` retirado usaba un usuario sin privilegios), la redirección de `http://` muestra `Server: Caddy` y `modal-function-call-id` expone un identificador interno de cada llamada. Nada de esto se puede cambiar desde la app.
- **D16:** sin región fija, la app puede quedar lejos de Neon (se vio `us-central` en GCP). Fijar `us-east` fija la zona pero no el proveedor (se vieron AWS y Azure). Modal también permite fijar el proveedor (`cloud="aws"`); su efecto en el costo no se verificó.
- **D17:** un contenedor pequeño ya tarda de 3,6 a 5,8 s en arrancar en frío. Keycloak tardará bastante más (la guía estima de 20 a 40 s), lo que respalda el modo demo.

## Evidencia

Los comandos se corrieron desde la raíz del repo. Los de Modal llevan `--env-file .env` para usar el workspace de krtr (regla 7 de la guía).

### Despliegue

```console
$ uv run --env-file .env modal deploy krtr_probe.py
✓ Created objects.
└── 🔨 Created web function probe => https://juan-alvarezo-2002--krtr-probe.modal.run
✓ App deployed in 4.462s! 🎉
View Deployment: https://modal.com/apps/juan-alvarezo-2002/main/deployed/krtr-probe
```

### (a) IP del cliente

```console
$ curl -s https://checkip.amazonaws.com
<IP pública>

$ curl -s https://juan-alvarezo-2002--krtr-probe.modal.run/a-plain | python3 -m json.tool
{
    "path": "a-plain",
    "scheme": "https",
    "client": ["<IP pública>", 54119],
    "headers": [
        ["host", "juan-alvarezo-2002--krtr-probe.modal.run"],
        ["user-agent", "curl/8.7.1"],
        ["accept", "*/*"],
        ["accept-encoding", "gzip"]
    ],
    "container_user": {"uid": 0, "name": "root"},
    "container_uptime_seconds": 0.381,
    "python": "3.13.3",
    "modal": {"MODAL_REGION": "us-east", "MODAL_CLOUD_PROVIDER": "CLOUD_PROVIDER_AWS"}
}

$ curl -s -H "X-Forwarded-For: 203.0.113.7" -H "X-Real-IP: 203.0.113.8" -H "Forwarded: for=203.0.113.9" \
    https://juan-alvarezo-2002--krtr-probe.modal.run/a-spoofed | python3 -m json.tool
{
    "path": "a-spoofed",
    "scheme": "https",
    "client": ["<IP pública>", 54124],
    "headers": [
        ["host", "juan-alvarezo-2002--krtr-probe.modal.run"],
        ["user-agent", "curl/8.7.1"],
        ["accept", "*/*"],
        ["forwarded", "for=203.0.113.9"],
        ["x-real-ip", "203.0.113.8"],
        ["accept-encoding", "gzip"]
    ],
    ...
}
```

El `X-Forwarded-For` enviado no llega al contenedor, `X-Real-IP` y `Forwarded` llegan intactos, y `client` sigue siendo la IP real.

### (b) Versiones de TLS

El cliente (OpenSSL 3.6.5) se configura con `@SECLEVEL=0` para que sí ofrezca TLS 1.0 y 1.1. Así, un rechazo viene del servidor y no del cliente.

```console
$ HOST=juan-alvarezo-2002--krtr-probe.modal.run
$ openssl s_client -connect "$HOST:443" -servername "$HOST" -tls1 -cipher 'DEFAULT:@SECLEVEL=0' </dev/null
...:error:0A00042E:SSL routines:ssl3_read_bytes:tlsv1 alert protocol version:...:SSL alert number 70
New, (NONE), Cipher is (NONE)
$ openssl s_client ... -tls1_1 ...
...:error:0A00042E:SSL routines:ssl3_read_bytes:tlsv1 alert protocol version:...:SSL alert number 70
New, (NONE), Cipher is (NONE)
$ openssl s_client ... -tls1_2 ...
New, TLSv1.2, Cipher is ECDHE-ECDSA-AES128-GCM-SHA256
$ openssl s_client ... -tls1_3 ...
New, TLSv1.3, Cipher is TLS_AES_128_GCM_SHA256
```

### (c) HTTP sin cifrar

```console
$ curl -sI http://juan-alvarezo-2002--krtr-probe.modal.run/c-http
HTTP/1.1 308 Permanent Redirect
Connection: close
Location: https://juan-alvarezo-2002--krtr-probe.modal.run/c-http
Server: Caddy
Date: Fri, 02 Oct 2026 04:02:37 GMT
```

### (d) Public Suffix List

```console
$ curl -s https://publicsuffix.org/list/public_suffix_list.dat | grep -n -i "modal"
4796:modalen.no
```

De 16.497 líneas, la única que contiene "modal" es `modalen.no`: `modal.run` no está en la lista.

### (e) Arranque en frío

La app usa `scaledown_window=2`: el contenedor se apaga 2 s después de quedar sin tráfico. Cada ronda espera 45 s, mide una petición en frío y otra en caliente. Una `container_uptime_seconds` baja confirma que respondió un contenedor recién creado. Los tiempos son de punta a punta desde la red del equipo, e incluyen el handshake TLS de cada `curl`.

```console
$ for round in 1 2 3; do sleep 45; curl -s -o cold.json -w "round $round cold: %{time_total}s, " "$URL/e-cold-$round"; ...; done
round 1 cold: 5.793276s, container uptime: 0.591 s
round 1 warm: 0.582039s
round 2 cold: 3.630805s, container uptime: 0.358 s
round 2 warm: 0.347561s
round 3 cold: 3.638661s, container uptime: 0.433 s
round 3 warm: 0.320932s
```

### (f) Cabeceras de respuesta y usuario del contenedor

```console
$ curl -s -D - -o /dev/null https://juan-alvarezo-2002--krtr-probe.modal.run/f-get
HTTP/2 200
alt-svc: h3=":443"; ma=2592000
content-type: application/json
date: Fri, 02 Oct 2026 04:05:59 GMT
modal-function-call-id: fc-01M3XCMJ6Y7T8E612THFC1JG25
vary: accept-encoding
content-length: 377
```

`content-type` y `content-length` los pone la app. No hay cabecera `Server`. Un `HEAD` (`curl -I`) devuelve 405, porque la app solo define `GET`, y trae las mismas cabeceras de Modal.

El usuario sale de `container_user` en la salida de (a): `{"uid": 0, "name": "root"}`.

### Regiones observadas

| Contenedor | `MODAL_REGION` | `MODAL_CLOUD_PROVIDER` |
|---|---|---|
| El de (a) | `us-east` | `CLOUD_PROVIDER_AWS` |
| El de la ronda 3 de (e) | `us-east` | `CLOUD_PROVIDER_AZURE` |
| Uno extra (`/region-1` a `/region-3`) | `us-central` | `CLOUD_PROVIDER_GCP` |

### Detención

```console
$ uv run --env-file .env modal app stop krtr-probe --yes
$ uv run --env-file .env modal app list
│ ap-lV6jrMhslX87tHFFbCLw45 │ krtr-probe │ stopped │ 0 │ ...
$ curl -s -o /dev/null -w "HTTP %{http_code}\n" https://juan-alvarezo-2002--krtr-probe.modal.run/after-stop
HTTP 404
```

Sin `--yes`, `modal app stop` pide confirmación y, fuera de una terminal interactiva, cancela sin detener nada.

## Anexo: código de `krtr-probe`

La app no forma parte del paquete `krtr`. Se desplegó desde un archivo temporal con `uv run --env-file .env modal deploy krtr_probe.py`.

```python
"""Temporary Modal app for task 0.4 of docs/guia-web-seguridad_modal.md."""

import os
import platform
import pwd
import time
from typing import Any

import modal
from fastapi import FastAPI, Request

# Set when the container imports this module, so a fresh (cold) container
# reports a near-zero uptime and a reused (warm) one a larger value.
CONTAINER_STARTED_AT = time.time()

# Only non-sensitive Modal variables are echoed: the endpoint is public.
ECHOED_MODAL_VARIABLES = ("MODAL_REGION", "MODAL_CLOUD_PROVIDER")

image = modal.Image.debian_slim(python_version="3.13").uv_pip_install("fastapi==0.142.2")
app = modal.App("krtr-probe")
web_app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@web_app.get("/{path:path}")
async def echo_request(path: str, request: Request) -> dict[str, Any]:
    """Returns what the container sees of the request and of itself."""
    user_id = os.getuid()
    return {
        "path": path,
        "scheme": request.url.scheme,
        "client": [request.client.host, request.client.port] if request.client else None,
        "headers": [
            [name.decode("latin-1"), value.decode("latin-1")]
            for name, value in request.headers.raw
        ],
        "container_user": {"uid": user_id, "name": pwd.getpwuid(user_id).pw_name},
        "container_uptime_seconds": round(time.time() - CONTAINER_STARTED_AT, 3),
        "python": platform.python_version(),
        "modal": {name: os.environ.get(name) for name in ECHOED_MODAL_VARIABLES},
    }


@app.function(image=image, scaledown_window=2)
@modal.asgi_app(label="krtr-probe")
def probe() -> FastAPI:
    """Serves the echo app at https://<workspace>--krtr-probe.modal.run."""
    return web_app
```
