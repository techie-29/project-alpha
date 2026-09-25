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

const MAX_DATA_ROWS = 50000;

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

function toIsoDate(value) {
  if (!(value instanceof Date) || Number.isNaN(value.getTime())) return value;
  return value.toISOString().slice(0, 10);
}

function mergedValue(rows, merges, rowIndex, columnIndex) {
  const merge = merges.find(({ s, e }) => (
    rowIndex >= s.r && rowIndex <= e.r &&
    columnIndex >= s.c && columnIndex <= e.c
  ));

  if (!merge) return rows[rowIndex]?.[columnIndex];
  return rows[merge.s.r]?.[merge.s.c];
}

/**
 * Converts a common two-level Excel header (for example, "Order" merged over
 * "ID" and "Date") into one stable header row. Title-only merged rows are
 * deliberately ignored so the normal table detector can skip them.
 */
function repairMergedHeaders(rows, merges = []) {
  if (!merges.length) return rows;

  const topRows = [...new Set(merges.map((merge) => merge.s.r))].sort((a, b) => a - b);

  for (const topRow of topRows) {
    const rowMerges = merges.filter((merge) => merge.s.r === topRow);
    const bottomRow = Math.max(
      ...rowMerges.map((merge) => Math.max(merge.e.r, merge.s.r + (merge.e.c > merge.s.c ? 1 : 0)))
    );
    const nextDataRow = rows[bottomRow + 1] || [];
    const width = Math.max(
      nextDataRow.length,
      ...rowMerges.map((merge) => merge.e.c + 1)
    );

    const topLabels = new Set();
    for (let column = 0; column < width; column += 1) {
      const value = mergedValue(rows, merges, topRow, column);
      if (value !== null && value !== undefined && String(value).trim()) {
        topLabels.add(String(value).trim().toLowerCase());
      }
    }

    const hasVerticalHeader = rowMerges.some((merge) => merge.e.r > merge.s.r);
    if (topLabels.size < 2 && rowMerges.length < 2 && !hasVerticalHeader) continue;

    const headers = [];
    for (let column = 0; column < width; column += 1) {
      const labels = [];
      for (let row = topRow; row <= bottomRow; row += 1) {
        const value = mergedValue(rows, merges, row, column);
        const label = value === null || value === undefined ? "" : String(value).trim();
        if (label && labels[labels.length - 1] !== label) labels.push(label);
      }
      headers.push(labels.join(" "));
    }

    if (headers.filter(Boolean).length < 2) continue;

    const repairedRows = rows.map((row) => [...row]);
    for (let row = topRow; row < bottomRow; row += 1) repairedRows[row] = [];
    repairedRows[bottomRow] = headers;
    return repairedRows;
  }

  return rows;
}

function parseFirstExcelSheet(filePath) {
  const workbook = XLSX.readFile(filePath, { cellDates: true, cellNF: true });
  const sheetName = workbook.SheetNames[0];

  if (!sheetName) throw new Error("Excel workbook does not contain a worksheet");

  const worksheet = workbook.Sheets[sheetName];
  const rawRows = XLSX.utils.sheet_to_json(worksheet, {
    header: 1,
    defval: null,
    blankrows: true,
    raw: true
  });

  let excelDateCellCount = 0;
  const datedRows = rawRows.map((row) => row.map((value) => {
    const normalized = toIsoDate(value);
    if (normalized !== value) excelDateCellCount += 1;
    return normalized;
  }));
  const merges = worksheet["!merges"] || [];
  const rows = repairMergedHeaders(datedRows, merges);

  const ignoredSheetCount = Math.max(0, workbook.SheetNames.length - 1);
  const warnings = [];
  if (ignoredSheetCount > 0) {
    const noun = ignoredSheetCount === 1 ? "worksheet was" : "worksheets were";
    warnings.push(
      `Only the first worksheet was processed; ${ignoredSheetCount} additional ${noun} ignored.`
    );
  }

  return {
    sheetName,
    rows,
    warnings,
    workbook: {
      sheetCount: workbook.SheetNames.length,
      ignoredSheetCount,
      mergedRangeCount: merges.length,
      excelDateCellCount
    }
  };
}

function processFile(file) {
  const format = detectFileFormat(file);

  if (format === "csv") {
    const dataset = normalizeTable(parseCSV(file.path), { maxRows: MAX_DATA_ROWS });
    return {
      format,
      sheetName: null,
      warnings: [],
      workbook: null,
      ...dataset
    };
  }

  const sheet = parseFirstExcelSheet(file.path);
  const dataset = normalizeTable(sheet.rows, { maxRows: MAX_DATA_ROWS });

  return {
    format,
    sheetName: sheet.sheetName,
    warnings: sheet.warnings,
    workbook: sheet.workbook,
    ...dataset
  };
}

module.exports = {
  processFile,
  detectFileFormat,
  repairMergedHeaders,
  MAX_DATA_ROWS
};
