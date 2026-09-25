const { insight } = require("../helpers");

module.exports = function lowStock(context) {
  return (context.inventory || []).filter((item) => item.stock !== null && item.reorderLevel !== null && item.stock <= item.reorderLevel).map((item) => insight("low_stock", context, {
    type: "alert", category: "inventory", severity: item.stock <= 0 ? "critical" : "high",
    title: item.stock <= 0 ? `${item.productName} is out of stock` : `${item.productName} is below its reorder level`,
    explanation: `${item.productName} has ${item.stock} units against a reorder level of ${item.reorderLevel}.`,
    evidence: { metric: "stock_qty", value: item.stock, reorder_level: item.reorderLevel },
    entity: { kind: "product", key: item.productKey, name: item.productName },
    action: "Review and replenish this product.",
    link: `/analytics/inventory?product=${encodeURIComponent(item.productKey)}`
  }));
};
