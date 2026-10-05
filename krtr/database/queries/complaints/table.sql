-- Schema for the `complaints` fact table: one row per complaint/claim/request
-- raised through the PQR system, partitioned daily by `process_date` in the
-- source.
-- Assumes `customers`, `products`, `branches`, `service_agents` and the
-- interactions table already exist: `complaints` references all four by
-- foreign key but this repository does not create them.
-- Consumed by krtr.database.neon.schema.create_table_schema.
CREATE TABLE IF NOT EXISTS complaints (
    complaint_id VARCHAR(30) PRIMARY KEY,                   -- Unique complaint/claim ID.
    creation_date TIMESTAMP NOT NULL,                       -- Complaint creation date.
    process_date DATE NOT NULL,                             -- Process date (partition key).
    customer_id VARCHAR(20) NOT NULL,                       -- Customer ID.
    case_type VARCHAR(30) NOT NULL,                         -- Type (Complaint, Claim, Request, Suggestion).
    category VARCHAR(100) NOT NULL,                         -- Case category.
    subcategory VARCHAR(100),                                -- Subcategory.
    reception_channel VARCHAR(30) NOT NULL,                 -- Channel (Call Center, Email, Web, App, Branch, Regulator).
    affected_product_id VARCHAR(20),                         -- Affected product ID.
    related_branch_id VARCHAR(20),                           -- Related branch ID.
    origin_interaction_id VARCHAR(30),                       -- Originating interaction ID.
    description TEXT NOT NULL,                              -- Case description (in Spanish).
    claimed_amount DECIMAL(15, 2),                          -- Claimed amount (if applicable).
    currency VARCHAR(3),                                    -- Claimed amount currency.
    priority VARCHAR(20) NOT NULL,                          -- Priority (Low, Medium, High, Critical).
    status VARCHAR(30) NOT NULL,                            -- Status (Open, In Process, Escalated, Resolved, Closed, Rejected).
    assigned_agent_id VARCHAR(20),                           -- Assigned agent ID.
    assignment_date TIMESTAMP,                              -- Assignment date.
    first_response_date TIMESTAMP,                          -- First response date.
    resolution_date TIMESTAMP,                              -- Resolution date.
    closing_date TIMESTAMP,                                 -- Closing date.
    sla_breached BOOLEAN NOT NULL,                          -- SLA breached.
    resolution_days INTEGER,                                 -- Days to resolution.
    resolution TEXT                                         -- Resolution description (in Spanish).
);
