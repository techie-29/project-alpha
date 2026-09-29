const config = require("../config");
const { insight } = require("../helpers");

module.exports = function excessStock(context) {
  return (context.inventory || []).filter((item) => item.daysOfCover !== null && item.daysOfCover > config.excessStockDays).map((item) => insight("excess_stock", context, {
    type: "insight", category: "inventory", severity: "low",
    title: `${item.productName} has excess stock cover`,
    explanation: `Current stock represents about ${Math.round(item.daysOfCover)} days at recent sales velocity.`,
    evidence: { metric: "days_of_cover", value: item.daysOfCover, stock: item.stock, velocity: item.velocity },
    entity: { kind: "product", key: item.productKey, name: item.productName },
    action: "Review purchasing or consider a promotion.", link: `/analytics/inventory?product=${encodeURIComponent(item.productKey)}`
  }));
};
