const express = require("express");

const upload = require("../middleware/uploadMiddleware");

const {
    processFile
} = require("../services/fileprocessingservices");

const {
    profileDataset
} = require("../services/datasetProfilingService");

const {
    createIngestionResult
} = require("../services/ingestionResultService");

const router = express.Router();

router.post("/", upload.single("file"), (req, res, next) => {
    try {
        if (!req.file) {
            return res.status(400).json({
                success: false,
                message: "No file was uploaded"
            });
        }

        /*
         * Part 2:
         * Read the CSV or Excel file and extract headers and rows.
         */
        const dataset = processFile(req.file);

        /*
         * Part 3:
         * Count rows and columns and detect column types.
         */
        const profile = profileDataset(dataset);

        /*
         * Part 4:
         * Package the file information, dataset, profile,
         * and Module 3 handoff into one response.
         */
        const ingestionResult = createIngestionResult({
            file: req.file,
            dataset: dataset,
            profile: profile
        });

        return res.status(200).json(ingestionResult);
    } catch (error) {
        next(error);
    }
});

module.exports = router;