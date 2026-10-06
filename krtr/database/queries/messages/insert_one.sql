-- Inserts one chat message or agent reply, as each turn happens. Takes
-- named parameters, so the store can run it through
-- NeonClient.execute_params; the batch template in query.sql stays for
-- bulk loads.
-- Consumed by krtr.back.ia.messages.store.NeonMessageStore.
INSERT INTO messages (
    message_id,
    incident_id,
    customer_id,
    sender,
    content,
    language,
    outcome,
    sent_at
) VALUES (
    %(message_id)s,
    %(incident_id)s,
    %(customer_id)s,
    %(sender)s,
    %(content)s,
    %(language)s,
    %(outcome)s,
    %(sent_at)s
)
