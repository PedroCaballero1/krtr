-- Looks up a single session by its `session_id_hash`, used on every
-- authenticated request to validate the `__Host-krtr_session` cookie
-- (GET /api/me, POST /api/session/activity and every CSRF-protected route).
-- Consumed by krtr.back.security.sessions's session-validation dependency.
SELECT
    session_id_hash,
    customer_id,
    tokens_ciphertext,
    created_at,
    last_activity_at,
    absolute_expires_at,
    revoked_at
FROM app_sessions
WHERE session_id_hash = %(session_id_hash)s
