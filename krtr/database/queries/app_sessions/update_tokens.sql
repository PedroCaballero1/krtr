-- Replaces the encrypted OIDC tokens of a live session after the backend
-- refreshes them with Keycloak (task 4.4 of docs/guia-web-seguridad_modal.md),
-- so the access token never expires while the customer is active.
-- Revoked sessions are left untouched.
-- Consumed by krtr.back.security.sessions.store.
UPDATE app_sessions
SET tokens_ciphertext = %(tokens_ciphertext)s
WHERE session_id_hash = %(session_id_hash)s
  AND revoked_at IS NULL
