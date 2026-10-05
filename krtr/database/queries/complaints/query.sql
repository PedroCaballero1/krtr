-- Bulk-insert template for the `complaints` table, used with psycopg2's
-- execute_values (the VALUES placeholder is expanded to one group per row).
-- Column order must match the column order of `complaints/table.sql`.
-- Do not write a literal percent-s in these comments: psycopg2 counts it as a placeholder.
INSERT INTO complaints (
    complaint_id,
    creation_date,
    process_date,
    customer_id,
    case_type,
    category,
    subcategory,
    reception_channel,
    affected_product_id,
    related_branch_id,
    origin_interaction_id,
    description,
    claimed_amount,
    currency,
    priority,
    status,
    assigned_agent_id,
    assignment_date,
    first_response_date,
    resolution_date,
    closing_date,
    sla_breached,
    resolution_days,
    resolution
) VALUES %s
