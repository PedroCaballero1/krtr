-- Schema for the `customers` dimension table: one row per customer, the root
-- entity `products` and `branches` reference by foreign key.
-- Consumed by krtr.database.neon.schema.create_table_schema.
CREATE TABLE IF NOT EXISTS customers (
    customer_id VARCHAR(20) PRIMARY KEY,                  -- Unique customer ID.
    document_number VARCHAR(20) NOT NULL UNIQUE,           -- Identity document number.
    document_type VARCHAR(10) NOT NULL,                    -- Document type (DNI, CURP, CC, CE, Passport).
    first_name VARCHAR(100) NOT NULL,                      -- Customer first name (in Spanish).
    last_name VARCHAR(100) NOT NULL,                       -- Customer last name (in Spanish).
    date_of_birth DATE NOT NULL,                           -- Date of birth.
    gender VARCHAR(1),                                     -- Gender (M, F, O).
    email VARCHAR(100),                                    -- Email address.
    mobile_phone VARCHAR(20),                              -- Mobile phone number.
    landline_phone VARCHAR(20),                            -- Landline phone number.
    address VARCHAR(200),                                  -- Full address (in Spanish).
    city VARCHAR(100) NOT NULL,                            -- City of residence.
    state VARCHAR(100) NOT NULL,                           -- State/Province.
    country VARCHAR(50) NOT NULL,                          -- Country (Mexico, Colombia, Argentina).
    postal_code VARCHAR(10),                                -- Postal code.
    detected_accent VARCHAR(50),                            -- Spanish accent detected (mexican, colombian, argentine, neutral).
    segment VARCHAR(50) NOT NULL,                           -- Customer segment (Premium, Plus, Basic, Student).
    credit_score INTEGER,                                   -- Credit score (300-850).
    estimated_monthly_income DECIMAL(12, 2),                -- Estimated monthly income in local currency.
    occupation VARCHAR(100),                                -- Customer occupation.
    marital_status VARCHAR(20),                             -- Marital status.
    education_level VARCHAR(50),                            -- Education level.
    registration_date TIMESTAMP NOT NULL,                   -- Registration date as customer.
    registration_branch_id VARCHAR(20) NOT NULL,            -- Branch ID where registered.
    customer_status VARCHAR(20) NOT NULL,                   -- Status (Active, Inactive, Suspended, Closed).
    last_updated TIMESTAMP NOT NULL                         -- Last record update.
);
