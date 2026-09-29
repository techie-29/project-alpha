const defaultDb = require("../../config/db");
const { hashFile: defaultHashFile } = require("../engine/ingestion/hashFile");
const { profileColumns: defaultProfileColumns } = require("../engine/ingestion/profileColumns");
const { detectDatasetType: defaultDetectDatasetType } = require("../engine/ingestion/detectDatasetType");
const { processFile: defaultProcessFile } = require("../../services/fileprocessingservices");
const { saveIngestion: defaultSaveIngestion } = require("../../services/ingestionPersistenceService");

function createDatasetService({
  db = defaultDb,
  hashFile = defaultHashFile,
  profileColumns = defaultProfileColumns,
  detectDatasetType = defaultDetectDatasetType,
  processFile = defaultProcessFile,
  saveIngestion = defaultSaveIngestion
} = {}) {
  async function findDuplicate(businessAccountId, fileHash) {
    const [rows] = await db.execute(
      `SELECT id, original_file_name, created_at
       FROM ingestions
       WHERE business_account_id = ? AND file_hash = ?
       LIMIT 1`,
      [businessAccountId, fileHash]
    );

    return rows[0] || null;
  }

  async function ingestDataset({ businessAccountId, file }) {
    const fileHash = await hashFile(file.path);
    const duplicate = await findDuplicate(businessAccountId, fileHash);

    if (duplicate) {
      const error = new Error("This exact file has already been uploaded");
      error.status = 409;
      error.code = "DUPLICATE_DATASET";
      error.details = {
        existingIngestionId: duplicate.id,
        originalFileName: duplicate.original_file_name,
        uploadedAt: duplicate.created_at
      };
      throw error;
    }

    const processed = processFile(file);
    const profile = {
      ...profileColumns(processed),
      headerRowNumber: processed.headerRowNumber,
      skippedRowCount: (processed.skippedRows || []).length,
      skippedRows: processed.skippedRows || [],
      warnings: processed.warnings || [],
      workbook: processed.workbook || null
    };
    const datasetType = detectDatasetType(processed.headers, processed.rows);

    const sourceFile = {
      fileName: file.originalname,
      format: processed.format,
      sizeBytes: file.size,
      sheetName: processed.sheetName,
      fileHash
    };

    const dataset = {
      headers: processed.headers,
      rows: processed.rows,
      sourceRowNumbers: processed.sourceRowNumbers
    };

    const ingestionId = await saveIngestion({
      businessAccountId,
      sourceFile,
      dataset,
      profile,
      datasetType: datasetType.type,
      included: true
    });

    return {
      ingestionId,
      sourceFile,
      dataset: {
        headers: dataset.headers,
        rows: dataset.rows,
        profile,
        type: datasetType
      },
      processing: {
        status: "completed",
        stages: ["hashing", "parsing", "profiling", "persisting"],
        skippedRows: processed.skippedRows || [],
        skippedRowCount: (processed.skippedRows || []).length,
        warnings: processed.warnings || [],
        workbook: processed.workbook || null
      }
    };
  }

  return { ingestDataset, findDuplicate };
}

const datasetService = createDatasetService();

module.exports = {
  createDatasetService,
  ingestDataset: datasetService.ingestDataset,
  findDuplicate: datasetService.findDuplicate
};
