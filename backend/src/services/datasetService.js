const db = require("../../config/db");
const { hashFile } = require("../engine/ingestion/hashFile");
const { profileColumns } = require("../engine/ingestion/profileColumns");
const { detectDatasetType } = require("../engine/ingestion/detectDatasetType");
const { processFile } = require("../../services/fileprocessingservices");
const { saveIngestion } = require("../../services/ingestionPersistenceService");

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
  const profile = profileColumns(processed);
  const datasetType = detectDatasetType(processed.headers, processed.rows);

  const sourceFile = {
    fileName: file.originalname,
    format: processed.format,
    sizeBytes: file.size,
    sheetName: processed.sheetName,
    fileHash
  };

  const ingestionId = await saveIngestion({
    businessAccountId,
    sourceFile,
    dataset: {
      headers: processed.headers,
      rows: processed.rows
    },
    profile,
    datasetType: datasetType.type,
    included: true
  });

  return {
    ingestionId,
    sourceFile,
    dataset: {
      headers: processed.headers,
      rows: processed.rows,
      profile,
      type: datasetType
    },
    processing: {
      skippedRows: processed.skippedRows || [],
      skippedRowCount: (processed.skippedRows || []).length
    }
  };
}

module.exports = { ingestDataset, findDuplicate };
