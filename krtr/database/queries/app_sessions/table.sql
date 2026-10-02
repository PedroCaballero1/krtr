-- Schema for the `app_sessions` table: server-side sessions for the krtr
-- BFF (D1 of docs/guia-web-seguridad.md). Lets the backend enforce the
-- idle/absolute session timeouts and the "1 session per customer_id" rule
-- (G15) from any Cloud Run instance, since the session state lives in the
-- database rather than in-process.
-- No indexes beyond the primary key: the CLAUDE.md rule against creating
-- indexes unless the user explicitly asks for them applies here.
-- Consumed by krtr.back.security.sessions (create, touch activity,
-- validate, revoke) and krtr.back.security.oidc (reads tokens_ciphertext).
CREATE TABLE IF NOT EXISTS app_sessions (
    session_id_hash VARCHAR(64) PRIMARY KEY,  -- SHA-256 hex digest of the random session token stored in the `__Host-krtr_session` cookie. Only the hash is stored; the raw token never touches the database.
    customer_id VARCHAR(20) NOT NULL,         -- The customer this session belongs to. Used to enforce "1 session per customer_id" by revoking any other non-revoked session for the same customer_id on a new login.
    tokens_ciphertext BYTEA NOT NULL,         -- AES-256-GCM ciphertext (nonce + ciphertext) of the OIDC tokens (access, refresh, id) issued by Keycloak for this session. Never stored in plaintext.
    created_at TIMESTAMPTZ NOT NULL,          -- When the session was created (login time), in UTC.
    last_activity_at TIMESTAMPTZ NOT NULL,    -- Last time the user was active, in UTC. Drives the 5-minute idle timeout.
    absolute_expires_at TIMESTAMPTZ NOT NULL, -- Hard cutoff for this session (created_at + 30 minutes), in UTC. Enforced even if the user stays active.
    revoked_at TIMESTAMPTZ                    -- When the session was revoked (logout, a newer login for the same customer_id, or an expiry job), in UTC. NULL while the session is still valid.
);
