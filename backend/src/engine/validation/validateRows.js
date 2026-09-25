const { parseNumber, normalizeText, normalizeStatus } = require("../transform/normalizers");
const { detectDateOrder, parseDate } = require("../transform/dateNormalizer");
const {
  isPresent,
  issue,
  requiredMissing,
  invalidEmail,
  impossibleValues
} = require("./rules");

const NUMERIC_FIELDS = new Set([
  "quantity", "unit_price", "discount", "revenue", "profit", "cost_price",
  "stock_qty", "reorder_level"
]);
const DATE_FIELDS = new Set(["order_date", "stock_as_of_date"]);

function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function mappedRecord(rawData, mappings) {
  const record = {};
  mappings.forEach(({ originalHeader, field }) => {
    if (field) record[field] = rawData?.[originalHeader] ?? null;
  });
  return record;
}

function stableKey(record) {
  return JSON.stringify(
    Object.keys(record).sort().map((key) => [key, record[key]])
  );
}

function validateRows({ rawRows, mappings, datasetType }) {
  const mapped = rawRows.map((row) => ({
    sourceRowNumber: row.sourceRowNumber,
    rawData: row.rawData,
    record: mappedRecord(row.rawData, mappings)
  }));

  const dateOrders = {};
  DATE_FIELDS.forEach((field) => {
    dateOrders[field] = detectDateOrder(mapped.map((row) => row.record[field]));
  });

  const medians = {};
  ["unit_price", "cost_price", "revenue"].forEach((field) => {
    medians[field] = median(
      mapped.map((row) => parseNumber(row.record[field])).filter((value) => value !== null && value >= 0)
    );
  });

  const seen = new Set();
  const issues = [];
  const rows = mapped.map(({ sourceRowNumber, rawData, record }) => {
    const rowIssues = [];
    const repairedFields = [];
    const normalized = {};

    Object.entries(record).forEach(([field, originalValue]) => {
      if (!isPresent(originalValue)) {
        normalized[field] = null;
        return;
      }

      if (NUMERIC_FIELDS.has(field)) {
        const value = parseNumber(originalValue);
        normalized[field] = value;
        if (value === null) {
          rowIssues.push(issue({
            rowIndex: sourceRowNumber,
            field,
            code: "INVALID_NUMBER",
            severity: "error",
            originalValue,
            message: "Value is not a valid number",
            action: "skipped"
          }));
        } else if (typeof originalValue !== "number" || originalValue !== value) {
          repairedFields.push(field);
          rowIssues.push(issue({
            rowIndex: sourceRowNumber,
            field,
            code: "NUMBER_NORMALIZED",
            severity: "repaired",
            originalValue,
            message: `Number normalized to ${value}`,
            action: "repaired"
          }));
        }
        return;
      }

      if (DATE_FIELDS.has(field)) {
        const orderInfo = dateOrders[field];
        const value = parseDate(originalValue, orderInfo.order);
        normalized[field] = value;
        const isAmbiguousNumeric = /^(\d{1,2})[\/-](\d{1,2})[\/-](\d{2,4})$/.test(String(originalValue).trim()) &&
          !orderInfo.order && orderInfo.reason !== "not_needed";
        if (isAmbiguousNumeric) {
          rowIssues.push(issue({
            rowIndex: sourceRowNumber,
            field,
            code: "AMBIGUOUS_DATE_FORMAT",
            severity: "error",
            originalValue,
            message: "Date order could be day/month or month/day and was not guessed",
            action: "skipped"
          }));
        } else if (!value) {
          rowIssues.push(issue({
            rowIndex: sourceRowNumber,
            field,
            code: "INVALID_DATE",
            severity: "error",
            originalValue,
            message: "Value is not a real supported date",
            action: "skipped"
          }));
        } else if (String(originalValue).slice(0, 10) !== value) {
          repairedFields.push(field);
          rowIssues.push(issue({
            rowIndex: sourceRowNumber,
            field,
            code: "DATE_NORMALIZED",
            severity: "repaired",
            originalValue,
            message: `Date normalized to ${value}`,
            action: "repaired"
          }));
        }
        return;
      }

      const value = field === "status" ? normalizeStatus(originalValue) : normalizeText(originalValue);
      normalized[field] = value;
      if (value !== originalValue) {
        repairedFields.push(field);
        rowIssues.push(issue({
          rowIndex: sourceRowNumber,
          field,
          code: field === "status" ? "STATUS_NORMALIZED" : "TEXT_NORMALIZED",
          severity: "repaired",
          originalValue,
          message: `Value normalized to ${value}`,
          action: "repaired"
        }));
      }
    });

    rowIssues.push(...requiredMissing({ rowIndex: sourceRowNumber, record: normalized, datasetType }));
    rowIssues.push(...invalidEmail({ rowIndex: sourceRowNumber, value: normalized.customer_email }));
    rowIssues.push(...impossibleValues({ rowIndex: sourceRowNumber, record: normalized }));

    ["unit_price", "cost_price", "revenue"].forEach((field) => {
      const baseline = medians[field];
      const value = normalized[field];
      if (baseline > 0 && value > baseline * 100) {
        rowIssues.push(issue({
          rowIndex: sourceRowNumber,
          field,
          code: "SUSPICIOUS_VALUE",
          severity: "warning",
          originalValue: record[field],
          message: `Value is more than 100 times the column median (${baseline})`,
          action: "kept"
        }));
      }
    });

    if (Object.values(normalized).every((value) => !isPresent(value))) {
      rowIssues.push(issue({
        rowIndex: sourceRowNumber,
        code: "EMPTY_ROW",
        severity: "error",
        message: "Mapped row contains no usable values",
        action: "skipped"
      }));
    }

    const key = stableKey(normalized);
    if (seen.has(key)) {
      rowIssues.push(issue({
        rowIndex: sourceRowNumber,
        code: "DUPLICATE_ROW",
        severity: "error",
        message: "Row duplicates an earlier normalized record",
        action: "skipped"
      }));
    } else {
      seen.add(key);
    }

    issues.push(...rowIssues);
    const skipped = rowIssues.some((rowIssue) => rowIssue.severity === "error");
    const status = skipped ? "skipped" : repairedFields.length ? "repaired" : "valid";
    return {
      sourceRowNumber,
      status,
      canonical: normalized,
      rawValues: rawData,
      repairedFields: [...new Set(repairedFields)],
      issues: rowIssues
    };
  });

  const counts = rows.reduce((summary, row) => {
    summary[row.status] += 1;
    return summary;
  }, { valid: 0, repaired: 0, skipped: 0 });

  return {
    rows,
    issues,
    dateOrders,
    summary: {
      totalRows: rows.length,
      validRows: counts.valid,
      repairedRows: counts.repaired,
      skippedRows: counts.skipped,
      issueCount: issues.length,
      validationSuccessRate: rows.length ? Number(((rows.length - counts.skipped) / rows.length).toFixed(4)) : 0
    }
  };
}

module.exports = { validateRows, mappedRecord, stableKey, median };
