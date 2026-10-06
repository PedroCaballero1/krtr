-- Reads Keycloak's own login events (D3, task 4.10 of docs/guia-web-seguridad_modal.md) from
-- `event_entity` in the `keycloak` database, which Keycloak creates and owns: krtr never writes
-- to it and has no table.sql for it. Runs as krtr_audit_reader, whose only grant there is SELECT
-- on this table (never on `credential`, which holds the password hashes).
-- `event_time` is epoch milliseconds. Keycloak 26 keeps the details in `details_json_long_value`
-- and leaves `details_json` for older rows, so both are read as one.
-- Consumed by krtr.back.security.audit.keycloak_sync.sync_auth_events.
SELECT
    id,
    type,
    event_time,
    realm_id,
    client_id,
    user_id,
    session_id,
    ip_address,
    error,
    COALESCE(details_json_long_value, details_json) AS details_json
FROM event_entity
WHERE event_time >= %(since_epoch_ms)s
ORDER BY event_time
