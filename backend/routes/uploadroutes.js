const express = require("express");

const upload = require("../middleware/uploadMiddleware");

const {
    processFile
} = require("../services/fileprocessingservices");

const {
    profileDataset
} = require("../services/datasetProfilingService");

const router = express.Router();

router.post(
    "/",
    upload.single("file"),

    (req, res, next) => {
        try {
            if (!req.file) {
                return res.status(400).json({
                    success: false,
                    message: "No file uploaded"
                });
            }

            const result = processFile(req.file);

            const profile = profileDataset(result);

            const completeOutput = {
                success: true,
                message: "File processed and profiled successfully",

                data: {
                    headers: result.headers,
                    rows: result.rows,
                    profile: profile
                }
            };

            console.log(
                JSON.stringify(completeOutput, null, 2)
            );

            return res.json(completeOutput);

        } catch (error) {
            next(error);
        }
    }
);
module.exports = router;