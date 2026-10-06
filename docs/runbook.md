# Runbook de krtr-web en Modal

_Tarea 8.1 de [`guia-web-seguridad_modal.md`](guia-web-seguridad_modal.md) · 5-oct-2026_

Procedimientos para operar la página en producción. El contrato de la API está en [`api.md`](api.md) y el comportamiento de la plataforma en [`modal-platform.md`](modal-platform.md).

| | |
|---|---|
| App | https://juan-alvarezo-2002--krtr.modal.run |
| Keycloak | https://juan-alvarezo-2002--krtr-auth.modal.run |
| Workspace / entorno de Modal | `juan-alvarezo-2002` / `main` |
| App de Modal | `krtr-web`: funciones `web`, `auth`, `auth_import` y `purge_events` (cron diario a las 03:00 COT) |
| Secretos de Modal | `krtr-web`, `krtr-auth`, `krtr-jobs` |
| Base de datos | Neon, proyecto "Hackathon", rama `production` (bases `neondb` y `keycloak`) |

## Reglas

1. **Los comandos de Modal se corren desde la raíz del repo, donde está el `.env`, como `uv run --env-file .env modal …`.** El CLI `modal` no lee `.env`: sin `--env-file` usa el perfil activo de `~/.modal.toml`, que es otro workspace. Hace falta el extra: `uv sync --extra modal`.
2. **No se despliega a mano.** Se despliega haciendo merge a `master` o corriendo el workflow `Deploy` (ver §1). Si alguna vez fuera imprescindible desplegar a mano, el único comando válido es el de la §1.4.
3. **Cada despliegue reinicia Keycloak:** el login no funciona durante unos 30 s (hasta 3 min). No se despliega durante la evaluación del jurado.
4. **Nunca se imprimen** valores del `.env`, de los secretos de Modal ni de `data/credentials/`. Los comandos de este documento los usan sin mostrarlos.

## 1. Desplegar

### 1.1 Camino normal: merge a `master`

1. Abrir un PR contra `master`. El workflow `CI` corre los jobs `lint-and-test` y `security`.
2. Hacer el merge con los dos jobs en verde.
3. El push a `master` vuelve a correr `CI`. Si termina en verde, arranca solo el workflow `Deploy` (`.github/workflows/deploy.yml`), que:
   - compila el frontend, instala con `uv sync --locked --extra modal` y corre `modal deploy -m krtr.back.deploy.app` sobre el mismo commit que probó el CI;
   - toma `KRTR_WARM` de la variable del repositorio (si no existe, usa `true`);
   - hace un smoke test que espera hasta 10 min a que `/healthz` y el `.well-known` de Keycloak respondan 200, y comprueba que `/admin/` dé 404.
4. En paralelo, el workflow `Release` (semantic-release) sube la versión y crea la etiqueta `vX.Y.Z` si hay commits `feat` o `fix`. Su commit `chore(release)` lo hace el bot de GitHub Actions, así que no dispara otro CI ni otro despliegue.

### 1.2 Volver a desplegar sin cambiar el código

En GitHub: **Actions → Deploy → Run workflow** (rama `master`). Sirve, por ejemplo, para aplicar un cambio de `KRTR_WARM` (§2).

### 1.3 Comprobar un despliegue

```bash
# La versión nueva aparece arriba, con el commit desplegado (un * indica cambios sin commit)
uv run --env-file .env modal app history krtr-web

# Los mismos checks del smoke test
curl -s -o /dev/null -w "%{http_code}\n" https://juan-alvarezo-2002--krtr.modal.run/healthz
curl -s -o /dev/null -w "%{http_code}\n" https://juan-alvarezo-2002--krtr-auth.modal.run/realms/krtr/.well-known/openid-configuration
curl -s -o /dev/null -w "%{http_code}\n" https://juan-alvarezo-2002--krtr-auth.modal.run/admin/   # 404

# Las pruebas de seguridad contra producción (usan las cuentas QA de data/credentials/)
uv run pytest e2e/security
```

Los logs de la app: `uv run --env-file .env modal app logs krtr-web`.

### 1.4 Despliegue a mano (solo en emergencias)

Solo si GitHub Actions no está disponible. Hay que hacerlo desde un árbol limpio en `master` y **como módulo** (`-m`): por ruta de archivo, la imagen no encuentra el módulo y los contenedores no arrancan.

