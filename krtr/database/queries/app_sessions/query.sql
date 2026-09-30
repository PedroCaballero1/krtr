-- Bulk-insert template for the `app_sessions` table, used with psycopg2's
-- execute_values (the VALUES placeholder is expanded to one group per row).
-- Column order must match the column order of `app_sessions/table.sql`.
-- Do not write a literal percent-s in these comments: psycopg2 counts it as a placeholder.
INSERT INTO app_sessions (
    session_id_hash,
    customer_id,
    tokens_ciphertext,
    created_at,
    last_activity_at,
    absolute_expires_at,
    revoked_at
) VALUES %s
