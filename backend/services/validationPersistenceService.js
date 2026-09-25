const db = require("../config/db");

const BATCH_SIZE = 250;

function parseJson(value, fallback) {
  if (value === null || value === undefined) return fallback;
  if (typeof value !== "string") return value;
  try { return JSON.parse(value); } catch { return fallback; }
}

async function loadValidationInput({ businessAccountId, ingestionId }) {
  const [datasets] = await db.execute(
    `SELECT i.id, i.dataset_type, i.status, dm.mapping_json
     FROM ingestions i
     LEFT JOIN dataset_mappings dm
       ON dm.ingestion_id = i.id AND dm.business_account_id = i.business_account_id
     WHERE i.id = ? AND i.business_account_id = ?
     LIMIT 1`,
    [ingestionId, businessAccountId]
  );
  if (!datasets[0]) return null;

  const [rows] = await db.execute(
    `SELECT source_row_number, raw_data
     FROM ingestion_rows
     WHERE ingestion_id = ?
     ORDER BY source_row_number`,
    [ingestionId]
  );

  return {
    ingestionId: datasets[0].id,
    datasetType: datasets[0].dataset_type || "unknown",
    status: datasets[0].status,
    mappings: parseJson(datasets[0].mapping_json, null),
    rawRows: rows.map((row) => ({
      sourceRowNumber: row.source_row_number,
      rawData: parseJson(row.raw_data, {})
    }))
  };
}

async function insertIssues(connection, businessAccountId, ingestionId, issues) {
  for (let start = 0; start < issues.length; start += BATCH_SIZE) {
    const batch = issues.slice(start, start + BATCH_SIZE);
    const placeholders = batch.map(() => "(?, ?, ?, ?, ?, ?, ?, ?, ?)").join(", ");
    const values = [];
    batch.forEach((item) => values.push(
      ingestionId,
      businessAccountId,
      item.row_index,
      item.field,
      item.code,
      item.severity,
      item.original_value === undefined ? null : JSON.stringify(item.original_value),
      item.message,
      item.action
    ));
    await connection.execute(
      `INSERT INTO validation_issues (
        ingestion_id, business_account_id, row_index, field_name,
        issue_code, severity, original_value, message, action
      ) VALUES ${placeholders}`,
      values
    );
  }
}

async function updateRows(connection, ingestionId, rows) {
  for (let start = 0; start < rows.length; start += BATCH_SIZE) {
    const batch = rows.slice(start, start + BATCH_SIZE);
    const placeholders = batch.map(() => "(?, ?, ?, ?, ?, ?)").join(", ");
    const values = [];
    batch.forEach((row) => values.push(
      ingestionId,
      row.sourceRowNumber,
      JSON.stringify(row.rawValues),
      row.status,
      JSON.stringify(row.issues),
      JSON.stringify(row.canonical)
    ));
    await connection.execute(
      `INSERT INTO ingestion_rows (
        ingestion_id, source_row_number, raw_data,
        validation_status, validation_issues, transformed_data
      ) VALUES ${placeholders}
      ON DUPLICATE KEY UPDATE
        validation_status = VALUES(validation_status),
        validation_issues = VALUES(validation_issues),
        transformed_data = VALUES(transformed_data)`,
      values
    );
  }
}

async function saveValidationResult({ businessAccountId, ingestionId, result }) {
  let connection;
  try {
    connection = await db.getConnection();
    await connection.beginTransaction();
    await connection.execute(
      "DELETE FROM validation_issues WHERE ingestion_id = ? AND business_account_id = ?",
      [ingestionId, businessAccountId]
    );
    await updateRows(connection, ingestionId, result.rows);
    await insertIssues(connection, businessAccountId, ingestionId, result.issues);
    await connection.execute(
      `UPDATE ingestions
       SET validation_summary_json = ?, status = 'ready_for_transformation'
       WHERE id = ? AND business_account_id = ?`,
      [JSON.stringify({ ...result.summary, dateOrders: result.dateOrders }), ingestionId, businessAccountId]
    );
    await connection.commit();
  } catch (error) {
    if (connection) await connection.rollback();
    throw error;
  } finally {
    connection?.release();
  }
}

async function getValidationResult({ businessAccountId, ingestionId }) {
  const [datasets] = await db.execute(
    `SELECT id, status, validation_summary_json
     FROM ingestions
     WHERE id = ? AND business_account_id = ?
     LIMIT 1`,
    [ingestionId, businessAccountId]
  );
  if (!datasets[0]) return null;
  if (!datasets[0].validation_summary_json) return { pending: true };

  const [rows] = await db.execute(
    `SELECT source_row_number, validation_status, validation_issues, transformed_data, raw_data
     FROM ingestion_rows
     WHERE ingestion_id = ?
     ORDER BY source_row_number
     LIMIT 50`,
    [ingestionId]
  );
  const [issues] = await db.execute(
    `SELECT row_index, field_name, issue_code, severity, original_value, message, action
     FROM validation_issues
     WHERE ingestion_id = ? AND business_account_id = ?
     ORDER BY row_index, id
     LIMIT 200`,
    [ingestionId, businessAccountId]
  );

  return {
    pending: false,
    status: datasets[0].status,
    summary: parseJson(datasets[0].validation_summary_json, {}),
    rows: rows.map((row) => ({
      sourceRowNumber: row.source_row_number,
      status: row.validation_status,
      canonical: parseJson(row.transformed_data, {}),
      rawValues: parseJson(row.raw_data, {}),
      issues: parseJson(row.validation_issues, [])
    })),
    issues: issues.map((item) => ({
      row_index: item.row_index,
      field: item.field_name,
      code: item.issue_code,
      severity: item.severity,
      original_value: parseJson(item.original_value, item.original_value),
      message: item.message,
      action: item.action
    }))
  };
}

module.exports = { loadValidationInput, saveValidationResult, getValidationResult };
