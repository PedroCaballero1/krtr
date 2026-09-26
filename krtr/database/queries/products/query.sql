-- Bulk-insert template for the `products` table, used with psycopg2's
-- execute_values (the VALUES placeholder is expanded to one group per row).
-- Column order must match the column order of `products/table.sql`.
-- Do not write a literal percent-s in these comments: psycopg2 counts it as a placeholder.
INSERT INTO products (
    product_id,
    customer_id,
    product_type,
    product_number,
    currency,
    current_balance,
    credit_limit,
    interest_rate,
    opening_date,
    expiration_date,
    opening_branch_id,
    product_status,
    opening_channel,
    has_linked_app,
    days_past_due,
    last_transaction_date,
    last_updated
) VALUES %s
