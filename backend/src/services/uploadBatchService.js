const { ingestDataset } = require("./datasetService");
const batchRepository = require("../../services/ingestionBatchPersistenceService");

function publicError(error) {
  const isExpected = !error.status || error.status < 500;
  return {
    code: error.code || "FILE_PROCESSING_FAILED",
    message: isExpected ? error.message : "The file could not be processed"
  };
}

function createBatchProcessor({
  ingest = ingestDataset,
  repository = batchRepository
} = {}) {
  return async function processUploadBatch({ businessAccountId, files }) {
    if (!Array.isArray(files) || files.length === 0) {
      const error = new Error("Choose at least one file to upload");
      error.status = 400;
      error.code = "EMPTY_BATCH";
      throw error;
    }

    const batchId = await repository.createBatch({ businessAccountId, files });
    const items = [];

    for (let fileIndex = 0; fileIndex < files.length; fileIndex += 1) {
      const file = files[fileIndex];
      await repository.markItemProcessing({ batchId, fileIndex });

      try {
        const result = await ingest({ businessAccountId, file });
        await repository.recordItemResult({
          batchId,
          fileIndex,
          ingestionId: result.ingestionId
        });
        items.push({
          fileIndex,
          fileName: file.originalname,
          status: "completed",
          result
        });
      } catch (error) {
        const safeError = publicError(error);
        await repository.recordItemResult({
          batchId,
          fileIndex,
          error: safeError
        });
        items.push({
          fileIndex,
          fileName: file.originalname,
          status: "failed",
          error: safeError
        });
      }
    }

    const batch = await repository.finishBatch(batchId);
    return { batch, items };
  };
}

const processUploadBatch = createBatchProcessor();

module.exports = { createBatchProcessor, processUploadBatch, publicError };
