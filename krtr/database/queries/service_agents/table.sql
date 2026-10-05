-- Schema for the `service_agents` dimension table: one row per customer
-- service agent, snapshotted monthly.
-- Assumes `branches` already exists: `service_agents` references it by
-- foreign key but this repository does not create it.
-- Consumed by krtr.database.neon.schema.create_table_schema.
CREATE TABLE IF NOT EXISTS service_agents (
    agent_id VARCHAR(20) PRIMARY KEY,                      -- Unique agent ID.
    employee_code VARCHAR(15) NOT NULL UNIQUE,              -- Employee code.
    first_name VARCHAR(100) NOT NULL,                       -- Agent first name (in Spanish).
    last_name VARCHAR(100) NOT NULL,                        -- Agent last name (in Spanish).
    email VARCHAR(100) NOT NULL,                            -- Corporate email.
    phone VARCHAR(20),                                      -- Contact phone.
    native_accent VARCHAR(50) NOT NULL,                     -- Native Spanish accent (mexican, colombian, argentine).
    country_of_origin VARCHAR(50) NOT NULL,                 -- Country of origin.
    assigned_branch_id VARCHAR(20),                         -- Assigned branch.
    agent_type VARCHAR(30) NOT NULL,                        -- Type (Phone, In-Person, Digital, Hybrid).
    experience_level VARCHAR(20) NOT NULL,                  -- Level (Junior, Mid-Senior, Senior, Specialist).
    languages VARCHAR(100) NOT NULL,                        -- Languages spoken.
    specialty VARCHAR(100),                                 -- Specialty.
    hire_date DATE NOT NULL,                                -- Hire date.
    avg_csat DECIMAL(3, 2),                                 -- Average CSAT score (1-5).
    total_monthly_interactions INTEGER,                     -- Total interactions in last month.
    agent_status VARCHAR(20) NOT NULL,                      -- Status (Active, Vacation, Leave, Inactive).
    work_shift VARCHAR(20) NOT NULL                         -- Shift (Morning, Afternoon, Night, Rotating).
);
