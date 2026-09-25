const { normalizeHeader } = require("../mapping/canonicalFields");
const { suggestMappings } = require("../mapping/suggestMapping");

const TYPE_FIELDS = {
  sales: { order_id: 2, order_date: 2, quantity: 1, revenue: 2, unit_price: 1 },
  inventory: { stock_qty: 2, reorder_level: 2, stock_as_of_date: 1 },
  customers: { customer_id: 2, customer_name: 2, customer_email: 2, customer_phone: 1, region: 1 },
  products: { product_name: 1.5, sku: 1.5, category: 1, unit_price: 1, cost_price: 1 },
  suppliers: { supplier_name: 3 }
};

function detectDatasetType(headers, rows = []) {
  const mappings = suggestMappings(headers, rows)
    .filter((item) => item.field && item.confidence >= 0.8);
  const mappedFields = new Set(mappings.map((item) => item.field));

  const scores = Object.entries(TYPE_FIELDS).map(([type, fields]) => ({
    type,
    score: Object.entries(fields).reduce(
      (score, [field, weight]) => score + (mappedFields.has(field) ? weight : 0),
      0
    )
  })).sort((a, b) => b.score - a.score);

  const best = scores[0];
  if (!best || best.score === 0) {
    return { type: "unknown", confidence: 0, evidence: [] };
  }

  const evidence = Object.keys(TYPE_FIELDS[best.type])
    .filter((field) => mappedFields.has(field));
  const confidence = Math.min(1, best.score / 5);

  return {
    type: best.type,
    confidence: Number(confidence.toFixed(2)),
    evidence,
    normalizedHeaders: headers.map(normalizeHeader)
  };
}

module.exports = { detectDatasetType };
