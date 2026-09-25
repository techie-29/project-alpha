const express = require("express");
const fs = require("fs");

const upload = require("../middleware/uploadMiddleware");
const { MAX_BATCH_FILES } = require("../middleware/uploadMiddleware");
const { ingestDataset } = require("../src/services/datasetService");
const { processUploadBatch } = require("../src/services/uploadBatchService");
const batchRepository = require("../services/ingestionBatchPersistenceService");

function removeTemporaryFile(filePath) {
  if (!filePath) return;

  fs.unlink(filePath, (error) => {
    if (error && error.code !== "ENOENT") {
      console.error("Could not remove temporary upload:", error.message);
    }
  });
}

function ingestionData(result) {
  return {
    sourceFile: result.sourceFile,
    dataset: result.dataset,
    processing: result.processing,
    handoff: {
      status: "ready_for_mapping",
      ingestionId: result.ingestionId
    }
  };
}

function createUploadRouter({
  ingest = ingestDataset,
  processBatch = processUploadBatch,
  getBatch = batchRepository.getBatch
} = {}) {
  const router = express.Router();

  router.post("/batch", upload.array("files", MAX_BATCH_FILES), async (req, res, next) => {
    try {
      if (!req.files?.length) {
        return res.status(400).json({
          success: false,
          code: "EMPTY_BATCH",
          message: "Choose at least one file to upload"
        });
      }

      const result = await processBatch({
        businessAccountId: req.user.id,
        files: req.files
      });

      return res.status(200).json({
        success: true,
        message: result.batch.status === "completed"
          ? "All datasets were uploaded and processed successfully"
          : "Batch processing finished; one or more files need attention",
        data: {
          batch: result.batch,
          items: result.items.map((item) => ({
            fileIndex: item.fileIndex,
            fileName: item.fileName,
            status: item.status,
            error: item.error || null,
            data: item.result ? ingestionData(item.result) : null
          }))
        }
      });
    } catch (error) {
      next(error);
    } finally {
      (req.files || []).forEach((file) => removeTemporaryFile(file.path));
    }
  });

  router.get("/batches/:batchId", async (req, res, next) => {
    try {
      const batch = await getBatch({
        businessAccountId: req.user.id,
        batchId: req.params.batchId
      });

      if (!batch) {
        return res.status(404).json({
          success: false,
          message: "Upload batch not found"
        });
      }

      return res.json({ success: true, data: { batch } });
    } catch (error) {
      next(error);
    }
  });

  router.post("/", upload.single("file"), async (req, res, next) => {
    try {
      if (!req.file) {
        return res.status(400).json({
          success: false,
          message: "No file uploaded"
        });
      }

      const result = await ingest({
        businessAccountId: req.user.id,
        file: req.file
      });

      return res.status(200).json({
        success: true,
        message: "Dataset uploaded, profiled and saved successfully",
        data: ingestionData(result)
      });
    } catch (error) {
      next(error);
    } finally {
      removeTemporaryFile(req.file?.path);
    }
  });

  return router;
}

module.exports = createUploadRouter();
module.exports.createUploadRouter = createUploadRouter;
module.exports.ingestionData = ingestionData;
