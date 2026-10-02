-- Inserts a single event row, used by EventRecorder.record_event for
-- real-time writes (one event per call from a request handler), as opposed
-- to query.sql's bulk-load template (used for batch backfills, e.g. the
-- Keycloak auth-event sync job, task 4.10).
-- Consumed by krtr.back.security.audit.recorder.EventRecorder.
INSERT INTO events (
    id,
    event_name,
    properties,
    occurred_at
) VALUES (
    %(id)s,
    %(event_name)s,
    %(properties)s,
    %(occurred_at)s
)
