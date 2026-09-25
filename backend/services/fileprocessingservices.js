const fs = require("fs");
const path = require("path");
const { parse } = require("csv-parse/sync");
const XLSX = require("xlsx");
const { normalizeTable } = require("../src/engine/ingestion/normalizeTable");

const SUPPORTED_FORMATS = {
  ".csv": "csv",
  ".xlsx": "xlsx",
  ".xls": "xls"
};

function detectFileFormat(file) {
  if (!file || !file.originalname || !file.path) {
    throw new Error("Uploaded file information is missing");
  }

  const extension = path.extname(file.originalname).toLowerCase();
  const format = SUPPORTED_FORMATS[extension];
  if (!format) throw new Error("Unsupported file format");
  return format;
}

function parseCSV(filePath) {
  const content = fs.readFileSync(filePath, "utf8");
  return parse(content, {
    bom: true,
    skip_empty_lines: false,
    relax_column_count: true
  });
}

function parseFirstExcelSheet(filePath) {
  const workbook = XLSX.readFile(filePath, { cellDates: true });
  const sheetName = workbook.SheetNames[0];

  if (!sheetName) throw new Error("Excel workbook does not contain a worksheet");

  const worksheet = workbook.Sheets[sheetName];
  const rows = XLSX.utils.sheet_to_json(worksheet, {
    header: 1,
    defval: null,
    blankrows: true,
    raw: true
  });

  return { sheetName, rows };
}

function processFile(file) {
  const format = detectFileFormat(file);

  if (format === "csv") {
    const dataset = normalizeTable(parseCSV(file.path));
    return { format, sheetName: null, ...dataset };
  }

  const sheet = parseFirstExcelSheet(file.path);
  const dataset = normalizeTable(sheet.rows);

  return {
    format,
    sheetName: sheet.sheetName,
    ...dataset
  };
}

module.exports = { processFile, detectFileFormat };
