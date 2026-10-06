-- Finds one complaint by its ID, only if it belongs to the given customer,
-- with what a status answer shows: when it was opened, its category and its
-- status. Filtering by complaint_id AND customer_id makes another
-- customer's complaint look exactly like one that does not exist.
-- complaint_id is the primary key, so the lookup needs no extra index.
-- Consumed by krtr.back.ia.deterministic.neon_readers.NeonComplaintsReader.
SELECT
    complaint_id,
    creation_date,
    category,
    status
FROM complaints
WHERE complaint_id = %(complaint_id)s
  AND customer_id = %(customer_id)s
