const { normalizeHeader } = require("../mapping/canonicalFields");
const { suggestMappings } = require("../mapping/suggestMapping");

const TYPE_FIELDS = {
  sales: ["order_id", "order_date", "quantity", "revenue", "unit_price"],
  inventory: ["stock_qty", "reorder_level", "stock_as_of_date"],
  customers: ["customer_id", "customer_name", "customer_email", "customer_phone", "region"],
  products: ["product_name", "sku", "category", "unit_price", "cost_price"],
  suppliers: ["supplier_name"]
};

function detectDatasetType(headers, rows = []) {
  const mappings = suggestMappings(headers, rows)
    .filter((item) => item.field && item.confidence >= 0.8);
  const mappedFields = new Set(mappings.map((item) => item.field));

  const scores = Object.entries(TYPE_FIELDS).map(([type, fields]) => ({
    type,
    score: fields.filter((field) => mappedFields.has(field)).length
  })).sort((a, b) => b.score - a.score);

  const best = scores[0];
  if (!best || best.score === 0) {
    return { type: "unknown", confidence: 0, evidence: [] };
  }

  const evidence = TYPE_FIELDS[best.type].filter((field) => mappedFields.has(field));
  const confidence = Math.min(1, best.score / Math.min(3, TYPE_FIELDS[best.type].length));

  return {
    type: best.type,
    confidence: Number(confidence.toFixed(2)),
    evidence,
    normalizedHeaders: headers.map(normalizeHeader)
  };
}

module.exports = { detectDatasetType };
