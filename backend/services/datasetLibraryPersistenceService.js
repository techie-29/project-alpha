const db = require("../config/db");

function parseJson(value, fallback) {
  if (value === null || value === undefined) return fallback;
  if (typeof value !== "string") return value;
  try { return JSON.parse(value); } catch { return fallback; }
}

async function listDatasets({ businessAccountId }) {
  const [rows] = await db.execute(
    `SELECT i.*, DATE_FORMAT(i.date_from, '%Y-%m-%d') AS date_from,
            DATE_FORMAT(i.date_to, '%Y-%m-%d') AS date_to,
            dm.coverage AS mapping_coverage, dm.missing_critical_fields,
            (SELECT COUNT(*) FROM sales_records sr WHERE sr.ingestion_id = i.id) AS sales_records,
            (SELECT COUNT(*) FROM stock_snapshots ss WHERE ss.ingestion_id = i.id) AS stock_records
     FROM ingestions i
     LEFT JOIN dataset_mappings dm ON dm.ingestion_id = i.id AND dm.business_account_id = i.business_account_id
     WHERE i.business_account_id = ?
     ORDER BY i.created_at DESC`,
    [businessAccountId]
  );
  const [repeatedOrders] = await db.execute(
    `SELECT DISTINCT current_row.ingestion_id, current_row.order_id
     FROM sales_records current_row
     INNER JOIN sales_records other_row
       ON other_row.business_account_id = current_row.business_account_id
      AND other_row.order_id = current_row.order_id
      AND other_row.ingestion_id <> current_row.ingestion_id
     WHERE current_row.business_account_id = ? AND current_row.order_id IS NOT NULL`,
    [businessAccountId]
  );
  const repeatedByDataset = repeatedOrders.reduce((counts, row) => {
    counts.set(row.ingestion_id, (counts.get(row.ingestion_id) || 0) + 1);
    return counts;
  }, new Map());
  rows.forEach((row) => { row.repeated_order_count = repeatedByDataset.get(row.id) || 0; });
  return rows;
}

async function getDataset({ businessAccountId, ingestionId }) {
  const [datasets] = await db.execute(
    `SELECT i.*, DATE_FORMAT(i.date_from, '%Y-%m-%d') AS date_from,
            DATE_FORMAT(i.date_to, '%Y-%m-%d') AS date_to,
            dm.mapping_json, dm.coverage AS mapping_coverage, dm.missing_critical_fields
     FROM ingestions i
     LEFT JOIN dataset_mappings dm ON dm.ingestion_id = i.id AND dm.business_account_id = i.business_account_id
     WHERE i.id = ? AND i.business_account_id = ? LIMIT 1`,
    [ingestionId, businessAccountId]
  );
  if (!datasets[0]) return null;
  const [issues] = await db.execute(
    `SELECT row_index, field_name, issue_code, severity, original_value, message, action
     FROM validation_issues WHERE ingestion_id = ? AND business_account_id = ?
     ORDER BY row_index, id LIMIT 100`,
    [ingestionId, businessAccountId]
  );
  return { dataset: datasets[0], issues };
}

async function setDatasetIncluded({ businessAccountId, ingestionId, included }) {
  const [result] = await db.execute(
    `UPDATE ingestions SET included = ? WHERE id = ? AND business_account_id = ?`,
    [included, ingestionId, businessAccountId]
  );
  return result.affectedRows > 0;
}

async function loadExport({ businessAccountId, ingestionId, type }) {
  const [datasets] = await db.execute(
    "SELECT original_file_name FROM ingestions WHERE id = ? AND business_account_id = ? LIMIT 1",
    [ingestionId, businessAccountId]
  );
  if (!datasets[0]) return null;
  const selections = {
    sales: `SELECT order_id, DATE_FORMAT(order_date, '%Y-%m-%d') AS order_date, product_key,
                   product_name, sku, category, quantity, unit_price, discount, revenue,
                   cost_price, profit, customer_key, customer_id, customer_name, customer_email,
                   status, notes, source_row_number
            FROM sales_records WHERE ingestion_id = ? AND business_account_id = ? ORDER BY source_row_number`,
    stock: `SELECT product_key, product_name, sku, stock_qty, reorder_level, stock_status,
                   DATE_FORMAT(stock_as_of_date, '%Y-%m-%d') AS stock_as_of_date,
                   supplier_name, source_row_number
            FROM stock_snapshots WHERE ingestion_id = ? AND business_account_id = ? ORDER BY source_row_number`,
    issues: `SELECT row_index, field_name, issue_code, severity, original_value, message, action
             FROM validation_issues WHERE ingestion_id = ? AND business_account_id = ? ORDER BY row_index, id`
  };
  const [rows] = await db.execute(selections[type], [ingestionId, businessAccountId]);
  return { filename: datasets[0].original_file_name, rows };
}

module.exports = { listDatasets, getDataset, setDatasetIncluded, loadExport, parseJson };
