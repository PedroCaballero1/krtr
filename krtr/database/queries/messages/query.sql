-- Bulk-insert template for the `messages` table, used with psycopg2's
-- execute_values (the VALUES placeholder is expanded to one group per row),
-- e.g. for backfills. Column order must match the column order of
-- `messages/table.sql`.
-- Do not write a literal percent-s in these comments: psycopg2 counts it as a placeholder.
INSERT INTO messages (
    message_id,
    incident_id,
    customer_id,
    sender,
    content,
    language,
    outcome,
    sent_at
) VALUES %s
