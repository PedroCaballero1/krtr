-- Revokes a single session by its `session_id_hash`, used by
-- POST /auth/logout and by the idle/absolute expiry checks.
-- Consumed by krtr.back.security.sessions's logout and expiry handlers.
UPDATE app_sessions
SET revoked_at = %(revoked_at)s
WHERE session_id_hash = %(session_id_hash)s
  AND revoked_at IS NULL