```bash
git status --short                       # tiene que salir vacío
npm --prefix krtr/front run build        # la imagen de `web` copia krtr/front/dist
KRTR_WARM=true uv run --env-file .env modal deploy -m krtr.back.deploy.app
```

### 1.5 Volver a una versión anterior

- **Camino normal:** `git revert` del commit que falla, PR y merge. El CI despliega la versión corregida.
- **Emergencia:** `uv run --env-file .env modal app rollback krtr-web v<N>`, con `<N>` sacado de `modal app history krtr-web`. Vuelve a desplegar esa versión tal como estaba, incluido su modo demo. Después, `master` tiene que quedar igual a esa versión: si no, el siguiente merge vuelve a desplegar el código que fallaba.

## 2. Modo demo (D17)

Con `KRTR_WARM=true`, `web` y `auth` tienen siempre un contenedor encendido (`min_containers=1`). Con `false`, se apagan cuando no hay tráfico: la página arranca en unos 6 s y Keycloak en unos 30 s o más. El modo demo cuesta unos **3,15 USD al día** (§8 de la guía); llevar el registro del gasto en [`modal-platform.md`](modal-platform.md#registro-de-gasto-diario).

El valor se fija **al desplegar**. Para cambiarlo:

1. En GitHub: **Settings → Secrets and variables → Actions → Variables**, crear o editar `KRTR_WARM` con `true` o `false`. Si la variable no existe, el workflow usa `true`.
2. Correr **Actions → Deploy → Run workflow** (§1.2). Reinicia Keycloak.
3. Comprobar:

   ```bash
   uv run --env-file .env modal container list
   ```

   Con el modo demo encendido aparecen 2 contenedores de `krtr-web`. Apagado, desaparecen a los pocos minutos sin tráfico.

**Encenderlo:** antes de mandarle las credenciales al jurado. **Apagarlo:** cuando termine la evaluación.

## 3. Rotar secretos

Los secretos de Modal se arman con `krtr back deploy push-secrets` a partir del `.env`, con una lista fija de variables por secreto. El comando no imprime valores y no tiene opción de rotar: **para rotar un valor, se cambia en el `.env` y se vuelve a publicar**. Un secreto nuevo solo llega a los contenedores con el siguiente despliegue.

```bash
uv run --env-file .env krtr back deploy push-secrets   # actualiza krtr-web, krtr-auth y krtr-jobs
uv run --env-file .env modal secret list               # comprobar que se actualizaron
# Luego desplegar: Actions → Deploy → Run workflow (§1.2)
```

Para generar una llave AES-256 nueva (32 bytes en base64), sin mostrarla en pantalla:

```bash
# Borrar antes del .env la línea de la llave que se va a cambiar; esto agrega la nueva al final
python3 -c 'import base64, secrets; print("KRTR_TOKENS_KEY=" + base64.b64encode(secrets.token_bytes(32)).decode())' >> .env
```

Qué pasa al rotar cada variable del `.env`:

| Variable | Secretos | Efecto y pasos extra |
|---|---|---|
| `KRTR_TOKENS_KEY` | `krtr-web` | Cierra todas las sesiones y los logins en curso: los tokens guardados y la cookie de login dejan de poder descifrarse. No hace falta nada más. |
| `KRTR_EVENTS_KEY` | `krtr-web`, `krtr-jobs` | Los eventos ya guardados quedan **ilegibles**: no existe una herramienta para volver a cifrarlos. Solo se rota si la llave se filtró. |
| `KRTR_MESSAGES_KEY` | `krtr-web`, `krtr-jobs` | Lo mismo con los mensajes del chat (tabla `messages`). Al retomar un caso no se ve la conversación anterior. |
| `KRTR_APP_DB_PASSWORD` | `krtr-web`, `krtr-jobs` | Antes, en Neon y con el rol dueño, `ALTER ROLE krtr_app PASSWORD '…'` en la rama `production`. |
| `KRTR_KEYCLOAK_DB_PASSWORD` | `krtr-auth` | Antes, `ALTER ROLE krtr_keycloak PASSWORD '…'` en Neon. Keycloak deja de conectarse hasta que se despliegue. |
| `KRTR_PROD_WEB_OIDC_CLIENT_SECRET` | `krtr-web`, `krtr-auth` | ⚠️ Keycloak guardó el secreto del cliente `krtr-web` al importar el realm, la primera vez, y no lo vuelve a leer del entorno. Si solo se cambia el `.env`, **el login se rompe**. Después de desplegar, hay que actualizarlo en Keycloak (abajo). |
| `KRTR_PROD_KEYCLOAK_ADMIN_PASSWORD` | `krtr-auth` | ⚠️ La contraseña del admin bootstrap solo se usa al crear el realm `master`: cambiar el secreto no cambia la del admin que ya existe. Si no se actualiza también en Keycloak (abajo), `kcadm.sh` y `auth_import` dejan de autenticarse. |

Las dos últimas se generan solas si faltan en el `.env`: `push-secrets` crea un valor nuevo cuando se borra (o se renombra) su línea.

Los pasos en Keycloak usan `kcadm.sh` dentro del contenedor `auth` (cómo entrar: §5). La sesión de `kcadm.sh` se abre con el usuario y la contraseña de admin que ya tiene el contenedor:

```bash
# Secreto del cliente, DESPUÉS de desplegar: el contenedor ya tiene el valor nuevo
uv run --env-file .env modal container exec --no-pty <id-auth> -- bash -c '
K=/opt/keycloak/bin/kcadm.sh
$K config credentials --server http://127.0.0.1:8081 --realm master \
  --user "$KC_BOOTSTRAP_ADMIN_USERNAME" --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" >/dev/null
CID=$($K get clients -r krtr -q clientId=krtr-web --fields id --format csv --noquotes)
$K update clients/$CID -r krtr -s "secret=$KRTR_WEB_OIDC_CLIENT_SECRET" && echo "client secret updated"'
```

Para la contraseña del admin, la nueva llega al contenedor por el secreto y la vieja (que se retira) entra como argumento. `modal container exec` no reenvía stdin, así que no se puede pasar por una tubería.

1. En el `.env`, renombrar la línea `KRTR_PROD_KEYCLOAK_ADMIN_PASSWORD=` a `KRTR_OLD_KEYCLOAK_ADMIN_PASSWORD=`, sin mostrarla: `sed -i '' 's/^KRTR_PROD_KEYCLOAK_ADMIN_PASSWORD=/KRTR_OLD_KEYCLOAK_ADMIN_PASSWORD=/' .env`.
2. `push-secrets`: genera la contraseña nueva en el `.env` y la publica. Después, desplegar (§1.2).
3. En el contenedor `auth` nuevo, entrar con la vieja y poner la nueva, que el contenedor ya tiene en `KC_BOOTSTRAP_ADMIN_PASSWORD`:

   ```bash
   uv run --env-file .env sh -c 'modal container exec --no-pty "$1" -- bash -c "
   K=/opt/keycloak/bin/kcadm.sh
   \$K config credentials --server http://127.0.0.1:8081 --realm master \
     --user \"\$KC_BOOTSTRAP_ADMIN_USERNAME\" --password \"$KRTR_OLD_KEYCLOAK_ADMIN_PASSWORD\" >/dev/null
   \$K set-password -r master --username \"\$KC_BOOTSTRAP_ADMIN_USERNAME\" \
     --new-password \"\$KC_BOOTSTRAP_ADMIN_PASSWORD\" && echo admin password updated"' _ <id-auth>
   ```

4. Borrar del `.env` la línea `KRTR_OLD_KEYCLOAK_ADMIN_PASSWORD=`.

> Estos dos procedimientos no se han probado en producción. El login de `kcadm.sh` por `modal container exec` sí se verificó (5-oct).

## 4. Volver a importar usuarios

La importación usa el `partialImport` de Keycloak con `ifResourceExists=SKIP` (D20). Es idempotente: **solo agrega los usuarios que faltan y nunca cambia la contraseña de uno que ya existe**. Si se regeneran las credenciales (`credentials generate --overwrite`), las contraseñas nuevas **no** llegan a las cuentas existentes y los CSV del jurado y de QA quedan mal. Para cambiar la contraseña de una cuenta existente, usar `kcadm.sh set-password` (§5).

El servicio `auth` tiene que estar apagado, porque `auth_import` arranca su propio Keycloak contra la misma base:

1. Apagar el modo demo: `KRTR_WARM=false` y correr `Deploy` (§2).
2. Esperar a que `uv run --env-file .env modal container list` no muestre el contenedor de `auth` (§5 explica cómo distinguirlo). Mientras dure la importación, no abrir `krtr-auth`: cualquier visita lo vuelve a encender.
3. Importar (unos 30 min para 150.000 usuarios):

   ```bash
   uv run --env-file .env krtr back security credentials import --remote
   ```

   Sube los JSON de `data/credentials/import/` al Volume `krtr-credentials-import`, ejecuta `auth_import` y vacía el Volume aunque falle. Termina con el resumen de usuarios agregados y omitidos. Si `auth` tiene contenedores, se niega; `--force` lo salta, pero no conviene usarlo.
4. Volver a encender el modo demo: `KRTR_WARM=true` y correr `Deploy`.

## 5. Desbloquear una cuenta (`kcadm.sh` vía `modal container exec`)

Tras 5 contraseñas incorrectas, Keycloak bloquea la cuenta 15 minutos y luego la desbloquea sola. Para desbloquearla antes:

1. **Encontrar el contenedor de `auth`.** `modal container list` muestra los contenedores de `krtr-web` sin decir de qué función son. El de `auth` es el que tiene `kcadm.sh`:

   ```bash
   uv run --env-file .env modal container list
   uv run --env-file .env modal container exec --no-pty <id> -- ls /opt/keycloak/bin/kcadm.sh
   ```

   Si `auth` no tiene contenedor (modo demo apagado), basta con abrir https://juan-alvarezo-2002--krtr-auth.modal.run/realms/krtr para que arranque.

2. **Ver el estado y desbloquear.** En Keycloak los usernames están en minúsculas: `CLI-ABC…` se busca como `cli-abc…`.

   ```bash
   uv run --env-file .env modal container exec --no-pty <id-auth> -- bash -c '
   USERNAME=cli-xxxxxxxxxxxx
   K=/opt/keycloak/bin/kcadm.sh
   $K config credentials --server http://127.0.0.1:8081 --realm master \
     --user "$KC_BOOTSTRAP_ADMIN_USERNAME" --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" >/dev/null
   ID=$($K get users -r krtr -q username=$USERNAME -q exact=true --fields id --format csv --noquotes)
   $K get attack-detection/brute-force/users/$ID -r krtr      # estado: numFailures, disabled
   $K delete attack-detection/brute-force/users/$ID -r krtr   # desbloquear
   $K get attack-detection/brute-force/users/$ID -r krtr      # numFailures vuelve a 0'
   ```

   `$K delete attack-detection/brute-force/users -r krtr` desbloquea **todas** las cuentas del realm.

> Verificado en producción el 5-oct: el login de `kcadm.sh`, la búsqueda del usuario y la lectura del estado (`GET`) con la cuenta `CLI-MFA000000001`. El `DELETE` es el endpoint estándar de Keycloak y no se ha corrido todavía en producción.

La misma sesión de `kcadm.sh` sirve para otras tareas de administración: `set-password`, quitar una acción obligatoria, desactivar un usuario (`update users/$ID -r krtr -s enabled=false`). La consola web de administración no está publicada (el gateway responde 404 en `/admin`).

## 6. Correr la purga a mano

`purge_events` borra los eventos y los mensajes del chat de más de 3 meses. Corre sola todos los días a las 03:00 COT (08:00 UTC). Para correrla ahora:

```bash
npm --prefix krtr/front run build   # solo si krtr/front/dist no existe: la imagen lo copia
uv run --env-file .env modal run -m krtr.back.deploy.app::purge_events
```

- `modal run` crea una copia temporal de la app, ejecuta solo `purge_events` con el secreto `krtr-jobs` y termina. La app desplegada no se toca.
- Al final muestra el resultado: `{"events": <borrados>, "messages": <borrados>}`.
- **No anteponer `KRTR_WARM=true`.** Encendería un contenedor de `web` y otro de `auth` en la copia temporal, es decir, un segundo Keycloak contra la base de producción.
- La sincronización de los eventos de Keycloak (`sync_auth_events`, D3) todavía no existe ni está programada.
