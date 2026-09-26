-- Schema for the `products` dimension table: one row per financial product
-- (account, card, loan, ...) held by a customer.
-- Assumes `customers` and `branches` already exist: `products` references
-- both by foreign key but this repository does not create them.
-- Consumed by krtr.database.neon.products.schema.create_products_schema.
CREATE TABLE IF NOT EXISTS products (
    product_id VARCHAR(20) PRIMARY KEY,                        -- Unique product ID.
    customer_id VARCHAR(20) NOT NULL REFERENCES customers (customer_id),  -- Owner customer ID.
    product_type VARCHAR(50) NOT NULL,                         -- Product type (Checking Account, Savings Account, Credit Card, Debit Card, Personal Loan, Mortgage, Investment, ...).
    product_number VARCHAR(30) NOT NULL UNIQUE,                -- Account/card/policy number.
    currency VARCHAR(3) NOT NULL,                              -- Currency (MXN, COP, ARS, USD).
    current_balance DECIMAL(15, 2) NOT NULL,                   -- Current balance.
    credit_limit DECIMAL(15, 2),                               -- Credit limit (for credit products).
    interest_rate DECIMAL(5, 2),                               -- Annual interest rate (%).
    opening_date DATE NOT NULL,                                -- Product opening date.
    expiration_date DATE,                                      -- Expiration date (for term products).
    opening_branch_id VARCHAR(20) NOT NULL REFERENCES branches (branch_id),  -- Branch where opened.
    product_status VARCHAR(20) NOT NULL,                       -- Status (Active, Blocked, Closed, Suspended).
    opening_channel VARCHAR(30) NOT NULL,                      -- Opening channel (Branch, Web, App, Call Center).
    has_linked_app BOOLEAN NOT NULL,                           -- Whether the product is linked to the mobile app.
    days_past_due INTEGER,                                     -- Days past due (for credits).
    last_transaction_date TIMESTAMP,                           -- Last transaction date.
    last_updated TIMESTAMP NOT NULL                            -- Last record update.
);
