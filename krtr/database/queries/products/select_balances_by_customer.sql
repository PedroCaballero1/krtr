-- Lists one customer's products of one type, with what a balance answer
-- shows: the number, the currency, the balance and, for credit products,
-- the limit. Closed products are left out, since their balance answers no
-- current question. Always filtered by customer_id, which comes from the
-- session, so a customer can never read another customer's products.
-- product_type is the label as stored (e.g. 'Cuenta Ahorro'); the reader
-- maps it from the ProductType the chat engine asks for.
-- Consumed by krtr.back.ia.deterministic.neon_readers.NeonProductsReader.
SELECT
    product_number,
    currency,
    current_balance,
    credit_limit
FROM products
WHERE customer_id = %(customer_id)s
  AND product_type = %(product_type)s
  AND product_status <> 'Closed'
ORDER BY opening_date, product_id
