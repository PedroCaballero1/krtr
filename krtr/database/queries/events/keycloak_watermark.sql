-- The mark the Keycloak event sync (D3, task 4.10) resumes from: the time of the latest Keycloak
-- event already copied into `events`, recognized by its event-name prefix (auth_keycloak_*), so
-- the app's own auth_* events never move it. NULL until the first sync copies something.
-- Consumed by krtr.back.security.audit.keycloak_sync.sync_auth_events.
SELECT max(occurred_at)
FROM events
WHERE starts_with(event_name, %(event_name_prefix)s)
