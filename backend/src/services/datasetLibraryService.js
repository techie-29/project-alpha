const defaultRepository = require("../../services/datasetLibraryPersistenceService");
const ExcelJS = require("exceljs");

function parseJson(value, fallback) {
  if (value === null || value === undefined) return fallback;
  if (typeof value !== "string") return value;
  try { return JSON.parse(value); } catch { return fallback; }
}

function summary(row) {
  const validation = parseJson(row.validation_summary_json, {});
  const quality = parseJson(row.quality_summary_json, {});
  return {
    id: row.id,
    filename: row.original_file_name,
    format: row.file_format,
    fileSizeBytes: row.file_size_bytes,
    fileHash: row.file_hash,
    datasetType: row.dataset_type,
    included: Boolean(row.included),
    status: row.status,
    rowsUploaded: row.row_count,
    rowsProcessed: validation.processedRows ?? null,
    rowsRepaired: validation.repairedRows ?? null,
    rowsSkipped: validation.skippedRows ?? null,
    salesRecords: Number(row.sales_records || 0),
    stockRecords: Number(row.stock_records || 0),
    repeatedOrderCount: Number(row.repeated_order_count || 0),
    dateFrom: row.date_from,
    dateTo: row.date_to,
    mappingCoverage: row.mapping_coverage === null ? null : Number(row.mapping_coverage),
    validationSuccessRate: validation.validationSuccessRate ?? null,
    qualityScore: quality.score ?? null,
    missingCriticalFields: parseJson(row.missing_critical_fields, []),
    createdAt: row.created_at
  };
}

function overlapWarnings(datasets) {
  return datasets.map((dataset) => {
    if (!dataset.dateFrom || !dataset.dateTo) return { ...dataset, overlapWarnings: [] };
    const overlaps = datasets.filter((other) => other.id !== dataset.id && other.datasetType === dataset.datasetType && other.dateFrom && other.dateTo && String(other.dateFrom).slice(0, 10) <= String(dataset.dateTo).slice(0, 10) && String(other.dateTo).slice(0, 10) >= String(dataset.dateFrom).slice(0, 10));
    return { ...dataset, overlapWarnings: overlaps.map((other) => ({ datasetId: other.id, filename: other.filename, from: other.dateFrom, to: other.dateTo })) };
  });
}

function createDatasetLibraryService({ repository = defaultRepository } = {}) {
  async function list({ businessAccountId }) {
    return overlapWarnings((await repository.listDatasets({ businessAccountId })).map(summary));
  }

  async function get({ businessAccountId, ingestionId }) {
    const result = await repository.getDataset({ businessAccountId, ingestionId });
    if (!result) {
      const error = new Error("Dataset not found");
      error.status = 404;
      throw error;
    }
    return {
      ...summary(result.dataset),
      headers: parseJson(result.dataset.headers_json, []),
      profile: parseJson(result.dataset.profile_json, {}),
      mapping: parseJson(result.dataset.mapping_json, []),
      validation: parseJson(result.dataset.validation_summary_json, null),
      transformation: parseJson(result.dataset.transformation_summary_json, null),
      quality: parseJson(result.dataset.quality_summary_json, null),
      issues: result.issues.map((issue) => ({ ...issue, original_value: parseJson(issue.original_value, issue.original_value) }))
    };
  }

  async function setIncluded({ businessAccountId, ingestionId, included }) {
    if (typeof included !== "boolean") {
      const error = new Error("included must be a boolean");
      error.status = 400;
      throw error;
    }
    const updated = await repository.setDatasetIncluded({ businessAccountId, ingestionId, included });
    if (!updated) {
      const error = new Error("Dataset not found");
      error.status = 404;
      throw error;
    }
    return { ingestionId: Number(ingestionId), included };
  }

  async function exportDataset({ businessAccountId, ingestionId, type = "sales", format = "csv" }) {
    if (!["sales", "stock", "issues"].includes(type) || !["csv", "xlsx"].includes(format)) {
      const error = new Error("Export type must be sales, stock or issues and format must be csv or xlsx");
      error.status = 400;
      error.code = "INVALID_EXPORT";
      throw error;
    }
    const result = await repository.loadExport({ businessAccountId, ingestionId, type });
    if (!result) {
      const error = new Error("Dataset not found");
      error.status = 404;
      throw error;
    }
    const columns = result.rows.length ? Object.keys(result.rows[0]) : [];
    const base = result.filename.replace(/\.[^.]+$/, "").replace(/[^a-z0-9_-]+/gi, "-");
    if (format === "csv") {
      const escape = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
      const lines = [columns, ...result.rows.map((row) => columns.map((column) => {
        const value = row[column];
        return typeof value === "object" && value !== null ? JSON.stringify(value) : value;
      }))].map((row) => row.map(escape).join(","));
      return { filename: `${base}-${type}.csv`, mime: "text/csv; charset=utf-8", buffer: Buffer.from(lines.join("\n"), "utf8") };
    }
    const workbook = new ExcelJS.Workbook();
    const sheet = workbook.addWorksheet(type);
    sheet.columns = columns.map((column) => ({ header: column, key: column, width: Math.max(14, column.length + 2) }));
    result.rows.forEach((row) => sheet.addRow(row));
    if (columns.length) {
      sheet.getRow(1).font = { bold: true };
      sheet.autoFilter = { from: { row: 1, column: 1 }, to: { row: 1, column: columns.length } };
      sheet.views = [{ state: "frozen", ySplit: 1 }];
    }
    return { filename: `${base}-${type}.xlsx`, mime: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", buffer: Buffer.from(await workbook.xlsx.writeBuffer()) };
  }

  return { list, get, setIncluded, exportDataset };
}

const service = createDatasetLibraryService();
module.exports = { createDatasetLibraryService, overlapWarnings, list: service.list, get: service.get, setIncluded: service.setIncluded, exportDataset: service.exportDataset };
