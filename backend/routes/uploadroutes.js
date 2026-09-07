const express = require("express");
const fs = require("fs");

const upload = require("../middleware/uploadMiddleware");
const {
    processFile
} = require("../services/fileprocessingservices");
const {
    profileDataset
} = require("../services/datasetProfilingService");
const {
    saveIngestion
} = require("../services/ingestionPersistenceService");

const router = express.Router();

function removeTemporaryFile(filePath) {
    if (!filePath) {
        return;
    }

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

        const processedDataset = processFile(req.file);
        const profile = profileDataset(processedDataset);
        const sourceFile = {
            fileName: req.file.originalname,
            format: processedDataset.format,
            sizeBytes: req.file.size,
            sheetName: processedDataset.sheetName
        };
        const ingestionId = await saveIngestion({
            businessAccountId: req.user.id,
            sourceFile,
            dataset: {
                headers: processedDataset.headers,
                rows: processedDataset.rows
            },
            profile
        });

        const ingestionResult = {
            success: true,
            message: "Dataset uploaded and structured successfully",

            data: {
                sourceFile,

                dataset: {
                    headers: processedDataset.headers,
                    rows: processedDataset.rows,
                    profile
                },

                handoff: {
                    status: "ready_for_validation",
                    ingestionId
                }
            }
        };

        console.log(
            `Ingestion ${ingestionId} saved for ${req.file.originalname}: ` +
            `${profile.rowCount} rows, ${profile.columnCount} columns`
        );

        return res.status(200).json(ingestionResult);
    } catch (error) {
        next(error);
    } finally {
        removeTemporaryFile(req.file?.path);
    }
});

module.exports = router;
