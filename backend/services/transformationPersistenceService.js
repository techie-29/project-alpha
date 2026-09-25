const db = require("../config/db");

const BATCH_SIZE = 200;

function parseJson(value, fallback) {
  if (value === null || value === undefined) return fallback;
  if (typeof value !== "string") return value;
  try { return JSON.parse(value); } catch { return fallback; }
}

async function loadTransformationInput({ businessAccountId, ingestionId }) {
  const [datasets] = await db.execute(
    `SELECT i.id, i.dataset_type, i.status, i.validation_summary_json,
            dm.coverage AS mapping_coverage
     FROM ingestions i
     LEFT JOIN dataset_mappings dm
       ON dm.ingestion_id = i.id AND dm.business_account_id = i.business_account_id
     WHERE i.id = ? AND i.business_account_id = ?
     LIMIT 1`,
    [ingestionId, businessAccountId]
  );
  if (!datasets[0]) return null;

  const [rows] = await db.execute(
    `SELECT source_row_number, validation_status, validation_issues,
            transformed_data, raw_data
     FROM ingestion_rows
     WHERE ingestion_id = ? AND validation_status <> 'pending'
     ORDER BY source_row_number`,
    [ingestionId]
  );
  const validationSummary = parseJson(datasets[0].validation_summary_json, null);

  return {
    datasetType: datasets[0].dataset_type || "unknown",
    status: datasets[0].status,
    validationSummary,
    mappingCoverage: Number(datasets[0].mapping_coverage || 0),
    rows: rows.map((row) => {
      const issues = parseJson(row.validation_issues, []);
      return {
        sourceRowNumber: row.source_row_number,
        status: row.validation_status,
        canonical: parseJson(row.transformed_data, {}),
        rawValues: parseJson(row.raw_data, {}),
        repairedFields: [...new Set(
          issues.filter((issue) => issue.severity === "repaired" && issue.field)
            .map((issue) => issue.field)
        )],
        issues
      };
    })
  };
}

async function insertBatches(connection, table, columns, records, valuesForRecord) {
  for (let start = 0; start < records.length; start += BATCH_SIZE) {
    const batch = records.slice(start, start + BATCH_SIZE);
    const rowPlaceholder = `(${columns.map(() => "?").join(", ")})`;
    const placeholders = batch.map(() => rowPlaceholder).join(", ");
    const values = batch.flatMap(valuesForRecord);
    await connection.execute(
      `INSERT INTO ${table} (${columns.join(", ")}) VALUES ${placeholders}`,
      values
    );
  }
}

