const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const REQUIRED_GROUPS = {
  sales: [
    ["order_date"], ["quantity"], ["product_name", "sku"], ["revenue", "unit_price"]
  ],
  inventory: [["product_name", "sku"], ["stock_qty"]],
  customers: [["customer_id", "customer_email", "customer_name"]],
  suppliers: [["supplier_name"]],
  products: [["product_name", "sku"]]
};

function isPresent(value) {
  return value !== null && value !== undefined && String(value).trim() !== "";
}

function issue({ rowIndex, field = null, code, severity, originalValue = null, message, action }) {
  return {
    row_index: rowIndex,
    field,
    code,
    severity,
    original_value: originalValue,
    message,
    action
  };
}

function requiredMissing({ rowIndex, record, datasetType }) {
  const groups = REQUIRED_GROUPS[datasetType] || [];
  return groups
    .filter((group) => !group.some((field) => isPresent(record[field])))
    .map((group) => issue({
      rowIndex,
      field: group.join("|"),
      code: "REQUIRED_MISSING",
      severity: "error",
      message: `A required value is missing (${group.join(" or ")})`,
      action: "skipped"
    }));
}

function invalidEmail({ rowIndex, value }) {
  if (!isPresent(value) || EMAIL_PATTERN.test(String(value).trim())) return [];
  return [issue({
    rowIndex,
    field: "customer_email",
    code: "INVALID_EMAIL",
    severity: "warning",
    originalValue: value,
    message: "Email format is invalid",
    action: "kept"
  })];
}

function impossibleValues({ rowIndex, record }) {
  const issues = [];
  if (record.quantity < 0) {
    issues.push(issue({
      rowIndex,
      field: "quantity",
      code: "NEGATIVE_QUANTITY",
      severity: "error",
      originalValue: record.quantity,
      message: "Quantity cannot be negative",
      action: "skipped"
    }));
  }
  if (record.stock_qty < 0) {
    issues.push(issue({
      rowIndex,
      field: "stock_qty",
      code: "NEGATIVE_STOCK",
      severity: "error",
      originalValue: record.stock_qty,
      message: "Stock quantity cannot be negative",
      action: "skipped"
    }));
  }
  return issues;
}

module.exports = {
  EMAIL_PATTERN,
  REQUIRED_GROUPS,
  isPresent,
  issue,
  requiredMissing,
  invalidEmail,
  impossibleValues
};
