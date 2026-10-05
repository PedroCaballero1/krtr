-- Inserts one server-side session when a customer logs in (task 4.4 of
-- docs/guia-web-seguridad_modal.md). Takes named parameters, so the
-- session service can run it through NeonClient.execute_params; the batch
-- template in query.sql stays for bulk loads. A new session is never
-- revoked, so revoked_at starts NULL.
-- Consumed by krtr.back.security.sessions.store.
INSERT INTO app_sessions (
    session_id_hash,
    customer_id,
    tokens_ciphertext,
    created_at,
    last_activity_at,
    absolute_expires_at,
    revoked_at
) VALUES (
    %(session_id_hash)s,
    %(customer_id)s,
    %(tokens_ciphertext)s,
    %(created_at)s,
    %(last_activity_at)s,
    %(absolute_expires_at)s,
    NULL
)
