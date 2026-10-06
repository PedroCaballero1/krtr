-- Lists one case's messages, oldest first, to resume or review the
-- conversation (G17). Filters by incident_id AND customer_id, so a customer
-- can never read another customer's case, even knowing its ID; the index
-- of table.sql serves exactly this filter. The message_id tie-break keeps
-- the order stable when two messages share a timestamp.
-- Consumed by krtr.back.ia.messages.store.NeonMessageStore.
SELECT
    message_id,
    incident_id,
    customer_id,
    sender,
    content,
    language,
    outcome,
    sent_at
FROM messages
WHERE incident_id = %(incident_id)s
  AND customer_id = %(customer_id)s
ORDER BY sent_at, message_id
