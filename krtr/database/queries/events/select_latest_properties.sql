-- Reads the stored `properties` of the most recent events, exactly as they
-- sit in the database (AES-256-GCM nonce + ciphertext), without decrypting
-- them. Exists for the production security suite (task 7.2 of
-- docs/guia-web-seguridad_modal.md), which checks that the column holds
-- ciphertext and never readable JSON.
-- Consumed by e2e/security/test_encryption_at_rest.py.
SELECT
    properties
FROM events
ORDER BY occurred_at DESC
LIMIT %(limit)s
