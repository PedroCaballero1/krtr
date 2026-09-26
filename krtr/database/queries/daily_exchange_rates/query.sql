-- Bulk-insert template for the `daily_exchange_rates` table, used with psycopg2's
-- execute_values (the VALUES placeholder is expanded to one group per row).
-- Column order must match the column order of `daily_exchange_rates/table.sql`.
-- Do not write a literal percent-s in these comments: psycopg2 counts it as a placeholder.
INSERT INTO daily_exchange_rates (
    date,
    source_currency,
    target_currency,
    exchange_rate,
    buy_rate,
    sell_rate,
    source
) VALUES %s
