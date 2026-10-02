#!/usr/bin/env bash
# Creates the Artifact Registry repo, the service accounts and the Secret
# Manager secrets for krtr (task 6.2 of docs/guia-web-seguridad.md).
#
# Prepared by Claude Code. A team member reviews it and runs it with an
# authenticated gcloud (`gcloud auth login`) against the project from task 1.2.
# It is idempotent: anything that already exists is left alone, and a secret
# that already has a version is never overwritten.
#
# Secret values are never passed as arguments (so they stay out of shell
# history and `ps`). They are generated with `openssl rand` or read from a
# hidden prompt, and sent to gcloud through stdin.
#
# Usage:
#   deploy/gcp/setup-registry-accounts-secrets.sh            # create everything
#   deploy/gcp/setup-registry-accounts-secrets.sh --verify   # only show secret IAM
#
# Optional environment overrides: PROJECT_ID, REGION.

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-krtr-hackathon}"
REGION="${REGION:-us-east4}"
REPOSITORY="krtr"

# Service accounts (one per workload, least privilege).
SA_WEB="krtr-web"            # Cloud Run service: FastAPI BFF + SPA.
SA_AUTH="krtr-auth"          # Cloud Run service: Keycloak.
SA_JOBS="krtr-jobs"          # Cloud Run jobs: purge-events, sync-auth-events.
SA_DEPLOYER="krtr-deployer"  # GitHub Actions (WIF is wired up in task 6.8).

# Secrets. Generated ones are random; manual ones are pasted from Neon (1.3).
SECRET_APP_DATABASE_URL="krtr-app-database-url"            # Neon app DB, pooled (role krtr_app).
SECRET_AUDIT_DATABASE_URL="krtr-audit-database-url"        # Neon keycloak DB (role krtr_audit_reader).
SECRET_KEYCLOAK_DB_PASSWORD="krtr-keycloak-db-password"    # Password of role krtr_keycloak.
SECRET_EVENTS_KEY="krtr-events-key"                        # KRTR_EVENTS_KEY, base64 32 bytes.
SECRET_TOKENS_KEY="krtr-tokens-key"                        # KRTR_TOKENS_KEY, base64 32 bytes.
SECRET_WEB_CLIENT_SECRET="krtr-web-oidc-client-secret"     # Keycloak client `krtr-web`.
SECRET_KEYCLOAK_ADMIN_PASSWORD="krtr-keycloak-admin-password"  # Keycloak bootstrap admin.
SECRET_IMPORTER_CLIENT_SECRET="krtr-importer-client-secret"    # Keycloak client `krtr-importer`.

ALL_SECRETS=(
  "$SECRET_APP_DATABASE_URL" "$SECRET_AUDIT_DATABASE_URL" "$SECRET_KEYCLOAK_DB_PASSWORD"
  "$SECRET_EVENTS_KEY" "$SECRET_TOKENS_KEY" "$SECRET_WEB_CLIENT_SECRET"
  "$SECRET_KEYCLOAK_ADMIN_PASSWORD" "$SECRET_IMPORTER_CLIENT_SECRET"
)

# Prints the service accounts allowed to read a secret. The admin password and
# the importer secret have no reader: only team members read them. A case
# statement instead of an associative array, so it runs on macOS's bash 3.2.
secret_readers() {
  case "$1" in
    "$SECRET_APP_DATABASE_URL")     echo "$SA_WEB $SA_JOBS" ;;
    "$SECRET_AUDIT_DATABASE_URL")   echo "$SA_JOBS" ;;
    "$SECRET_KEYCLOAK_DB_PASSWORD") echo "$SA_AUTH" ;;
    "$SECRET_EVENTS_KEY")           echo "$SA_WEB $SA_JOBS" ;;
    "$SECRET_TOKENS_KEY")           echo "$SA_WEB" ;;
    # krtr-auth reads it too, so the realm import (3.2) can set the client secret.
    "$SECRET_WEB_CLIENT_SECRET")    echo "$SA_WEB $SA_AUTH" ;;
    *)                              echo "" ;;
  esac
}

