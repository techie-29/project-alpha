const multer = require("multer");
const path = require("path");
const fs = require("fs");
const crypto = require("crypto");

const ALLOWED = [".csv", ".xlsx", ".xls"];
const MAX_FILE_MB = Number(process.env.ALPHA_MAX_FILE_MB || 100);
const MAX_FILES = 10;
const UPLOAD_ROOT = path.resolve(process.env.UPLOAD_DIR || path.join(__dirname, "..", "uploads"), "alpha");

const storage = multer.diskStorage({
  destination(req, file, cb) {
    const dir = path.join(UPLOAD_ROOT, String(req.user.id));
    fs.mkdirSync(dir, { recursive: true });
    cb(null, dir);
  },
  filename(req, file, cb) {
    cb(null, `${crypto.randomUUID()}${path.extname(file.originalname).toLowerCase()}`);
  }
});

const alphaUpload = multer({
  storage,
  limits: { fileSize: MAX_FILE_MB * 1024 * 1024, files: MAX_FILES },
  fileFilter(req, file, cb) {
    if (ALLOWED.includes(path.extname(file.originalname).toLowerCase())) return cb(null, true);
    const error = new Error("Only CSV and Excel files are allowed");
    error.status = 400;
    cb(error);
  }
});

module.exports = alphaUpload;
module.exports.MAX_FILES = MAX_FILES;
module.exports.MAX_FILE_MB = MAX_FILE_MB;
module.exports.UPLOAD_ROOT = UPLOAD_ROOT;
