-- Bulk-insert template for the `transactions` table, used with psycopg2's
-- execute_values (the VALUES placeholder is expanded to one group per row).
-- Column order must match the column order of `transactions/table.sql`.
-- Do not write a literal percent-s in these comments: psycopg2 counts it as a placeholder.
INSERT INTO transactions (
    transaction_id,
    transaction_date,
    process_date,
    product_id,
    customer_id,
    transaction_type,
    transaction_category,
    amount,
    currency,
    amount_usd,
    channel,
    branch_id,
    merchant_name,
    merchant_category,
    transaction_country,
    transaction_city,
    transaction_status,
    response_code,
    is_fraud,
    fraud_score,
    latitude,
    longitude
) VALUES %s
