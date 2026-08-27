const multer = require("multer");
const path = require("path");

const allowedExtensions = [".csv", ".xlsx", ".xls"];

const upload = multer({
    dest: "uploads/",

    limits: {
        fileSize: 10 * 1024 * 1024
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