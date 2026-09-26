-- Reads one table's columns, in creation order, with their Postgres data
-- type and nullability. This is how the repository learns a table's shape
-- at load time instead of redeclaring it in Python: the shape always comes
-- from that table's own table.sql, applied to the live database.
-- Consumed by krtr.database.neon.client.NeonClient.get_column_specs.
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = %(table_name)s
ORDER BY ordinal_position;