# How each secret's first value is produced.
GENERATED_AES_KEYS=("$SECRET_EVENTS_KEY" "$SECRET_TOKENS_KEY")
GENERATED_PASSWORDS=("$SECRET_WEB_CLIENT_SECRET" "$SECRET_KEYCLOAK_ADMIN_PASSWORD" "$SECRET_IMPORTER_CLIENT_SECRET")
MANUAL_SECRETS=("$SECRET_APP_DATABASE_URL" "$SECRET_AUDIT_DATABASE_URL" "$SECRET_KEYCLOAK_DB_PASSWORD")

log() { printf '[6.2] %s\n' "$*" >&2; }

service_account_email() { printf '%s@%s.iam.gserviceaccount.com' "$1" "$PROJECT_ID"; }

# Creates the Docker repository in Artifact Registry if it does not exist.
create_repository() {
  if gcloud artifacts repositories describe "$REPOSITORY" --location="$REGION" \
      --project="$PROJECT_ID" >/dev/null 2>&1; then
    log "Artifact Registry repo '$REPOSITORY' already exists in $REGION"
    return
  fi
  log "Creating Artifact Registry repo '$REPOSITORY' in $REGION"
  gcloud artifacts repositories create "$REPOSITORY" --project="$PROJECT_ID" \
    --location="$REGION" --repository-format=docker \
    --description="krtr container images"
}

# Creates one service account if it does not exist.
create_service_account() {
  local name="$1" display_name="$2"
  if gcloud iam service-accounts describe "$(service_account_email "$name")" \
      --project="$PROJECT_ID" >/dev/null 2>&1; then
    log "Service account '$name' already exists"
    return
  fi
  log "Creating service account '$name'"
  gcloud iam service-accounts create "$name" --project="$PROJECT_ID" \
    --display-name="$display_name"
}

create_service_accounts() {
  create_service_account "$SA_WEB" "krtr-web (Cloud Run service)"
  create_service_account "$SA_AUTH" "krtr-auth (Keycloak on Cloud Run)"
  create_service_account "$SA_JOBS" "krtr-jobs (Cloud Run jobs)"
  create_service_account "$SA_DEPLOYER" "krtr-deployer (GitHub Actions)"
}

# Grants the deployer only what `gcloud run deploy` and an image push need:
# deploy Cloud Run, push to the krtr repo, and act as the runtime accounts.
grant_deployer_roles() {
  local deployer
  deployer="serviceAccount:$(service_account_email "$SA_DEPLOYER")"
  log "Granting roles/run.developer on the project to $SA_DEPLOYER"
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="$deployer" \
    --role="roles/run.developer" --condition=None >/dev/null
  log "Granting roles/artifactregistry.writer on repo '$REPOSITORY' to $SA_DEPLOYER"
  gcloud artifacts repositories add-iam-policy-binding "$REPOSITORY" \
    --project="$PROJECT_ID" --location="$REGION" --member="$deployer" \
    --role="roles/artifactregistry.writer" >/dev/null
  local runtime
  for runtime in "$SA_WEB" "$SA_JOBS" "$SA_AUTH"; do
    log "Allowing $SA_DEPLOYER to deploy as $runtime (roles/iam.serviceAccountUser)"
    gcloud iam service-accounts add-iam-policy-binding "$(service_account_email "$runtime")" \
      --project="$PROJECT_ID" --member="$deployer" \
      --role="roles/iam.serviceAccountUser" >/dev/null
  done
}

# Lets the runtime accounts pull images from the krtr repo.
grant_image_readers() {
  local runtime
  for runtime in "$SA_WEB" "$SA_AUTH" "$SA_JOBS"; do
    log "Granting roles/artifactregistry.reader on repo '$REPOSITORY' to $runtime"
    gcloud artifacts repositories add-iam-policy-binding "$REPOSITORY" \
      --project="$PROJECT_ID" --location="$REGION" \
      --member="serviceAccount:$(service_account_email "$runtime")" \
      --role="roles/artifactregistry.reader" >/dev/null
  done
}

