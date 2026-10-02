-- Bulk-insert template for the `events` table, used with psycopg2's
-- execute_values (the VALUES placeholder is expanded to one group per row).
-- Column order must match the column order of `events/table.sql`.
-- Do not write a literal percent-s in these comments: psycopg2 counts it as a placeholder.
INSERT INTO events (
    id,
    event_name,
    properties,
    occurred_at
) VALUES %s
