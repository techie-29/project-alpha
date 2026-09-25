const config = require("../config");
const { insight } = require("../helpers");

module.exports = function stockoutRisk(context) {
  return (context.inventory || []).filter((item) => item.daysOfCover !== null && item.daysOfCover < config.stockoutRiskDays).flatMap((item) => {
    const common = {
      category: "inventory", severity: item.daysOfCover < 7 ? "critical" : "high",
      explanation: `${item.stock} units remain; recent sales average ${Number(item.velocity).toFixed(2)} units per day.`,
      evidence: { metric: "days_of_cover", value: item.daysOfCover, stock: item.stock, velocity: item.velocity, window_days: item.windowDays },
      entity: { kind: "product", key: item.productKey, name: item.productName },
      link: `/analytics/inventory?product=${encodeURIComponent(item.productKey)}`
    };
    return [
      insight("stockout_risk_alert", context, { ...common, type: "alert", title: `${item.productName} may run out in ${Math.round(item.daysOfCover)} days` }),
      insight("stockout_risk_action", context, { ...common, type: "recommendation", title: `Restock ${item.productName}`, action: `Reorder soon${item.reorderLevel !== null ? `; reorder level is ${item.reorderLevel}` : ""}.` })
    ];
  });
};
