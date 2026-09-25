const multer = require("multer");
const path = require("path");

const allowedExtensions = [".csv", ".xlsx", ".xls"];
const MAX_FILE_SIZE = 10 * 1024 * 1024;
const MAX_BATCH_FILES = 10;

const upload = multer({
    dest: "uploads/",

    limits: {
        fileSize: MAX_FILE_SIZE,
        files: MAX_BATCH_FILES
    },

    fileFilter: (req, file, cb) => {
        const extension = path.extname(file.originalname).toLowerCase();

        if (allowedExtensions.includes(extension)) {
            cb(null, true);
        } else {
            cb(new Error("Only CSV and Excel files are allowed"));
        }
    }
});

module.exports = upload;
module.exports.MAX_FILE_SIZE = MAX_FILE_SIZE;
module.exports.MAX_BATCH_FILES = MAX_BATCH_FILES;
