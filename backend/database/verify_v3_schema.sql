USE project_alpha;

-- Read-only V3 database check. This file changes no tables or data.
SELECT 'DATABASE' AS check_type, DATABASE() AS item, 'SELECTED' AS status;

SELECT
    'TABLE' AS check_type,
    required.table_name AS item,
    IF(actual.table_name IS NULL, 'MISSING', 'PRESENT') AS status
FROM (
    SELECT 'business_accounts' AS table_name UNION ALL
    SELECT 'ingestions' UNION ALL
    SELECT 'ingestion_rows' UNION ALL
    SELECT 'ingestion_batches' UNION ALL
    SELECT 'ingestion_batch_items' UNION ALL
    SELECT 'dataset_mappings' UNION ALL
    SELECT 'saved_mappings' UNION ALL
    SELECT 'validation_issues' UNION ALL
    SELECT 'sales_records' UNION ALL
    SELECT 'stock_snapshots' UNION ALL
    SELECT 'customer_records' UNION ALL
    SELECT 'product_records' UNION ALL
    SELECT 'supplier_records' UNION ALL
    SELECT 'admin_activity_logs'
) required
LEFT JOIN information_schema.TABLES actual
  ON actual.table_schema = DATABASE()
 AND actual.table_name = required.table_name
ORDER BY required.table_name;

SELECT
    'COLUMN' AS check_type,
    CONCAT(required.table_name, '.', required.column_name) AS item,
    IF(actual.column_name IS NULL, 'MISSING', 'PRESENT') AS status,
    actual.column_type AS actual_type
FROM (
    SELECT 'business_accounts' AS table_name, 'role' AS column_name UNION ALL
    SELECT 'business_accounts', 'account_status' UNION ALL
    SELECT 'business_accounts', 'currency_code' UNION ALL
    SELECT 'business_accounts', 'timezone' UNION ALL
    SELECT 'business_accounts', 'date_format' UNION ALL
    SELECT 'ingestions', 'file_hash' UNION ALL
    SELECT 'ingestions', 'dataset_type' UNION ALL
    SELECT 'ingestions', 'included' UNION ALL
    SELECT 'ingestions', 'validation_summary_json' UNION ALL
    SELECT 'ingestions', 'transformation_summary_json' UNION ALL
    SELECT 'ingestions', 'quality_summary_json' UNION ALL
    SELECT 'ingestions', 'date_from' UNION ALL
    SELECT 'ingestions', 'date_to' UNION ALL
    SELECT 'ingestion_rows', 'source_row_number' UNION ALL
    SELECT 'ingestion_rows', 'validation_status' UNION ALL
    SELECT 'ingestion_rows', 'validation_issues' UNION ALL
    SELECT 'ingestion_rows', 'transformed_data'
) required
LEFT JOIN information_schema.COLUMNS actual
  ON actual.table_schema = DATABASE()
 AND actual.table_name = required.table_name
 AND actual.column_name = required.column_name
ORDER BY required.table_name, required.column_name;
