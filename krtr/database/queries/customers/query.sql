-- Bulk-insert template for the `customers` table, used with psycopg2's
-- execute_values (the VALUES placeholder is expanded to one group per row).
-- Column order must match the column order of `customers/table.sql`.
-- Do not write a literal percent-s in these comments: psycopg2 counts it as a placeholder.
INSERT INTO customers (
    customer_id,
    document_number,
    document_type,
    first_name,
    last_name,
    date_of_birth,
    gender,
    email,
    mobile_phone,
    landline_phone,
    address,
    city,
    state,
    country,
    postal_code,
    detected_accent,
    segment,
    credit_score,
    estimated_monthly_income,
    occupation,
    marital_status,
    education_level,
    registration_date,
    registration_branch_id,
    customer_status,
    last_updated
) VALUES %s
