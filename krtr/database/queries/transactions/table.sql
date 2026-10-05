-- Schema for the `transactions` fact table: one row per financial
-- transaction, partitioned daily by `process_date` in the source (1,097
-- daily files, 2023-06-17 to 2026-06-17).
-- Assumes `products`, `customers` and `branches` already exist:
-- `transactions` references all three by foreign key but this repository
-- does not create them.
-- Consumed by krtr.database.neon.schema.create_table_schema.
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id VARCHAR(30) PRIMARY KEY,                -- Unique transaction ID.
    transaction_date TIMESTAMP NOT NULL,                    -- Transaction date and time.
    process_date DATE NOT NULL,                             -- Process date (partition key).
    product_id VARCHAR(20) NOT NULL,                        -- Product ID.
    customer_id VARCHAR(20) NOT NULL,                       -- Customer ID.
    transaction_type VARCHAR(50) NOT NULL,                  -- Type (Deposit, Withdrawal, Transfer, Payment, Purchase, Adjustment).
    transaction_category VARCHAR(50),                       -- Category (Food, Transport, Services, Entertainment, Health, Other).
    amount DECIMAL(15, 2) NOT NULL,                         -- Transaction amount.
    currency VARCHAR(3) NOT NULL,                           -- Currency.
    amount_usd DECIMAL(15, 2),                              -- Amount converted to USD.
    channel VARCHAR(30) NOT NULL,                           -- Channel (ATM, Branch, Web, App, POS, Transfer).
    branch_id VARCHAR(20),                                  -- Branch ID (if applicable).
    merchant_name VARCHAR(150),                             -- Merchant name (for purchases).
    merchant_category VARCHAR(50),                          -- MCC merchant category.
    transaction_country VARCHAR(50) NOT NULL,               -- Country where the transaction occurred.
    transaction_city VARCHAR(100),                          -- City where the transaction occurred.
    transaction_status VARCHAR(20) NOT NULL,                -- Status (Approved, Declined, Pending, Reversed).
    response_code VARCHAR(10),                              -- System response code.
    is_fraud BOOLEAN NOT NULL,                              -- Marked as fraud.
    fraud_score DECIMAL(5, 2),                              -- Fraud risk score (0-100).
    latitude DECIMAL(10, 7),                                -- Transaction latitude.
    longitude DECIMAL(10, 7)                                -- Transaction longitude.
);
