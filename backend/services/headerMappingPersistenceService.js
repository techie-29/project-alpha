const db = require("../config/db");

async function getIngestion({ businessAccountId, ingestionId }) {
  const [rows] = await db.execute(
    `SELECT id, headers_json, dataset_type, status
     FROM ingestions
     WHERE id = ? AND business_account_id = ?
     LIMIT 1`,
    [ingestionId, businessAccountId]
  );
  return rows[0] || null;
}

async function getSampleRows({ businessAccountId, ingestionId, limit = 100 }) {
  const safeLimit = Math.max(1, Math.min(250, Number(limit) || 100));
  const [rows] = await db.execute(
    `SELECT ir.raw_data
     FROM ingestion_rows ir
     INNER JOIN ingestions i ON i.id = ir.ingestion_id
     WHERE ir.ingestion_id = ? AND i.business_account_id = ?
     ORDER BY ir.source_row_number
     LIMIT ${safeLimit}`,
    [ingestionId, businessAccountId]
  );
  return rows.map((row) => row.raw_data);
}

async function getDatasetMapping({ businessAccountId, ingestionId }) {
  const [rows] = await db.execute(
    `SELECT mapping_json, suggestions_json, coverage, header_coverage,
            missing_critical_fields, confirmed_at
     FROM dataset_mappings
     WHERE ingestion_id = ? AND business_account_id = ?
     LIMIT 1`,
    [ingestionId, businessAccountId]
  );
  return rows[0] || null;
}

async function getSavedMapping({ businessAccountId, headerSignature }) {
  const [rows] = await db.execute(
    `SELECT mapping_json
     FROM saved_mappings
     WHERE business_account_id = ? AND header_signature = ?
     LIMIT 1`,
    [businessAccountId, headerSignature]
  );
  return rows[0] || null;
}

async function saveMapping({
  businessAccountId,
  ingestionId,
  mappings,
  suggestions,
  coverage,
  headerSignature,
  saveTemplate
}) {
  let connection;

  try {
    connection = await db.getConnection();
    await connection.beginTransaction();

    await connection.execute(
      `INSERT INTO dataset_mappings (
        ingestion_id,
        business_account_id,
        mapping_json,
        suggestions_json,
        coverage,
        header_coverage,
        missing_critical_fields,
        confirmed_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
      ON DUPLICATE KEY UPDATE
        mapping_json = VALUES(mapping_json),
        suggestions_json = VALUES(suggestions_json),
        coverage = VALUES(coverage),
        header_coverage = VALUES(header_coverage),
        missing_critical_fields = VALUES(missing_critical_fields),
        confirmed_at = CURRENT_TIMESTAMP`,
      [
        ingestionId,
        businessAccountId,
        JSON.stringify(mappings),
        JSON.stringify(suggestions),
        coverage.coverage,
        coverage.headerCoverage,
        JSON.stringify(coverage.missingCriticalFields)
      ]
    );

    if (saveTemplate) {
      await connection.execute(
        `INSERT INTO saved_mappings (
          business_account_id,
          header_signature,
          mapping_json
        ) VALUES (?, ?, ?)
        ON DUPLICATE KEY UPDATE mapping_json = VALUES(mapping_json)`,
        [businessAccountId, headerSignature, JSON.stringify(mappings)]
      );
    }

    await connection.execute(
      `UPDATE ingestions
       SET status = 'ready_for_validation'
       WHERE id = ? AND business_account_id = ?`,
      [ingestionId, businessAccountId]
    );

    await connection.commit();
  } catch (error) {
    if (connection) await connection.rollback();
    throw error;
  } finally {
    connection?.release();
  }
}

module.exports = {
  getIngestion,
  getSampleRows,
  getDatasetMapping,
  getSavedMapping,
  saveMapping
};