async function saveTransformationResult({ businessAccountId, ingestionId, result, quality }) {
  let connection;
  try {
    connection = await db.getConnection();
    await connection.beginTransaction();
    await connection.execute("DELETE FROM sales_records WHERE ingestion_id = ?", [ingestionId]);
    await connection.execute("DELETE FROM stock_snapshots WHERE ingestion_id = ?", [ingestionId]);
    await connection.execute("DELETE FROM customer_records WHERE ingestion_id = ?", [ingestionId]);
    await connection.execute("DELETE FROM product_records WHERE ingestion_id = ?", [ingestionId]);
    await connection.execute("DELETE FROM supplier_records WHERE ingestion_id = ?", [ingestionId]);

    await insertBatches(connection, "sales_records", [
      "business_account_id", "ingestion_id", "source_row_number", "order_id", "order_date",
      "product_key", "product_name", "sku", "category", "quantity", "unit_price", "discount",
      "revenue", "cost_price", "profit", "customer_key", "customer_id", "customer_name",
      "customer_email", "status", "notes", "repaired_fields", "computed_fields", "raw_values"
    ], result.sales, (row) => [
      businessAccountId, ingestionId, row.source_row_index, row.order_id, row.order_date,
      row.product_key, row.product_name, row.sku, row.category, row.quantity, row.unit_price,
      row.discount, row.revenue, row.cost_price, row.profit, row.customer_key, row.customer_id,
      row.customer_name, row.customer_email, row.status, row.notes, JSON.stringify(row.repaired_fields),
      JSON.stringify(row.computed_fields), JSON.stringify(row.raw_values)
    ]);

    await insertBatches(connection, "stock_snapshots", [
      "business_account_id", "ingestion_id", "source_row_number", "product_key", "product_name",
      "sku", "stock_qty", "reorder_level", "stock_status", "stock_as_of_date", "supplier_name",
      "repaired_fields", "computed_fields", "raw_values"
    ], result.stock, (row) => [
      businessAccountId, ingestionId, row.source_row_index, row.product_key, row.product_name,
      row.sku, row.stock_qty, row.reorder_level, row.stock_status, row.stock_as_of_date,
      row.supplier_name, JSON.stringify(row.repaired_fields), JSON.stringify(row.computed_fields),
      JSON.stringify(row.raw_values)
    ]);

    await insertBatches(connection, "customer_records", [
      "business_account_id", "ingestion_id", "source_row_number", "customer_key", "customer_id",
      "customer_name", "customer_email", "customer_phone", "region", "repaired_fields", "raw_values"
    ], result.customers, (row) => [
      businessAccountId, ingestionId, row.source_row_index, row.customer_key, row.customer_id,
      row.customer_name, row.customer_email, row.customer_phone, row.region,
      JSON.stringify(row.repaired_fields), JSON.stringify(row.raw_values)
    ]);

    await insertBatches(connection, "product_records", [
      "business_account_id", "ingestion_id", "source_row_number", "product_key", "product_name",
      "sku", "category", "unit_price", "cost_price", "supplier_name", "repaired_fields", "raw_values"
    ], result.products, (row) => [
      businessAccountId, ingestionId, row.source_row_index, row.product_key, row.product_name,
      row.sku, row.category, row.unit_price, row.cost_price, row.supplier_name,
      JSON.stringify(row.repaired_fields), JSON.stringify(row.raw_values)
    ]);

    await insertBatches(connection, "supplier_records", [
      "business_account_id", "ingestion_id", "source_row_number", "supplier_key", "supplier_name",
      "repaired_fields", "raw_values"
    ], result.suppliers, (row) => [
      businessAccountId, ingestionId, row.source_row_index, row.supplier_key, row.supplier_name,
      JSON.stringify(row.repaired_fields), JSON.stringify(row.raw_values)
    ]);

    const dates = result.sales.map((row) => row.order_date).filter(Boolean).sort();
    await connection.execute(
      `UPDATE ingestions
       SET transformation_summary_json = ?, quality_summary_json = ?,
           date_from = ?, date_to = ?, status = 'ready_for_analytics'
       WHERE id = ? AND business_account_id = ?`,
      [
        JSON.stringify(result.summary), JSON.stringify(quality),
        dates[0] || null, dates[dates.length - 1] || null,
        ingestionId, businessAccountId
      ]
    );
    await connection.commit();
  } catch (error) {
    if (connection) await connection.rollback();
    throw error;
  } finally {
    connection?.release();
  }
}

async function getTransformationResult({ businessAccountId, ingestionId }) {
  const [datasets] = await db.execute(
    `SELECT status, transformation_summary_json, quality_summary_json, date_from, date_to
     FROM ingestions WHERE id = ? AND business_account_id = ? LIMIT 1`,
    [ingestionId, businessAccountId]
  );
  if (!datasets[0]) return null;
  if (!datasets[0].transformation_summary_json) return { pending: true };
  const [sales] = await db.execute("SELECT * FROM sales_records WHERE ingestion_id = ? ORDER BY source_row_number LIMIT 3", [ingestionId]);
  const [stock] = await db.execute("SELECT * FROM stock_snapshots WHERE ingestion_id = ? ORDER BY source_row_number LIMIT 3", [ingestionId]);
  const [customers] = await db.execute("SELECT * FROM customer_records WHERE ingestion_id = ? ORDER BY source_row_number LIMIT 3", [ingestionId]);
  const [products] = await db.execute("SELECT * FROM product_records WHERE ingestion_id = ? ORDER BY source_row_number LIMIT 3", [ingestionId]);
  const [suppliers] = await db.execute("SELECT * FROM supplier_records WHERE ingestion_id = ? ORDER BY source_row_number LIMIT 3", [ingestionId]);
  return {
    pending: false,
    status: datasets[0].status,
    summary: parseJson(datasets[0].transformation_summary_json, {}),
    quality: parseJson(datasets[0].quality_summary_json, {}),
    dateFrom: datasets[0].date_from,
    dateTo: datasets[0].date_to,
    examples: { sales, stock, customers, products, suppliers }
  };
}

module.exports = { loadTransformationInput, saveTransformationResult, getTransformationResult };
