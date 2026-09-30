-- Extends a session's idle timeout by updating `last_activity_at`, called
-- from POST /api/session/activity whenever the frontend reports user
-- activity (mouse, keyboard, touch, scroll), at most every 60 seconds.
-- Does not touch `absolute_expires_at`: activity extends idle time but
-- never the 30-minute absolute cutoff (G15).
-- Consumed by krtr.back.security.sessions's activity handler.
UPDATE app_sessions
SET last_activity_at = %(last_activity_at)s
WHERE session_id_hash = %(session_id_hash)s
  AND revoked_at IS NULL
