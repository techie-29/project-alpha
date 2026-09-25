const { normalizeText, normalizeStatus, productKey } = require("./normalizers");

function customerKey(record) {
  return normalizeText(record.customer_email)?.toLowerCase() ||
    normalizeText(record.customer_id)?.toLowerCase() ||
    normalizeText(record.customer_name)?.toLowerCase() ||
    null;
}

function deriveStockStatus(stock, reorderLevel) {
  if (stock === null || stock === undefined) return null;
  if (stock <= 0) return "out_of_stock";
  if (reorderLevel !== null && reorderLevel !== undefined && stock <= reorderLevel) return "low_stock";
  return "healthy";
}

function saleRecord(row, context) {
  const value = row.canonical;
  const discount = value.discount ?? 0;
  const calculatedRevenue = value.quantity !== null && value.quantity !== undefined &&
    value.unit_price !== null && value.unit_price !== undefined
    ? value.quantity * value.unit_price - discount
    : null;
  const revenue = value.revenue ?? calculatedRevenue;
  const totalCost = value.cost_price !== null && value.cost_price !== undefined &&
    value.quantity !== null && value.quantity !== undefined
    ? value.cost_price * value.quantity
    : null;
  const profit = value.profit ?? (
    revenue !== null && totalCost !== null ? revenue - totalCost : null
  );
  const computedFields = [];
  if (value.revenue === null || value.revenue === undefined) {
    if (calculatedRevenue !== null) computedFields.push("revenue");
  }
  if (value.profit === null || value.profit === undefined) {
    if (profit !== null) computedFields.push("profit");
  }

  return {
    dataset_id: context.datasetId,
    business_id: context.businessId,
    source_row_index: row.sourceRowNumber,
    order_id: normalizeText(value.order_id),
    order_date: value.order_date ?? null,
    product_key: productKey(value),
    product_name: normalizeText(value.product_name),
    sku: normalizeText(value.sku),
    category: normalizeText(value.category),
    quantity: value.quantity ?? null,
    unit_price: value.unit_price ?? null,
    discount,
    revenue,
    cost_price: value.cost_price ?? null,
    profit,
    customer_key: customerKey(value),
    customer_id: normalizeText(value.customer_id),
    customer_name: normalizeText(value.customer_name),
    customer_email: normalizeText(value.customer_email)?.toLowerCase() || null,
    status: normalizeStatus(value.status),
    notes: normalizeText(value.notes),
    repaired_fields: row.repairedFields || [],
    computed_fields: computedFields,
    raw_values: row.rawValues
  };
}

function stockSnapshot(row, context) {
  const value = row.canonical;
  const stockStatus = deriveStockStatus(value.stock_qty, value.reorder_level);
  return {
    dataset_id: context.datasetId,
    business_id: context.businessId,
    source_row_index: row.sourceRowNumber,
    product_key: productKey(value),
    product_name: normalizeText(value.product_name),
    sku: normalizeText(value.sku),
    stock_qty: value.stock_qty ?? null,
    reorder_level: value.reorder_level ?? null,
    stock_status: stockStatus,
    stock_as_of_date: value.stock_as_of_date ?? null,
    supplier_name: normalizeText(value.supplier_name),
    repaired_fields: row.repairedFields || [],
    computed_fields: stockStatus ? ["stock_status"] : [],
    raw_values: row.rawValues
  };
}

function customerRecord(row, context) {
  const value = row.canonical;
  return {
    dataset_id: context.datasetId,
    business_id: context.businessId,
    source_row_index: row.sourceRowNumber,
    customer_key: customerKey(value),
    customer_id: normalizeText(value.customer_id),
    customer_name: normalizeText(value.customer_name),
    customer_email: normalizeText(value.customer_email)?.toLowerCase() || null,
    customer_phone: normalizeText(value.customer_phone),
    region: normalizeText(value.region),
    repaired_fields: row.repairedFields || [],
    raw_values: row.rawValues
  };
}

function productRecord(row, context) {
  const value = row.canonical;
  return {
    dataset_id: context.datasetId,
    business_id: context.businessId,
    source_row_index: row.sourceRowNumber,
    product_key: productKey(value),
    product_name: normalizeText(value.product_name),
    sku: normalizeText(value.sku),
    category: normalizeText(value.category),
    unit_price: value.unit_price ?? null,
    cost_price: value.cost_price ?? null,
    supplier_name: normalizeText(value.supplier_name),
    repaired_fields: row.repairedFields || [],
    raw_values: row.rawValues
  };
}

function supplierRecord(row, context) {
  const value = row.canonical;
  const supplierName = normalizeText(value.supplier_name);
  return {
    dataset_id: context.datasetId,
    business_id: context.businessId,
    source_row_index: row.sourceRowNumber,
    supplier_key: supplierName?.toLowerCase() || null,
    supplier_name: supplierName,
    repaired_fields: row.repairedFields || [],
    raw_values: row.rawValues
  };
}

function transformValidatedRows({ rows, datasetType, datasetId, businessId }) {
  const acceptedRows = rows.filter((row) => row.status !== "skipped");
  const context = { datasetId, businessId };
  const sales = [];
  const stock = [];
  const customers = [];
  const products = [];
  const suppliers = [];

  acceptedRows.forEach((row) => {
    const value = row.canonical;
    const hasSales = datasetType === "sales" || value.order_id || value.order_date || value.quantity !== undefined || value.revenue !== undefined;
    const hasStock = datasetType === "inventory" || value.stock_qty !== undefined || value.reorder_level !== undefined;
    const hasCustomer = datasetType === "customers" || value.customer_id || value.customer_email || value.customer_name;
    const hasProduct = datasetType === "products";
    const hasSupplier = datasetType === "suppliers";
    if (hasSales) sales.push(saleRecord(row, context));
    if (hasStock) stock.push(stockSnapshot(row, context));
    if (hasCustomer) customers.push(customerRecord(row, context));
    if (hasProduct) products.push(productRecord(row, context));
    if (hasSupplier) suppliers.push(supplierRecord(row, context));
  });

  return {
    sales,
    stock,
    customers,
    products,
    suppliers,
    summary: {
      inputRows: rows.length,
      acceptedRows: acceptedRows.length,
      skippedRows: rows.length - acceptedRows.length,
      salesRecords: sales.length,
      stockSnapshots: stock.length,
      customerRecords: customers.length,
      productRecords: products.length,
      supplierRecords: suppliers.length
    },
    examples: {
      sales: sales.slice(0, 3),
      stock: stock.slice(0, 3),
      customers: customers.slice(0, 3),
      products: products.slice(0, 3),
      suppliers: suppliers.slice(0, 3)
    }
  };
}

module.exports = {
  customerKey,
  deriveStockStatus,
  saleRecord,
  stockSnapshot,
  productRecord,
  supplierRecord,
  transformValidatedRows
};
