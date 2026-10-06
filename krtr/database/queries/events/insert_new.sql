-- Bulk-insert template for the `events` table that skips rows whose id is already there, used
-- with psycopg2's execute_values like query.sql. The Keycloak event sync (D3, task 4.10) reuses
-- each Keycloak event's id as the row id, so copying the same event twice inserts it once.
-- Column order must match the column order of `events/table.sql`.
-- Do not write a literal percent-s in these comments: psycopg2 counts it as a placeholder.
-- Consumed by krtr.back.security.audit.keycloak_sync.sync_auth_events.
INSERT INTO events (
    id,
    event_name,
    properties,
    occurred_at
) VALUES %s
ON CONFLICT (id) DO NOTHING
