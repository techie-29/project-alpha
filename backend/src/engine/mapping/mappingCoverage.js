const REQUIRED_FIELD_GROUPS = {
  sales: [
    ["order_date"],
    ["quantity"],
    ["product_name", "sku"],
    ["revenue", "unit_price"]
  ],
  inventory: [
    ["product_name", "sku"],
    ["stock_qty"]
  ],
  customers: [
    ["customer_id", "customer_email", "customer_name"]
  ],
  suppliers: [
    ["supplier_name"]
  ],
  products: [
    ["product_name", "sku"]
  ]
};

function calculateMappingCoverage({ datasetType, mappings, totalHeaders }) {
  const mappedFields = new Set(
    mappings.map((mapping) => mapping.field).filter(Boolean)
  );
  const headerCount = totalHeaders ?? mappings.length;
  const headerCoverage = headerCount === 0 ? 0 : mappedFields.size / headerCount;
  const groups = REQUIRED_FIELD_GROUPS[datasetType] || [];
  const matchedGroups = groups.filter((group) => (
    group.some((field) => mappedFields.has(field))
  ));
  const requiredCoverage = groups.length === 0
    ? headerCoverage
    : matchedGroups.length / groups.length;
  const missingCriticalFields = groups
    .filter((group) => !group.some((field) => mappedFields.has(field)))
    .map((group) => group.join("|"));

  return {
    coverage: Number(requiredCoverage.toFixed(4)),
    headerCoverage: Number(headerCoverage.toFixed(4)),
    mappedHeaders: mappings.filter((mapping) => mapping.field).length,
    totalHeaders: headerCount,
    missingCriticalFields,
    requiredFieldGroups: groups
  };
}

module.exports = { REQUIRED_FIELD_GROUPS, calculateMappingCoverage };
