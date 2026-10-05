-- Bulk-insert template for the `service_agents` table, used with psycopg2's
-- execute_values (the VALUES placeholder is expanded to one group per row).
-- Column order must match the column order of `service_agents/table.sql`.
-- Do not write a literal percent-s in these comments: psycopg2 counts it as a placeholder.
INSERT INTO service_agents (
    agent_id,
    employee_code,
    first_name,
    last_name,
    email,
    phone,
    native_accent,
    country_of_origin,
    assigned_branch_id,
    agent_type,
    experience_level,
    languages,
    specialty,
    hire_date,
    avg_csat,
    total_monthly_interactions,
    agent_status,
    work_shift
) VALUES %s