# Creates an empty secret (no versions) if it does not exist.
create_secret() {
  local name="$1"
  if gcloud secrets describe "$name" --project="$PROJECT_ID" >/dev/null 2>&1; then
    log "Secret '$name' already exists"
    return
  fi
  log "Creating secret '$name'"
  gcloud secrets create "$name" --project="$PROJECT_ID" --replication-policy=automatic \
    --labels=app=krtr >/dev/null
}

secret_has_version() {
  [[ -n "$(gcloud secrets versions list "$1" --project="$PROJECT_ID" \
    --filter='state=ENABLED' --limit=1 --format='value(name)')" ]]
}

# Reads stdin and stores it as a new version of the secret.
add_secret_version_from_stdin() {
  gcloud secrets versions add "$1" --project="$PROJECT_ID" --data-file=- >/dev/null
}

# Gives a secret its first value, unless it already has one.
populate_secret() {
  local name="$1" source="$2"
  if secret_has_version "$name"; then
    log "Secret '$name' already has a value; leaving it unchanged"
    return
  fi
  case "$source" in
    aes-key)  log "Generating a random AES-256 key for '$name'"
              openssl rand -base64 32 | tr -d '\n' | add_secret_version_from_stdin "$name" ;;
    password) log "Generating a random password for '$name'"
              openssl rand -base64 33 | tr -d '\n/+=' | add_secret_version_from_stdin "$name" ;;
    manual)   populate_secret_from_prompt "$name" ;;
  esac
}

# Asks for a value with a hidden prompt; an empty answer skips it for later.
populate_secret_from_prompt() {
  local name="$1" value
  read -r -s -p "Value for '$name' (input hidden, empty to skip): " value
  printf '\n' >&2
  if [[ -z "$value" ]]; then
    log "Skipped '$name'; add it later with: gcloud secrets versions add $name --data-file=-"
    return
  fi
  printf '%s' "$value" | add_secret_version_from_stdin "$name"
  log "Stored a value for '$name'"
}

create_and_populate_secrets() {
  local name
  for name in "${GENERATED_AES_KEYS[@]}"; do create_secret "$name"; populate_secret "$name" aes-key; done
  for name in "${GENERATED_PASSWORDS[@]}"; do create_secret "$name"; populate_secret "$name" password; done
  for name in "${MANUAL_SECRETS[@]}"; do create_secret "$name"; populate_secret "$name" manual; done
}

# Grants roles/secretmanager.secretAccessor on each secret only to its readers.
grant_secret_readers() {
  local name reader
  for name in "${ALL_SECRETS[@]}"; do
    for reader in $(secret_readers "$name"); do
      log "Granting secretAccessor on '$name' to $reader"
      gcloud secrets add-iam-policy-binding "$name" --project="$PROJECT_ID" \
        --member="serviceAccount:$(service_account_email "$reader")" \
        --role="roles/secretmanager.secretAccessor" >/dev/null
    done
  done
}

# Prints each secret's IAM policy (the 6.2 verification step).
verify_secret_access() {
  local name readers
  for name in "${ALL_SECRETS[@]}"; do
    readers="$(secret_readers "$name")"
    log "IAM policy of '$name' (expected readers: ${readers:-none})"
    gcloud secrets get-iam-policy "$name" --project="$PROJECT_ID" \
      --format='table(bindings.role, bindings.members.flatten())'
  done
}

main() {
  if [[ "${1:-}" == "--verify" ]]; then
    verify_secret_access
    return
  fi
  log "Project: $PROJECT_ID · Region: $REGION"
  gcloud config set project "$PROJECT_ID" >/dev/null
  create_repository
  create_service_accounts
  grant_deployer_roles
  grant_image_readers
  create_and_populate_secrets
  grant_secret_readers
  verify_secret_access
  log "Done. Docker push target: $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/krtr-web"
}

main "$@"
