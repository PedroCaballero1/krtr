-- Retention purge for the `messages` table (§3.6 of
-- docs/guia-web-seguridad_modal.md): messages older than 3 months are
-- deleted, the same retention as `events`. Run daily by the `purge_events`
-- Modal cron (task 6.5), next to events/purge.sql.
-- Consumed by krtr.back.ia.messages.store.NeonMessageStore.purge_expired.
DELETE FROM messages
WHERE sent_at < now() - interval '3 months';
