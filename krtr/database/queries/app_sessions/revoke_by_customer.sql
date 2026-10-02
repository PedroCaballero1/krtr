-- Revokes every non-revoked session belonging to a `customer_id`, used on
-- a new login to enforce "1 session per user" (G15): the previous session
-- is revoked before the new one is created.
-- Consumed by krtr.back.security.oidc's callback handler, right before it
-- creates the new session row.
UPDATE app_sessions
SET revoked_at = %(revoked_at)s
WHERE customer_id = %(customer_id)s
  AND revoked_at IS NULL
