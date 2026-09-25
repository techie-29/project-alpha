const config = require("../config");
const { insight } = require("../helpers");

module.exports = function slowMoving(context) {
  return (context.inventory || []).filter((item) => item.stock > 0 && (item.daysSinceLastSale === null || item.daysSinceLastSale >= config.slowMovingDays)).map((item) => insight("slow_moving", context, {
    type: "insight", category: "inventory", severity: "medium", title: `${item.productName} is slow moving`,
    explanation: item.daysSinceLastSale === null
      ? `${item.stock} units are in stock with no recorded sale in the available history.`
      : `${item.stock} units are in stock and the last recorded sale was ${item.daysSinceLastSale} days ago.`,
    evidence: { metric: "days_since_last_sale", value: item.daysSinceLastSale, stock: item.stock },
    entity: { kind: "product", key: item.productKey, name: item.productName }, action: "Review demand and promotion options.",
    link: `/analytics/inventory?product=${encodeURIComponent(item.productKey)}`
  }));
};
