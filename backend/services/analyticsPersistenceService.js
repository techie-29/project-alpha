const db = require("../config/db");

function parseJson(value, fallback) {
  if (value === null || value === undefined) return fallback;
  if (typeof value !== "string") return value;
  try { return JSON.parse(value); } catch { return fallback; }
}

async function loadAnalyticsData({ businessAccountId }) {
  const [datasets] = await db.execute(
    `SELECT i.id, i.original_file_name, i.dataset_type, i.row_count, i.status,
            i.date_from, i.date_to, i.included, i.profile_json,
            i.validation_summary_json, i.transformation_summary_json, i.quality_summary_json,
            dm.coverage AS mapping_coverage, dm.missing_critical_fields
     FROM ingestions i
     LEFT JOIN dataset_mappings dm ON dm.ingestion_id = i.id AND dm.business_account_id = i.business_account_id
     WHERE i.business_account_id = ? AND i.included = TRUE AND i.status = 'ready_for_analytics'
     ORDER BY i.created_at DESC`,
    [businessAccountId]
  );
  const [sales] = await db.execute(
    `SELECT sr.*, DATE_FORMAT(sr.order_date, '%Y-%m-%d') AS order_date,
            i.original_file_name AS source_file_name, dm.mapping_json AS source_mapping
     FROM sales_records sr
     INNER JOIN ingestions i ON i.id = sr.ingestion_id
     LEFT JOIN dataset_mappings dm ON dm.ingestion_id = i.id AND dm.business_account_id = i.business_account_id
     WHERE sr.business_account_id = ? AND i.business_account_id = ? AND i.included = TRUE`,
    [businessAccountId, businessAccountId]
  );
  const [stock] = await db.execute(
    `SELECT ss.*, DATE_FORMAT(ss.stock_as_of_date, '%Y-%m-%d') AS stock_as_of_date,
            i.original_file_name AS source_file_name, dm.mapping_json AS source_mapping
     FROM stock_snapshots ss
     INNER JOIN ingestions i ON i.id = ss.ingestion_id
     LEFT JOIN dataset_mappings dm ON dm.ingestion_id = i.id AND dm.business_account_id = i.business_account_id
     WHERE ss.business_account_id = ? AND i.business_account_id = ? AND i.included = TRUE`,
    [businessAccountId, businessAccountId]
  );
  const [products] = await db.execute(
    `SELECT pr.* FROM product_records pr
     INNER JOIN ingestions i ON i.id = pr.ingestion_id
     WHERE pr.business_account_id = ? AND i.business_account_id = ? AND i.included = TRUE`,
    [businessAccountId, businessAccountId]
  );
  return {
    sales,
    stock,
    products,
    datasets: datasets.map((dataset) => {
      const profile = parseJson(dataset.profile_json, {});
      const validation = parseJson(dataset.validation_summary_json, {});
      const transformation = parseJson(dataset.transformation_summary_json, {});
      const quality = parseJson(dataset.quality_summary_json, {});
      return {
        id: dataset.id,
        filename: dataset.original_file_name,
        datasetType: dataset.dataset_type,
        status: dataset.status,
        includedInAnalytics: Boolean(dataset.included),
        rowsUploaded: dataset.row_count,
        rowsProcessed: validation.processedRows ?? transformation.totalRecords ?? null,
        rowsRepaired: validation.repairedRows ?? null,
        rowsSkipped: validation.skippedRows ?? null,
        dateFrom: dataset.date_from,
        dateTo: dataset.date_to,
        mappingCoverage: dataset.mapping_coverage === null ? null : Number(dataset.mapping_coverage),
        validationSuccessRate: validation.validationSuccessRate ?? null,
        qualityScore: quality.score ?? null,
        missingCriticalFields: parseJson(dataset.missing_critical_fields, []),
        duplicateHeaders: profile.duplicateHeaders || [],
        supportedAreas: transformation.supportedAreas || []
      };
    })
  };
}

module.exports = { loadAnalyticsData };
