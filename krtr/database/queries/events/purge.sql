-- Retention purge for the `events` table (§3.5 of docs/guia-web-seguridad.md):
-- events older than 3 months are deleted. Run daily by the
-- `krtr back security purge-events` job (Cloud Scheduler, see the guide's §6.9).
-- Consumed by krtr.back.security.audit's purge job.
DELETE FROM events
WHERE occurred_at < now() - interval '3 months';
