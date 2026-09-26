-- Schema for the `daily_exchange_rates` table: one row per day and currency pair, with the
-- exchange rate and the bank's buy and sell rates for that pair on that day.
-- Its primary key is (date, source_currency, target_currency), so a pair appears once per day.
-- Consumed by `krtr database neon create-schema daily_exchange_rates`.
CREATE TABLE IF NOT EXISTS daily_exchange_rates (
    date DATE NOT NULL,                       -- Exchange rate date.
    source_currency VARCHAR(3) NOT NULL,      -- Source currency.
    target_currency VARCHAR(3) NOT NULL,      -- Target currency.
    exchange_rate DECIMAL(12, 6) NOT NULL,    -- Exchange rate.
    buy_rate DECIMAL(12, 6),                  -- Bank buy rate.
    sell_rate DECIMAL(12, 6),                 -- Bank sell rate.
    source VARCHAR(50),                       -- Exchange rate source.
    PRIMARY KEY (date, source_currency, target_currency)
);
