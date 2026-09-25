const express = require("express");
const fs = require("fs");

const upload = require("../middleware/uploadMiddleware");
const { ingestDataset } = require("../src/services/datasetService");

const router = express.Router();

function removeTemporaryFile(filePath) {
  if (!filePath) return;

  fs.unlink(filePath, (error) => {
    if (error && error.code !== "ENOENT") {
      console.error("Could not remove temporary upload:", error.message);
    }
  });
}

router.post("/", upload.single("file"), async (req, res, next) => {
  try {
    if (!req.file) {
      return res.status(400).json({
        success: false,
        message: "No file uploaded"
      });
    }

    const result = await ingestDataset({
      businessAccountId: req.user.id,
      file: req.file
    });

    return res.status(200).json({
      success: true,
      message: "Dataset uploaded, profiled and saved successfully",
      data: {
        sourceFile: result.sourceFile,
        dataset: result.dataset,
        processing: result.processing,
        handoff: {
          status: "ready_for_mapping",
          ingestionId: result.ingestionId
        }
      }
    });
  } catch (error) {
    next(error);
  } finally {
    removeTemporaryFile(req.file?.path);
  }
});

module.exports = router;
