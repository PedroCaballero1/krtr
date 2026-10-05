-- Retention purge for the `events` table (§3.5 of docs/guia-web-seguridad_modal.md):
-- events older than 3 months are deleted. Run daily by the `purge_events`
-- Modal cron, or by hand with `krtr back security purge-events`.
-- Consumed by krtr.back.security.audit's purge job.
DELETE FROM events
WHERE occurred_at < now() - interval '3 months';
